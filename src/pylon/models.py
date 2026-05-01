import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asana_gid: Mapped[str] = mapped_column(Text, unique=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    assignee: Mapped[str | None] = mapped_column(Text)
    repo: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    pipeline: Mapped["Pipeline | None"] = relationship(back_populates="ticket")

    __table_args__ = (
        Index("idx_tickets_assignee", "assignee"),
        Index("idx_tickets_repo", "repo"),
    )


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"), unique=True)
    status: Mapped[str] = mapped_column(Text, default="queued")
    current_phase: Mapped[str | None] = mapped_column(Text)
    branch_name: Mapped[str | None] = mapped_column(Text)
    notes_path: Mapped[str | None] = mapped_column(Text)
    pr_url: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="pipeline")
    phase_runs: Mapped[list["PhaseRun"]] = relationship(back_populates="pipeline")
    worker_sessions: Mapped[list["WorkerSession"]] = relationship(back_populates="pipeline")

    __table_args__ = (Index("idx_pipelines_status", "status"),)


class PhaseRun(Base):
    __tablename__ = "phase_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipelines.id"))
    phase: Mapped[str] = mapped_column(Text)
    pass_number: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(Text, default="pending")
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("worker_sessions.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    pipeline: Mapped[Pipeline] = relationship(back_populates="phase_runs")
    decision_rounds: Mapped[list["DecisionRound"]] = relationship(back_populates="phase_run")

    __table_args__ = (Index("idx_phase_runs_pipeline", "pipeline_id", "phase"),)


class DecisionRound(Base):
    __tablename__ = "decision_rounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    phase_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("phase_runs.id"))
    round_number: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(Text, default="pending")
    emitted_at: Mapped[datetime | None] = mapped_column()
    answered_at: Mapped[datetime | None] = mapped_column()
    applied_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    phase_run: Mapped[PhaseRun] = relationship(back_populates="decision_rounds")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="round")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decision_rounds.id"))
    decision_key: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSONB)
    recommendation: Mapped[str | None] = mapped_column(Text)
    recommendation_why: Mapped[str | None] = mapped_column(Text)
    depends_on: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    round: Mapped[DecisionRound] = relationship(back_populates="decisions")
    answer: Mapped["Answer | None"] = relationship(back_populates="decision")

    __table_args__ = (
        UniqueConstraint("round_id", "decision_key"),
        Index("idx_decisions_round", "round_id"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decisions.id"), unique=True)
    choice: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="dashboard")
    answered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    decision: Mapped[Decision] = relationship(back_populates="answer")

    __table_args__ = (Index("idx_answers_decision", "decision_id"),)


class WorkerSession(Base):
    __tablename__ = "worker_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipelines.id"))
    phase: Mapped[str] = mapped_column(Text)
    pid: Mapped[int | None] = mapped_column()
    account: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="starting")
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    timeout_seconds: Mapped[int] = mapped_column(default=1800)
    exit_code: Mapped[int | None] = mapped_column()
    error_output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    pipeline: Mapped[Pipeline] = relationship(back_populates="worker_sessions")

    __table_args__ = (Index("idx_worker_sessions_status", "status"),)
