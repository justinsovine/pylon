import uuid
from datetime import datetime

from pydantic import BaseModel


class TicketBase(BaseModel):
    asana_gid: str
    slug: str
    title: str
    description: str | None = None
    assignee: str | None = None
    repo: str
    priority: str | None = None


class TicketOut(TicketBase):
    id: uuid.UUID
    synced_at: datetime
    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    asana_gid: str
    repo: str
    assignee: str | None = None


class PipelineOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    status: str
    current_phase: str | None
    branch_name: str | None
    notes_path: str | None
    pr_url: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    ticket: TicketOut | None = None
    pending_decisions: int = 0
    model_config = {"from_attributes": True}


class DecisionOption(BaseModel):
    key: str
    label: str
    tradeoff: str


class DecisionOut(BaseModel):
    id: uuid.UUID
    decision_key: str
    question: str
    context: str | None
    options: list[DecisionOption]
    recommendation: str | None
    recommendation_why: str | None
    depends_on: str | None
    answer: "AnswerOut | None" = None
    model_config = {"from_attributes": True}


class DecisionRoundOut(BaseModel):
    id: uuid.UUID
    round_number: int
    status: str
    emitted_at: datetime | None
    answered_at: datetime | None
    decisions: list[DecisionOut] = []
    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    decision_id: uuid.UUID
    choice: str
    note: str | None = None


class AnswerBatchSubmit(BaseModel):
    answers: list[AnswerSubmit]
    answered_by: str


class AnswerOut(BaseModel):
    id: uuid.UUID
    choice: str
    note: str | None
    answered_by: str
    source: str
    answered_at: datetime
    model_config = {"from_attributes": True}


class WorkerSessionOut(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    phase: str
    pid: int | None
    account: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    timeout_seconds: int
    exit_code: int | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PhaseStarted(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    worker_id: uuid.UUID | None = None


class DecisionsEmitted(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    round_number: int
    decisions: list[dict]


class PhaseCompleted(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    result: dict


class PhaseFailed(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    error: str
    retry_safe: bool = False


class ProgressUpdate(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    progress: float
    message: str


class ActivityEntry(BaseModel):
    timestamp: datetime
    event_type: str
    pipeline_id: uuid.UUID
    ticket_slug: str
    assignee: str | None
    message: str
