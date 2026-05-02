# WO-002: Decision card partial

## Scope
Decision cards with radio buttons, notes, batch submit via HTMX. Medium.

## Files to read
- src/pylon/templates/decisions.html (full file, small: HTMX shell)
- src/pylon/api/decisions.py (full file: pending query, round fetch, answer submit)
- src/pylon/schemas.py (lines 46-83: DecisionOption, DecisionOut, DecisionRoundOut, AnswerSubmit, AnswerBatchSubmit)
- src/pylon/models.py (lines 77-128: DecisionRound, Decision, Answer)
- src/pylon/main.py (need to add /partials/decisions/{slug} route)

## Key context

Decisions shell (decisions.html lines 4-9):
```html
<div class="max-w-3xl mx-auto">
    <h1 class="text-2xl font-semibold mb-6">{{ slug }}</h1>
    <div id="decisions-container" hx-get="/partials/decisions/{{ slug }}" hx-trigger="load" hx-swap="innerHTML">
```

Answer submit endpoint (decisions.py lines 56-122):
```python
@router.post("/rounds/{round_id}/answers")
async def submit_answers(round_id: uuid.UUID, body: AnswerBatchSubmit, db: AsyncSession = Depends(get_db)):
    # Creates Answer rows, marks round "answered", dispatches run_phase
```

AnswerBatchSubmit schema:
```python
class AnswerBatchSubmit(BaseModel):
    answers: list[AnswerSubmit]
    answered_by: str

class AnswerSubmit(BaseModel):
    decision_id: uuid.UUID
    choice: str
    note: str | None = None
```

DecisionOption schema:
```python
class DecisionOption(BaseModel):
    key: str
    label: str
    tradeoff: str
```

BUILDPLAN decision card layout shows: question, context, radio options with recommendation star, notes field, batch submit button.

## Changes
- [ ] src/pylon/main.py: Add `/partials/decisions/{slug}` route
- [ ] src/pylon/templates/partials/decisions.html (NEW): Decision cards with form
- [ ] src/pylon/templates/decisions.html: Add assignee dropdown for answered_by

## Proposed implementation

```python
# In main.py:
@app.get("/partials/decisions/{slug}", response_class=HTMLResponse)
async def decisions_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    ticket = (await db.execute(
        select(Ticket).where(Ticket.slug == slug)
    )).scalar_one_or_none()
    if not ticket or not ticket.pipeline:
        return HTMLResponse("<p class='text-gray-500'>No pipeline found.</p>")

    pipeline = (await db.execute(
        select(Pipeline)
        .where(Pipeline.ticket_id == ticket.id)
        .options(
            selectinload(Pipeline.phase_runs)
            .selectinload(PhaseRun.decision_rounds)
            .selectinload(DecisionRound.decisions)
            .selectinload(Decision.answer)
        )
    )).scalar_one()

    # Find first awaiting round
    awaiting_round = None
    for pr in pipeline.phase_runs:
        for dr in pr.decision_rounds:
            if dr.status == "awaiting":
                awaiting_round = dr
                break

    return templates.TemplateResponse("partials/decisions.html", {
        "request": request,
        "pipeline": pipeline,
        "round": awaiting_round,
        "phase": awaiting_round and next(
            (pr.phase for pr in pipeline.phase_runs
             for dr in pr.decision_rounds if dr.id == awaiting_round.id),
            None
        ),
    })
```

Template: form with radio buttons per decision, notes textarea, submit via HTMX POST to /api/decisions/rounds/{round_id}/answers.

```html
<!-- partials/decisions.html -->
{% if not round %}
<p class="text-gray-500">No pending decisions.</p>
{% else %}
<div class="text-sm text-gray-400 mb-4">
    {{ phase|title }} — Round {{ round.round_number }} — {{ round.decisions|length }} decisions
</div>
<form hx-post="/api/decisions/rounds/{{ round.id }}/answers"
      hx-headers='{"Content-Type": "application/json"}'
      hx-vals='js:{
        answered_by: document.getElementById("answered-by").value,
        answers: [...document.querySelectorAll("[data-decision-id]")].map(el => ({
            decision_id: el.dataset.decisionId,
            choice: el.querySelector("input[type=radio]:checked")?.value || "",
            note: el.querySelector("textarea")?.value || null
        }))
      }'
      hx-swap="innerHTML" hx-target="#decisions-container">

    <select id="answered-by" class="mb-4 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
        <option value="justin">justin</option>
        <option value="tanya">tanya</option>
        <option value="michael">michael</option>
    </select>

    {% for d in round.decisions %}
    <div class="bg-gray-900 rounded-lg p-4 mb-4 border border-gray-700" data-decision-id="{{ d.id }}">
        <h3 class="font-medium text-white mb-2">{{ loop.index }}. {{ d.question }}</h3>
        {% if d.context %}
        <p class="text-sm text-gray-400 mb-3">{{ d.context }}</p>
        {% endif %}
        {% for opt in d.options %}
        <label class="flex items-start gap-3 p-2 rounded hover:bg-gray-800 cursor-pointer mb-1">
            <input type="radio" name="choice-{{ d.id }}" value="{{ opt.key }}"
                   class="mt-0.5" {% if opt.key == d.recommendation %}checked{% endif %}>
            <div>
                <span class="text-sm text-white">{{ opt.key }}: {{ opt.label }}</span>
                {% if opt.key == d.recommendation %}
                <span class="text-xs text-amber-400 ml-1">recommended</span>
                {% endif %}
                <div class="text-xs text-gray-500">{{ opt.tradeoff }}</div>
            </div>
        </label>
        {% endfor %}
        <textarea placeholder="Notes (optional)"
                  class="mt-2 w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 resize-none"
                  rows="2"></textarea>
    </div>
    {% endfor %}

    <button type="submit"
            class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-medium">
        Submit {{ round.decisions|length }} answers
    </button>
</form>
{% endif %}
```

## Decisions
- [x] RESOLVED: Batch submit all decisions in a round at once (matches existing API contract)
- [x] RESOLVED: No auth, use dropdown for answered_by (Decision 3, Option B)
- [x] RESOLVED: Pre-select recommended option

## Tests
Requirements: manual
Run: `just dev`, need seed data with pending decisions
- [ ] Decision cards render with question, context, options
- [ ] Radio buttons work, recommendation pre-selected
- [ ] Submit sends correct payload to API
- [ ] After submit, page shows "No pending decisions"
- [ ] Notes field included in submission

## Commit
```
feat(dashboard): add decision card partial with answer form

Decisions partial renders pending decision rounds with radio buttons,
recommendation highlighting, notes field, and batch submit via HTMX.

- Register /partials/decisions/{slug} route
- Create partials/decisions.html with form and hx-post
- Answered_by via dropdown (no auth, 3 hardcoded devs)
- Pre-select recommended option on each decision card
```

## Dependencies
blocked_by: wo-001
blocks: none

## After commit
- Update status/PROGRESS.md: check "Decision card partial with radio buttons and submit"
