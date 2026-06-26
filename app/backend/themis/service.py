from __future__ import annotations

import asyncio
import statistics
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from .auth import CurrentUser
from .dify import run_workflow
from .logger import write_log
from .models import (
    Experiment,
    ExperimentSample,
    ExperimentStatus,
    ExperimentVariant,
    LabelStatus,
    LabelingResult,
    LabelingTask,
    LabelingTaskItem,
    ResponseMode,
    RunStatus,
    VariantRole,
    VariantRun,
)
from .schemas import ExperimentCreate, ExperimentUpdate
from .validation import render_merge_template, validate_merge_template, validate_payload, validate_required_and_types, validate_schema_document


COLORS = {
    VariantRole.CONTROL: "#0A84FF",
    VariantRole.EXPERIMENT_A: "#FF375F",
    VariantRole.EXPERIMENT_B: "#6750A4",
}


def _experiment_query() -> Select:
    return select(Experiment).options(selectinload(Experiment.variants)).order_by(Experiment.created_at.desc())


def validate_experiment_payload(payload: ExperimentCreate | ExperimentUpdate) -> None:
    validate_schema_document(payload.input_schema)
    roles = [variant.role for variant in payload.variants]
    if VariantRole.CONTROL not in roles or VariantRole.EXPERIMENT_A not in roles:
        raise HTTPException(status_code=400, detail="Control and experiment A are required")
    if len(set(roles)) != len(roles):
        raise HTTPException(status_code=400, detail="Variant roles must be unique")
    if len(payload.variants) > 3:
        raise HTTPException(status_code=400, detail="At most one control and two experiment variants are supported")
    for variant in payload.variants:
        try:
            validate_schema_document(variant.output_schema)
            validate_merge_template(variant.merge_template)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{variant.role.value}: {exc}") from exc
        if payload.preference_enabled and not variant.merge_template:
            raise HTTPException(status_code=400, detail=f"{variant.role.value}: merge template is required")


def list_experiments(db: Session) -> list[Experiment]:
    return list(db.scalars(_experiment_query()))


def get_experiment(db: Session, experiment_id: int) -> Experiment:
    exp = db.scalar(select(Experiment).options(selectinload(Experiment.variants)).where(Experiment.id == experiment_id))
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


def create_experiment(db: Session, payload: ExperimentCreate, user: CurrentUser) -> Experiment:
    validate_experiment_payload(payload)
    exp = Experiment(
        uuid=str(uuid.uuid4()),
        name=payload.name,
        api_key=payload.api_key,
        response_mode=payload.response_mode,
        input_schema=payload.input_schema,
        preference_enabled=payload.preference_enabled,
        status=ExperimentStatus.NOT_STARTED,
        created_by=user.username,
    )
    exp.variants = [
        ExperimentVariant(
            role=variant.role,
            name=variant.name,
            description=variant.description,
            workflow_id=variant.workflow_id,
            output_schema=variant.output_schema,
            merge_template=variant.merge_template,
            display_order=variant.display_order,
        )
        for variant in sorted(payload.variants, key=lambda v: v.display_order)
    ]
    db.add(exp)
    db.commit()
    db.refresh(exp)
    write_log(action="experiment.create", status="success", user_id=user.username, experiment_uuid=exp.uuid)
    return get_experiment(db, exp.id)


def update_experiment(db: Session, experiment_id: int, payload: ExperimentUpdate, user: CurrentUser) -> Experiment:
    exp = get_experiment(db, experiment_id)
    if exp.status != ExperimentStatus.NOT_STARTED:
        raise HTTPException(status_code=400, detail="Only not-started experiments can be edited")
    validate_experiment_payload(payload)
    exp.name = payload.name
    exp.api_key = payload.api_key
    exp.response_mode = payload.response_mode
    exp.input_schema = payload.input_schema
    exp.preference_enabled = payload.preference_enabled
    exp.variants.clear()
    db.flush()
    exp.variants = [
        ExperimentVariant(
            role=variant.role,
            name=variant.name,
            description=variant.description,
            workflow_id=variant.workflow_id,
            output_schema=variant.output_schema,
            merge_template=variant.merge_template,
            display_order=variant.display_order,
        )
        for variant in sorted(payload.variants, key=lambda v: v.display_order)
    ]
    db.commit()
    write_log(action="experiment.update", status="success", user_id=user.username, experiment_uuid=exp.uuid)
    return get_experiment(db, exp.id)


def import_samples(db: Session, experiment_id: int, samples: list[dict[str, Any]], background_tasks: BackgroundTasks, user: CurrentUser) -> dict:
    exp = get_experiment(db, experiment_id)
    if exp.status != ExperimentStatus.NOT_STARTED:
        raise HTTPException(status_code=400, detail="Only not-started experiments can import samples")
    errors = []
    for idx, sample in enumerate(samples):
        sample_errors = validate_payload(exp.input_schema, sample)
        if sample_errors:
            errors.append({"index": idx, "errors": sample_errors})
    if errors:
        return {"imported": 0, "experiment_uuid": exp.uuid, "errors": errors[:20]}
    for sample in samples:
        db.add(ExperimentSample(experiment_id=exp.id, sample_uuid=str(uuid.uuid4()), input_payload=sample))
    exp.total_samples = len(samples)
    exp.executed_samples = 0
    exp.status = ExperimentStatus.RUNNING
    db.commit()
    write_log(
        action="samples.import",
        status="success",
        user_id=user.username,
        experiment_uuid=exp.uuid,
        metadata={"count": len(samples)},
    )
    background_tasks.add_task(execute_experiment_sync, exp.id)
    return {"imported": len(samples), "experiment_uuid": exp.uuid, "errors": []}


def execute_experiment_sync(experiment_id: int) -> None:
    from .database import SessionLocal

    asyncio.run(_execute_experiment(experiment_id, SessionLocal))


async def _execute_experiment(experiment_id: int, session_factory) -> None:
    db: Session = session_factory()
    try:
        exp = get_experiment(db, experiment_id)
        samples = list(db.scalars(select(ExperimentSample).where(ExperimentSample.experiment_id == exp.id).order_by(ExperimentSample.id)))
        variants = list(exp.variants)
        for sample in samples:
            for variant in variants:
                await _run_variant(db, exp, sample, variant)
            exp.executed_samples += 1
            db.commit()
        if exp.preference_enabled:
            _create_labeling_tasks(db, exp)
            exp.status = ExperimentStatus.RUNNING
        else:
            exp.status = ExperimentStatus.COMPLETED
            exp.completed_at = datetime.utcnow()
        db.commit()
        write_log(action="experiment.execute", status="success", experiment_uuid=exp.uuid)
    except Exception as exc:
        db.rollback()
        exp = db.get(Experiment, experiment_id)
        if exp:
            exp.status = ExperimentStatus.FAILED
            db.commit()
            write_log(action="experiment.execute", status="failed", level="ERROR", experiment_uuid=exp.uuid, why=str(exc))
    finally:
        db.close()


async def _run_variant(db: Session, exp: Experiment, sample: ExperimentSample, variant: ExperimentVariant) -> None:
    result = await run_workflow(
        api_key=exp.api_key,
        workflow_id=variant.workflow_id,
        inputs=sample.input_payload,
        response_mode=exp.response_mode,
    )
    status = result.status
    schema_errors = None
    if status == RunStatus.SUCCESS:
        response_for_validation = _extract_outputs(result.response_payload)
        schema_errors = validate_required_and_types(variant.output_schema, response_for_validation)
        if schema_errors:
            status = RunStatus.SCHEMA_INVALID
    db.add(
        VariantRun(
            experiment_id=exp.id,
            sample_id=sample.id,
            variant_id=variant.id,
            status=status,
            http_status=result.http_status,
            request_payload=result.request_payload,
            response_payload=result.response_payload,
            error_message=result.error_message,
            schema_validation_error=schema_errors or None,
            latency_ms=result.latency_ms if status == RunStatus.SUCCESS else None,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
    )
    write_log(
        action="dify.call",
        status=status.value,
        experiment_uuid=exp.uuid,
        resource_type="variant",
        resource_id=str(variant.id),
        metadata={"sample_uuid": sample.sample_uuid, "latency_ms": result.latency_ms},
    )


def _extract_outputs(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("outputs"), dict):
        return payload["data"]["outputs"]
    if isinstance(payload.get("outputs"), dict):
        return payload["outputs"]
    return payload


def _create_labeling_tasks(db: Session, exp: Experiment) -> None:
    samples = list(db.scalars(select(ExperimentSample).where(ExperimentSample.experiment_id == exp.id)))
    variants = list(exp.variants)
    for sample in samples:
        runs = list(
            db.scalars(
                select(VariantRun).where(VariantRun.sample_id == sample.id).options(selectinload(VariantRun.variant))
            )
        )
        by_variant = {run.variant_id: run for run in runs}
        if any(by_variant.get(variant.id) is None or by_variant[variant.id].status != RunStatus.SUCCESS for variant in variants):
            continue
        task = LabelingTask(experiment_id=exp.id, sample_id=sample.id, task_uuid=str(uuid.uuid4()))
        for variant in variants:
            run = by_variant[variant.id]
            output = _extract_outputs(run.response_payload)
            try:
                merged = render_merge_template(variant.merge_template, output)
            except Exception:
                merged = str(output)
            task.items.append(
                LabelingTaskItem(
                    variant_id=variant.id,
                    merged_output=merged,
                    display_order=variant.display_order,
                )
            )
        db.add(task)


def close_experiment(db: Session, experiment_id: int, user: CurrentUser) -> Experiment:
    exp = get_experiment(db, experiment_id)
    if exp.preference_enabled:
        total = db.scalar(select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id)) or 0
        unlabeled = db.scalar(
            select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id, LabelingTask.status == LabelStatus.UNLABELED)
        ) or 0
        if total > 0 and unlabeled > 0:
            raise HTTPException(status_code=400, detail="All labeling tasks must be completed before closing")
    exp.status = ExperimentStatus.COMPLETED
    exp.completed_at = datetime.utcnow()
    db.commit()
    write_log(action="experiment.close", status="success", user_id=user.username, experiment_uuid=exp.uuid)
    return get_experiment(db, exp.id)


def build_report(db: Session, experiment_id: int) -> dict[str, Any]:
    exp = get_experiment(db, experiment_id)
    metrics = []
    for variant in exp.variants:
        runs = list(db.scalars(select(VariantRun).where(VariantRun.experiment_id == exp.id, VariantRun.variant_id == variant.id)))
        total = len(runs)
        request_success = [r for r in runs if r.status in (RunStatus.SUCCESS, RunStatus.SCHEMA_INVALID)]
        schema_valid = [r for r in runs if r.status == RunStatus.SUCCESS]
        latencies = sorted([r.latency_ms for r in schema_valid if r.latency_ms is not None])
        metrics.append(
            {
                "variant_id": variant.id,
                "role": variant.role,
                "name": variant.name,
                "color": COLORS[variant.role],
                "total": total,
                "success_count": len(request_success),
                "schema_valid_count": len(schema_valid),
                "success_rate": round(len(request_success) / total * 100, 2) if total else 0,
                "stability_rate": round(len(schema_valid) / len(request_success) * 100, 2) if request_success else 0,
                "latency_avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
                "latency_median_ms": round(statistics.median(latencies), 2) if latencies else None,
                "latency_q1_ms": _quantile(latencies, 0.25),
                "latency_q3_ms": _quantile(latencies, 0.75),
            }
        )
    labeling = None
    if exp.preference_enabled:
        total = db.scalar(select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id)) or 0
        labeled = db.scalar(
            select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id, LabelingTask.status == LabelStatus.LABELED)
        ) or 0
        winner_counts = defaultdict(int)
        rows = db.execute(
            select(LabelingResult.selected_variant_id, func.count(LabelingResult.id))
            .join(LabelingTask, LabelingResult.task_id == LabelingTask.id)
            .where(LabelingTask.experiment_id == exp.id)
            .group_by(LabelingResult.selected_variant_id)
        ).all()
        for variant_id, count in rows:
            winner_counts[variant_id] = count
        labeling = {
            "total": total,
            "labeled": labeled,
            "winners": [
                {"variant_id": variant.id, "name": variant.name, "role": variant.role.value, "color": COLORS[variant.role], "count": winner_counts[variant.id]}
                for variant in exp.variants
            ],
        }
    return {"experiment": exp, "metrics": metrics, "labeling": labeling}


def _quantile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    pos = (len(values) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    weight = pos - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight, 2)
