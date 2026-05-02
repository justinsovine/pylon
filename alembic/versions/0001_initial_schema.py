"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("asana_gid", sa.Text(), nullable=False, unique=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee", sa.Text(), nullable=True),
        sa.Column("repo", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_tickets_assignee", "tickets", ["assignee"])
    op.create_index("idx_tickets_repo", "tickets", ["repo"])

    op.create_table(
        "worker_sessions",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("account", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="starting"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("error_output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_worker_sessions_status", "worker_sessions", ["status"])

    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "ticket_id",
            postgresql.UUID(),
            sa.ForeignKey("tickets.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("current_phase", sa.Text(), nullable=True),
        sa.Column("branch_name", sa.Text(), nullable=True),
        sa.Column("notes_path", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_pipelines_status", "pipelines", ["status"])

    op.create_foreign_key(
        "fk_worker_sessions_pipeline",
        "worker_sessions",
        "pipelines",
        ["pipeline_id"],
        ["id"],
    )

    op.create_table(
        "phase_runs",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(),
            sa.ForeignKey("pipelines.id"),
            nullable=False,
        ),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("pass_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "worker_id",
            postgresql.UUID(),
            sa.ForeignKey("worker_sessions.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_phase_runs_pipeline", "phase_runs", ["pipeline_id", "phase"])

    op.create_table(
        "decision_rounds",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "phase_run_id",
            postgresql.UUID(),
            sa.ForeignKey("phase_runs.id"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("emitted_at", sa.DateTime(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "round_id",
            postgresql.UUID(),
            sa.ForeignKey("decision_rounds.id"),
            nullable=False,
        ),
        sa.Column("decision_key", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("recommendation_why", sa.Text(), nullable=True),
        sa.Column("depends_on", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("round_id", "decision_key"),
    )
    op.create_index("idx_decisions_round", "decisions", ["round_id"])

    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "decision_id",
            postgresql.UUID(),
            sa.ForeignKey("decisions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("choice", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="dashboard"),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_answers_decision", "answers", ["decision_id"])


def downgrade() -> None:
    op.drop_table("answers")
    op.drop_table("decisions")
    op.drop_table("decision_rounds")
    op.drop_table("phase_runs")
    op.drop_constraint("fk_worker_sessions_pipeline", "worker_sessions", type_="foreignkey")
    op.drop_table("pipelines")
    op.drop_table("worker_sessions")
    op.drop_table("tickets")
