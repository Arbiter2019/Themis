from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.append(str(Path(__file__).resolve().parents[1]))

from themis.database import SessionLocal
from themis.models import Experiment, LabelingTask, LabelingTaskItem, VariantRun
from themis.service import _extract_outputs
from themis.validation import render_merge_template


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild labeling item merged_output from variant run outputs and merge templates.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--experiment-id", type=int)
    group.add_argument("--experiment-uuid")
    parser.add_argument("--dry-run", action="store_true", help="Preview affected item count without writing updates.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        experiment = _load_experiment(db, args.experiment_id, args.experiment_uuid)
        tasks = list(
            db.scalars(
                select(LabelingTask)
                .options(selectinload(LabelingTask.items).selectinload(LabelingTaskItem.variant))
                .where(LabelingTask.experiment_id == experiment.id)
            )
        )
        updated = 0
        skipped = 0
        for task in tasks:
            for item in task.items:
                run = db.scalar(
                    select(VariantRun).where(
                        VariantRun.sample_id == task.sample_id,
                        VariantRun.variant_id == item.variant_id,
                    )
                )
                if not run:
                    skipped += 1
                    continue
                output = _extract_outputs(run.response_payload)
                next_output = render_merge_template(item.variant.merge_template, output)
                if item.merged_output != next_output:
                    updated += 1
                    if not args.dry_run:
                        item.merged_output = next_output
        if not args.dry_run:
            db.commit()
        print(f"experiment_id={experiment.id}")
        print(f"tasks={len(tasks)}")
        print(f"updated_items={updated}")
        print(f"skipped_items={skipped}")
        print(f"dry_run={args.dry_run}")
    finally:
        db.close()


def _load_experiment(db, experiment_id: int | None, experiment_uuid: str | None) -> Experiment:
    if experiment_id is not None:
        experiment = db.get(Experiment, experiment_id)
    else:
        experiment = db.scalar(select(Experiment).where(Experiment.uuid == experiment_uuid))
    if not experiment:
        raise SystemExit("experiment not found")
    return experiment


if __name__ == "__main__":
    main()
