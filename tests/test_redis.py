import asyncio

import pytest

from pylon.redis import get_progress, set_progress


@pytest.fixture
def pipeline_id():
    return "test-pipeline-001"


async def test_set_and_get_progress(pipeline_id):
    data = {"phase": "implement", "progress": 0.5, "message": "halfway"}
    await set_progress(pipeline_id, data)
    result = await get_progress(pipeline_id)
    assert result == data


async def test_get_progress_missing_key():
    result = await get_progress("nonexistent-pipeline-xyz")
    assert result is None


async def test_ttl_expiration(pipeline_id):
    data = {"phase": "test", "progress": 1.0, "message": "done"}
    await set_progress(pipeline_id, data, ttl=1)
    await asyncio.sleep(1.1)
    result = await get_progress(pipeline_id)
    assert result is None
