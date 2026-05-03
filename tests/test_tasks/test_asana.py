from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.pylon.models import Pipeline, Ticket
from src.pylon.tasks.asana import _poll_asana
from tests.factories import make_ticket

MOD = "src.pylon.tasks.asana"


async def test_poll_asana_creates_ticket_and_pipeline(db, setup_db):
    fake_tasks = [
        {
            "gid": "asana-new-1",
            "name": "Build login page",
            "notes": "Implement OAuth",
            "assignee": {"name": "Justin"},
            "custom_fields": [
                {"name": "repo", "text_value": "onboard"},
                {"name": "priority", "enum_value": {"name": "high"}},
            ],
        }
    ]

    factory = async_sessionmaker(setup_db, class_=AsyncSession, expire_on_commit=False)
    mock_client = AsyncMock()
    mock_client.get_section_tasks.return_value = fake_tasks

    with (
        patch(f"{MOD}.async_session", factory),
        patch(f"{MOD}.AsanaClient", return_value=mock_client),
        patch(f"{MOD}.settings") as mock_settings,
        patch("src.pylon.tasks.pipeline.run_phase"),
    ):
        mock_settings.asana_token = "fake"
        mock_settings.asana_ready_section_gid = "section-1"
        result = await _poll_asana()

    assert result["created"] == 1
    assert result["polled"] == 1
    assert result["skipped"] == 0

    async with factory() as session:
        tickets = (await session.execute(select(Ticket))).scalars().all()
        assert len(tickets) == 1
        assert tickets[0].asana_gid == "asana-new-1"
        assert tickets[0].title == "Build login page"
        assert tickets[0].repo == "onboard"

        pipelines = (await session.execute(select(Pipeline))).scalars().all()
        assert len(pipelines) == 1
        assert pipelines[0].status == "queued"


async def test_poll_asana_skips_existing_tickets(db, setup_db):
    existing = make_ticket(asana_gid="asana-existing")
    db.add(existing)
    await db.commit()

    fake_tasks = [
        {
            "gid": "asana-existing",
            "name": "Old task",
            "notes": "",
            "assignee": None,
            "custom_fields": [],
        },
        {
            "gid": "asana-new-2",
            "name": "New task",
            "notes": "Do stuff",
            "assignee": None,
            "custom_fields": [],
        },
    ]

    factory = async_sessionmaker(setup_db, class_=AsyncSession, expire_on_commit=False)
    mock_client = AsyncMock()
    mock_client.get_section_tasks.return_value = fake_tasks

    with (
        patch(f"{MOD}.async_session", factory),
        patch(f"{MOD}.AsanaClient", return_value=mock_client),
        patch(f"{MOD}.settings") as mock_settings,
        patch("src.pylon.tasks.pipeline.run_phase"),
    ):
        mock_settings.asana_token = "fake"
        mock_settings.asana_ready_section_gid = "section-1"
        result = await _poll_asana()

    assert result["created"] == 1
    assert result["skipped"] == 1
