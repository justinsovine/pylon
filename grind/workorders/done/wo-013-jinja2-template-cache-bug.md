---
id: wo-013
title: Fix Jinja2 template cache unhashable dict bug
type: bugfix
est: small
blocked_by: none
---

## Problem

Board route (`GET /`) throws `TypeError: unhashable type: 'dict'` on every request. Starlette 1.0.0 passes `globals` dict to `jinja2.Environment.get_template(name, globals)`, which Jinja2 3.1.6 tries to use as an LRUCache key. Dicts aren't hashable, so cache lookup explodes.

Traceback path:
```
main.py:31 board() -> templates.TemplateResponse("board.html", ...)
  -> starlette/templating.py:115 get_template(name)
  -> jinja2/environment.py:964 _load_template(name, globals)
  -> jinja2/utils.py:515 LRUCache.__getitem__ -- TypeError
```

## Root Cause

Jinja2 3.1.6 is latest available (no 3.1.7+). Starlette 1.0.0 (bundled with FastAPI 0.115+) assumes the cache can handle the globals tuple key. Version incompatibility with no upstream fix yet.

## Fix Options

**Option A (recommended):** Disable Jinja2 template cache by setting `auto_reload=True` or `cache_size=0` on the Jinja2 Environment. Minimal perf impact for dev tool with few templates.

**Option B:** Pin `fastapi<0.115` / `starlette<1.0` to get old TemplateResponse behavior. Downsides: loses other fixes, delays inevitable.

**Option C:** Subclass `Jinja2Templates` to override `get_template` and strip globals before cache lookup. More surgical but couples to Starlette internals.

## Implementation (Option A)

File: `src/pylon/main.py`

Find the `Jinja2Templates` instantiation and configure the environment:

```python
templates = Jinja2Templates(directory="src/pylon/templates")
templates.env.cache = None  # disable LRUCache, bypasses unhashable key bug
```

Or equivalently:
```python
templates = Jinja2Templates(directory="src/pylon/templates")
templates.env.auto_reload = True  # forces recompile, skips cache lookup
```

## Verify

```bash
curl -s http://localhost:8001/ | grep -q "Loading board" && echo "OK"
curl -s http://localhost:8001/partials/board | grep -q "flex-shrink" && echo "OK"
```

## Context Snapshot

```python
# src/pylon/main.py:20
templates = Jinja2Templates(directory=str(templates_dir))
```

Versions in container: Jinja2 3.1.6, Starlette 1.0.0, FastAPI (whatever pulls Starlette 1.0).
