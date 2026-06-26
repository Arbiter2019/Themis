from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import ExperimentStatus, LabelStatus, ResponseMode, RunStatus, VariantRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str


class VariantIn(BaseModel):
    role: VariantRole
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=600)
    workflow_id: str = Field(max_length=150)
    output_schema: dict[str, Any]
    merge_template: str | None = Field(default=None, max_length=1000)
    display_order: int


class ExperimentCreate(BaseModel):
    name: str = Field(max_length=100)
    api_key: str = Field(max_length=255)
    response_mode: ResponseMode = ResponseMode.BLOCKING
    input_schema: dict[str, Any]
    preference_enabled: bool = False
    variants: list[VariantIn]


class ExperimentUpdate(ExperimentCreate):
    pass


class VariantOut(VariantIn):
    id: int

    class Config:
        from_attributes = True


class ExperimentOut(BaseModel):
    id: int
    uuid: str
    name: str
    api_key: str
    response_mode: ResponseMode
    input_schema: dict[str, Any]
    preference_enabled: bool
    status: ExperimentStatus
    total_samples: int
    executed_samples: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    variants: list[VariantOut] = []

    class Config:
        from_attributes = True


class ExperimentListItem(BaseModel):
    id: int
    uuid: str
    name: str
    preference_enabled: bool
    status: ExperimentStatus
    total_samples: int
    executed_samples: int
    created_at: datetime

    class Config:
        from_attributes = True


class ImportSamplesRequest(BaseModel):
    samples: list[dict[str, Any]]


class ImportSamplesResponse(BaseModel):
    imported: int
    experiment_uuid: str
    errors: list[dict[str, Any]] = []


class MetricPoint(BaseModel):
    variant_id: int
    role: VariantRole
    name: str
    color: str
    total: int
    success_count: int
    schema_valid_count: int
    success_rate: float
    stability_rate: float
    latency_avg_ms: float | None
    latency_median_ms: float | None
    latency_q1_ms: float | None
    latency_q3_ms: float | None


class LabelingSummary(BaseModel):
    total: int
    labeled: int
    winners: list[dict[str, Any]]


class ReportOut(BaseModel):
    experiment: ExperimentListItem
    metrics: list[MetricPoint]
    labeling: LabelingSummary | None


class LabelingExperimentItem(BaseModel):
    experiment_id: int
    experiment_uuid: str
    name: str
    created_at: datetime
    total: int
    labeled: int


class LabelingTaskListItem(BaseModel):
    id: int
    task_uuid: str
    status: LabelStatus
    winner_name: str | None
    created_at: datetime
    labeled_at: datetime | None


class LabelingTaskItemOut(BaseModel):
    id: int
    variant_id: int
    variant_name: str
    variant_description: str | None
    workflow_id: str
    merged_output: str
    display_order: int


class LabelingTaskDetail(BaseModel):
    id: int
    task_uuid: str
    status: LabelStatus
    items: list[LabelingTaskItemOut]


class SubmitLabelRequest(BaseModel):
    selected_variant_id: int


class ValidateSchemaRequest(BaseModel):
    schema_doc: dict[str, Any]


class ValidateTemplateRequest(BaseModel):
    template: str | None


class OkResponse(BaseModel):
    ok: Literal[True] = True
