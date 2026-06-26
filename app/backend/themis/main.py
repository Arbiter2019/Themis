from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .auth import (
    CurrentUser,
    authenticate,
    create_session,
    destroy_session,
    get_current_user,
    require_admin,
    require_labeler_or_admin,
)
from .config import get_settings
from .database import Base, engine, get_db
from .logger import write_log
from .models import Experiment, LabelStatus, LabelingResult, LabelingTask, LabelingTaskItem
from .schemas import (
    ExperimentCreate,
    ExperimentListItem,
    ExperimentOut,
    ExperimentUpdate,
    ImportSamplesRequest,
    ImportSamplesResponse,
    LabelingExperimentItem,
    LabelingTaskDetail,
    LabelingTaskItemOut,
    LabelingTaskListItem,
    LoginRequest,
    LoginResponse,
    OkResponse,
    ReportOut,
    SubmitLabelRequest,
    ValidateSchemaRequest,
    ValidateTemplateRequest,
)
from .service import (
    build_report,
    close_experiment,
    create_experiment,
    get_experiment,
    import_samples,
    list_experiments,
    update_experiment,
)
from .validation import validate_merge_template, validate_schema_document


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "themis"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    user = authenticate(payload.username, payload.password)
    if not user:
        write_log(action="login", status="failed", user_id=payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(user)
    write_log(action="login", status="success", user_id=user.username)
    return LoginResponse(token=token, username=user.username, role=user.role)


@app.post("/api/auth/logout", response_model=OkResponse)
def logout(user: CurrentUser = Depends(get_current_user), authorization: str | None = Header(default=None)) -> OkResponse:
    if authorization:
        destroy_session(authorization.removeprefix("Bearer ").strip())
    write_log(action="logout", status="success", user_id=user.username)
    return OkResponse()


@app.get("/api/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    return {"username": user.username, "role": user.role}


@app.post("/api/validate/schema", response_model=OkResponse)
def validate_schema(payload: ValidateSchemaRequest, _: CurrentUser = Depends(require_admin)) -> OkResponse:
    try:
        validate_schema_document(payload.schema_doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OkResponse()


@app.post("/api/validate/template", response_model=OkResponse)
def validate_template(payload: ValidateTemplateRequest, _: CurrentUser = Depends(require_admin)) -> OkResponse:
    try:
        validate_merge_template(payload.template)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OkResponse()


@app.get("/api/experiments", response_model=list[ExperimentListItem])
def api_list_experiments(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> list[Experiment]:
    return list_experiments(db)


@app.post("/api/experiments", response_model=ExperimentOut)
def api_create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)) -> Experiment:
    return create_experiment(db, payload, user)


@app.get("/api/experiments/{experiment_id}", response_model=ExperimentOut)
def api_get_experiment(experiment_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> Experiment:
    return get_experiment(db, experiment_id)


@app.put("/api/experiments/{experiment_id}", response_model=ExperimentOut)
def api_update_experiment(
    experiment_id: int,
    payload: ExperimentUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
) -> Experiment:
    return update_experiment(db, experiment_id, payload, user)


@app.post("/api/experiments/{experiment_id}/import", response_model=ImportSamplesResponse)
def api_import_samples(
    experiment_id: int,
    payload: ImportSamplesRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
) -> dict:
    return import_samples(db, experiment_id, payload.samples, user)


@app.get("/api/experiments/{experiment_id}/report", response_model=ReportOut)
def api_report(experiment_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> dict:
    return build_report(db, experiment_id)


@app.post("/api/experiments/{experiment_id}/close", response_model=ExperimentOut)
def api_close_experiment(experiment_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)) -> Experiment:
    return close_experiment(db, experiment_id, user)


@app.get("/api/labeling/experiments", response_model=list[LabelingExperimentItem])
def labeling_experiments(db: Session = Depends(get_db), _: CurrentUser = Depends(require_labeler_or_admin)) -> list[dict]:
    rows = []
    experiments = db.scalars(
        select(Experiment).where(Experiment.preference_enabled.is_(True)).order_by(Experiment.created_at.desc())
    )
    for exp in experiments:
        total = db.scalar(select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id)) or 0
        labeled = db.scalar(
            select(func.count(LabelingTask.id)).where(LabelingTask.experiment_id == exp.id, LabelingTask.status == LabelStatus.LABELED)
        ) or 0
        rows.append(
            {
                "experiment_id": exp.id,
                "experiment_uuid": exp.uuid,
                "name": exp.name,
                "created_at": exp.created_at,
                "total": total,
                "labeled": labeled,
            }
        )
    return rows


@app.get("/api/labeling/experiments/{experiment_id}/tasks", response_model=list[LabelingTaskListItem])
def labeling_tasks(experiment_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_labeler_or_admin)) -> list[dict]:
    tasks = db.scalars(
        select(LabelingTask)
        .options(selectinload(LabelingTask.result).selectinload(LabelingResult.selected_variant))
        .where(LabelingTask.experiment_id == experiment_id)
        .order_by(LabelingTask.created_at.desc())
    )
    rows = []
    for task in tasks:
        rows.append(
            {
                "id": task.id,
                "task_uuid": task.task_uuid,
                "status": task.status,
                "winner_name": task.result.selected_variant.name if task.result else None,
                "created_at": task.created_at,
                "labeled_at": task.labeled_at,
            }
        )
    return rows


@app.get("/api/labeling/tasks/{task_id}", response_model=LabelingTaskDetail)
def labeling_task_detail(task_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_labeler_or_admin)) -> dict:
    task = db.scalar(
        select(LabelingTask)
        .options(selectinload(LabelingTask.items).selectinload(LabelingTaskItem.variant))
        .where(LabelingTask.id == task_id)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Labeling task not found")
    items = [
        LabelingTaskItemOut(
            id=item.id,
            variant_id=item.variant_id,
            variant_name=item.variant.name,
            variant_description=item.variant.description,
            workflow_id=item.variant.workflow_id,
            merged_output=item.merged_output,
            display_order=item.display_order,
        )
        for item in task.items
    ]
    return {"id": task.id, "task_uuid": task.task_uuid, "status": task.status, "items": items}


@app.post("/api/labeling/tasks/{task_id}/submit", response_model=OkResponse)
def submit_label(
    task_id: int,
    payload: SubmitLabelRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_labeler_or_admin),
) -> OkResponse:
    task = db.scalar(select(LabelingTask).options(selectinload(LabelingTask.items)).where(LabelingTask.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Labeling task not found")
    if task.status == LabelStatus.LABELED:
        raise HTTPException(status_code=400, detail="Task already labeled")
    variant_ids = {item.variant_id for item in task.items}
    if payload.selected_variant_id not in variant_ids:
        raise HTTPException(status_code=400, detail="Selected variant is not part of this task")
    task.status = LabelStatus.LABELED
    task.labeled_at = datetime.utcnow()
    db.add(LabelingResult(task_id=task.id, selected_variant_id=payload.selected_variant_id, labeled_by=user.username))
    db.commit()
    write_log(
        action="label.submit",
        status="success",
        user_id=user.username,
        resource_type="labeling_task",
        resource_id=str(task.id),
        metadata={"selected_variant_id": payload.selected_variant_id},
    )
    return OkResponse()
