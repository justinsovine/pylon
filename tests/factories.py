import uuid
from datetime import datetime

from src.pylon.models import (
    Answer,
    Decision,
    DecisionRound,
    PhaseRun,
    Pipeline,
    Ticket,
    WorkerSession,
)


def make_ticket(**overrides) -> Ticket:
    defaults = {
        "id": uuid.uuid4(),
        "asana_gid": f"asana-{uuid.uuid4().hex[:8]}",
        "slug": f"test-ticket-{uuid.uuid4().hex[:8]}",
        "title": "Test Ticket",
        "repo": "onboard",
        "assignee": "justin",
    }
    defaults.update(overrides)
    return Ticket(**defaults)


def make_pipeline(ticket: Ticket, **overrides) -> Pipeline:
    defaults = {
        "id": uuid.uuid4(),
        "ticket_id": ticket.id,
        "status": "queued",
        "notes_path": f"notes/{ticket.slug}",
        "branch_name": f"feature/{ticket.slug}",
    }
    defaults.update(overrides)
    return Pipeline(**defaults)


def make_phase_run(pipeline: Pipeline, **overrides) -> PhaseRun:
    defaults = {
        "id": uuid.uuid4(),
        "pipeline_id": pipeline.id,
        "phase": "investigate",
        "status": "pending",
    }
    defaults.update(overrides)
    return PhaseRun(**defaults)


def make_decision_round(phase_run: PhaseRun, **overrides) -> DecisionRound:
    defaults = {
        "id": uuid.uuid4(),
        "phase_run_id": phase_run.id,
        "round_number": 1,
        "status": "awaiting",
        "emitted_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    return DecisionRound(**defaults)


def make_decision(round_: DecisionRound, **overrides) -> Decision:
    defaults = {
        "id": uuid.uuid4(),
        "round_id": round_.id,
        "decision_key": f"d{uuid.uuid4().hex[:3]}",
        "question": "Which approach?",
        "options": [
            {"key": "A", "label": "Option A", "tradeoff": "Simple"},
            {"key": "B", "label": "Option B", "tradeoff": "Complex"},
        ],
        "recommendation": "A",
        "recommendation_why": "Simpler.",
    }
    defaults.update(overrides)
    return Decision(**defaults)
