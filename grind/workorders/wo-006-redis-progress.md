# WO-006: Redis progress caching

## Scope
Store worker progress updates in Redis, return cached data from progress endpoint. Small.

## Files to read
- src/pylon/api/internal.py (lines 224-227: progress endpoint stub)
- src/pylon/config.py (line 6: redis_url)
- src/pylon/schemas.py (lines 137-141: ProgressUpdate schema)

## Key context

Current stub (internal.py lines 224-227):
```python
@router.post("/progress", dependencies=[Depends(verify_internal_key)])
async def progress_update(body: ProgressUpdate):
    # TODO: store in Redis for fast dashboard polling (not worth a DB write)
    return {"ok": True}
```

ProgressUpdate schema:
```python
class ProgressUpdate(BaseModel):
    pipeline_id: uuid.UUID
    phase: str
    progress: float
    message: str
```

Redis URL config:
```python
redis_url: str = "redis://localhost:6379/0"
```

## Changes
- [ ] src/pylon/redis.py (NEW): Redis client singleton, get/set helpers
- [ ] src/pylon/api/internal.py (lines 224-227): Replace stub with Redis SET
- [ ] src/pylon/main.py: Add GET `/api/progress/{pipeline_id}` for dashboard polling

## Proposed implementation

```python
# src/pylon/redis.py
import redis.asyncio as redis

from .config import settings

pool = redis.ConnectionPool.from_url(settings.redis_url)

async def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=pool)

async def set_progress(pipeline_id: str, data: dict, ttl: int = 120):
    import json
    r = await get_redis()
    await r.set(f"pylon:progress:{pipeline_id}", json.dumps(data), ex=ttl)

async def get_progress(pipeline_id: str) -> dict | None:
    import json
    r = await get_redis()
    raw = await r.get(f"pylon:progress:{pipeline_id}")
    return json.loads(raw) if raw else None
```

```python
# In internal.py, replace progress stub:
from ..redis import set_progress

@router.post("/progress", dependencies=[Depends(verify_internal_key)])
async def progress_update(body: ProgressUpdate):
    await set_progress(str(body.pipeline_id), {
        "phase": body.phase,
        "progress": body.progress,
        "message": body.message,
    })
    return {"ok": True}
```

```python
# In main.py, add read endpoint:
from .redis import get_progress

@app.get("/api/progress/{pipeline_id}")
async def get_pipeline_progress(pipeline_id: str):
    data = await get_progress(pipeline_id)
    return data or {"phase": None, "progress": 0, "message": ""}
```

## Decisions
- [x] RESOLVED: 120s TTL, stale progress auto-expires
- [x] RESOLVED: No DB write, Redis-only (matches original TODO comment)

## Tests
Requirements: integration (needs Redis)
Run: `pytest tests/test_redis.py`
- [ ] set_progress + get_progress round-trip
- [ ] TTL expiration clears key
- [ ] get_progress returns None for missing key

## Commit
```
feat(progress): store worker progress in Redis

Replace progress endpoint stub with Redis SET (120s TTL). Add GET
endpoint for dashboard polling.

- Add redis.py with connection pool and get/set helpers
- Progress endpoint writes to Redis instead of no-op
- GET /api/progress/{pipeline_id} returns cached progress
```

## Dependencies
blocked_by: none
blocks: none

## After commit
- Update status/PROGRESS.md: check "Progress updates stored in Redis for fast polling"
