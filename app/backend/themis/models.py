from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import JSON, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def enum_values(enum_cls):
    return [item.value for item in enum_cls]


class ExperimentStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResponseMode(str, Enum):
    BLOCKING = "blocking"
    STREAMING = "streaming"


class VariantRole(str, Enum):
    CONTROL = "control"
    EXPERIMENT_A = "experiment_a"
    EXPERIMENT_B = "experiment_b"


class RunStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    DIFY_ERROR = "dify_error"
    SCHEMA_INVALID = "schema_invalid"


class LabelStatus(str, Enum):
    UNLABELED = "unlabeled"
    LABELED = "labeled"


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    response_mode: Mapped[ResponseMode] = mapped_column(SAEnum(ResponseMode, values_callable=enum_values), default=ResponseMode.BLOCKING)
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    preference_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ExperimentStatus] = mapped_column(SAEnum(ExperimentStatus, values_callable=enum_values), default=ExperimentStatus.NOT_STARTED)
    total_samples: Mapped[int] = mapped_column(Integer, default=0)
    executed_samples: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)

    variants: Mapped[list["ExperimentVariant"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan", order_by="ExperimentVariant.display_order"
    )
    samples: Mapped[list["ExperimentSample"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_experiments_status_created", "status", "created_at"),)


class ExperimentVariant(Base):
    __tablename__ = "experiment_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[VariantRole] = mapped_column(SAEnum(VariantRole, values_callable=enum_values), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(600), nullable=True)
    workflow_id: Mapped[str] = mapped_column(String(150), nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    merge_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now(), onupdate=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="variants")

    __table_args__ = (
        UniqueConstraint("experiment_id", "role", name="uq_variant_experiment_role"),
        Index("ix_variants_experiment_order", "experiment_id", "display_order"),
    )


class ExperimentSample(Base):
    __tablename__ = "experiment_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    sample_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="samples")
    runs: Mapped[list["VariantRun"]] = relationship(back_populates="sample", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("experiment_id", "sample_uuid", name="uq_sample_experiment_uuid"),
        Index("ix_samples_experiment_created", "experiment_id", "created_at"),
    )


class VariantRun(Base):
    __tablename__ = "variant_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    sample_id: Mapped[int] = mapped_column(ForeignKey("experiment_samples.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("experiment_variants.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus, values_callable=enum_values), default=RunStatus.PENDING)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_validation_error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())

    sample: Mapped[ExperimentSample] = relationship(back_populates="runs")
    variant: Mapped[ExperimentVariant] = relationship()

    __table_args__ = (
        UniqueConstraint("sample_id", "variant_id", name="uq_run_sample_variant"),
        Index("ix_runs_experiment_variant_status", "experiment_id", "variant_id", "status"),
        Index("ix_runs_experiment_variant_latency", "experiment_id", "variant_id", "latency_ms"),
    )


class LabelingTask(Base):
    __tablename__ = "labeling_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    sample_id: Mapped[int] = mapped_column(ForeignKey("experiment_samples.id", ondelete="CASCADE"), nullable=False)
    task_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    status: Mapped[LabelStatus] = mapped_column(SAEnum(LabelStatus, values_callable=enum_values), default=LabelStatus.UNLABELED)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)

    items: Mapped[list["LabelingTaskItem"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="LabelingTaskItem.display_order"
    )
    result: Mapped["LabelingResult | None"] = relationship(back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("experiment_id", "sample_id", name="uq_label_task_experiment_sample"),
        Index("ix_label_tasks_experiment_status", "experiment_id", "status"),
    )


class LabelingTaskItem(Base):
    __tablename__ = "labeling_task_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("labeling_tasks.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("experiment_variants.id", ondelete="CASCADE"), nullable=False)
    merged_output: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    task: Mapped[LabelingTask] = relationship(back_populates="items")
    variant: Mapped[ExperimentVariant] = relationship()

    __table_args__ = (UniqueConstraint("task_id", "variant_id", name="uq_label_item_task_variant"),)


class LabelingResult(Base):
    __tablename__ = "labeling_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("labeling_tasks.id", ondelete="CASCADE"), unique=True)
    selected_variant_id: Mapped[int] = mapped_column(ForeignKey("experiment_variants.id", ondelete="CASCADE"))
    labeled_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), server_default=func.now())

    task: Mapped[LabelingTask] = relationship(back_populates="result")
    selected_variant: Mapped[ExperimentVariant] = relationship()
