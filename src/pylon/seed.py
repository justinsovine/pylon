"""Seed development database with sample data."""
import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session, engine
from .models import (
    Answer,
    Base,
    Decision,
    DecisionRound,
    PhaseRun,
    Pipeline,
    Ticket,
    WorkerSession,
)

TICKET_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PIPELINE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PHASE_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
ROUND_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
DECISION_1_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")
DECISION_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000006")
WORKER_ID = uuid.UUID("00000000-0000-0000-0000-000000000007")

NOW = datetime.utcnow()


async def seed(session: AsyncSession) -> None:
    existing = await session.execute(select(Ticket).where(Ticket.id == TICKET_ID))
    if existing.scalar_one_or_none():
        print("Seed data already exists, skipping.")
        return

    ticket = Ticket(
        id=TICKET_ID,
        asana_gid="1234567890123456",
        slug="fix-invoice-pdf-alignment",
        title="Fix invoice PDF alignment on multi-page documents",
        description=(
            "When an invoice spans multiple pages, the header columns "
            "on page 2+ are misaligned by ~10px. Reproducible on all "
            "environments."
        ),
        assignee="justin",
        repo="esign",
        priority="high",
        synced_at=NOW,
        created_at=NOW - timedelta(hours=2),
    )

    pipeline = Pipeline(
        id=PIPELINE_ID,
        ticket_id=TICKET_ID,
        status="waiting_on_decision",
        current_phase="investigate",
        branch_name="pylon/fix-invoice-pdf-alignment",
        started_at=NOW - timedelta(hours=1),
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW - timedelta(minutes=10),
    )

    worker = WorkerSession(
        id=WORKER_ID,
        pipeline_id=PIPELINE_ID,
        phase="investigate",
        pid=12345,
        account="default",
        status="waiting",
        started_at=NOW - timedelta(hours=1),
        timeout_seconds=1200,
        created_at=NOW - timedelta(hours=1),
    )

    phase_run = PhaseRun(
        id=PHASE_RUN_ID,
        pipeline_id=PIPELINE_ID,
        phase="investigate",
        pass_number=1,
        status="waiting_on_decision",
        started_at=NOW - timedelta(hours=1),
        worker_id=WORKER_ID,
        created_at=NOW - timedelta(hours=1),
    )

    decision_round = DecisionRound(
        id=ROUND_ID,
        phase_run_id=PHASE_RUN_ID,
        round_number=1,
        status="pending",
        emitted_at=NOW - timedelta(minutes=10),
        created_at=NOW - timedelta(minutes=10),
    )

    decision_1 = Decision(
        id=DECISION_1_ID,
        round_id=ROUND_ID,
        decision_key="scope",
        question="Should the fix also address the footer alignment issue found during investigation?",
        context="Footer has a similar 5px offset but was not mentioned in the ticket.",
        options=[
            {"key": "fix_both", "label": "Fix header and footer alignment together", "tradeoff": "Larger PR, but fixes both issues in one pass"},
            {"key": "header_only", "label": "Fix header only, create separate ticket for footer", "tradeoff": "Smaller blast radius, easier to review"},
        ],
        recommendation="header_only",
        recommendation_why="Smaller blast radius, easier to review.",
        created_at=NOW - timedelta(minutes=10),
    )

    decision_2 = Decision(
        id=DECISION_2_ID,
        round_id=ROUND_ID,
        decision_key="approach",
        question="Which PDF rendering approach should be used?",
        context="Current code uses inline styles. Could switch to CSS classes.",
        options=[
            {"key": "inline", "label": "Keep inline styles, fix the calculation", "tradeoff": "Less risk, consistent with existing codebase style"},
            {"key": "css_classes", "label": "Refactor to CSS classes with proper page-break handling", "tradeoff": "Cleaner long-term, but larger diff and more testing needed"},
        ],
        recommendation="inline",
        recommendation_why="Less risk, consistent with existing codebase style.",
        depends_on="scope",
        created_at=NOW - timedelta(minutes=10),
    )

    session.add_all([ticket, pipeline, worker, phase_run, decision_round, decision_1, decision_2])
    await session.commit()
    print("Seed data created:")
    print(f"  Ticket: {ticket.slug}")
    print(f"  Pipeline: {pipeline.status} @ {pipeline.current_phase}")
    print(f"  Decisions: 2 pending")


async def main() -> None:
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
