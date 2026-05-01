# Polish

Nice-to-have, quality-of-life. Do after end-to-end loop works and daily use is stable.

## Dashboard UX

- [ ] "Accept All Recommendations" button on decision view
- [ ] Keyboard shortcuts for decision navigation (j/k/enter)
- [ ] Dark/light theme toggle
- [ ] Pipeline duration tracking and display
- [ ] Token usage tracking per phase/pipeline
- [ ] Estimated cost display

## Mobile

- [ ] Verify responsive layout works on phone for decision cards
- [ ] PWA manifest + service worker for home screen install
- [ ] Push notifications for pending decisions (if PWA)

## Observability

- [ ] Flower dashboard accessible from Pylon nav
- [ ] Worker logs viewable from dashboard
- [ ] Phase output/notes viewable from ticket detail
- [ ] Pipeline analytics (avg time per phase, decision response time)

## Developer experience

- [ ] Production Docker Compose variant
- [ ] One-command setup script (clone, env, migrate, seed, up)
- [ ] CLAUDE.md for the Pylon repo itself
- [ ] Contributing guide for Tanya/Michael

## Integrations

- [ ] GitHub PR status checks displayed in dashboard
- [ ] Asana comment with link to Pylon ticket detail
- [ ] Cross-repo ticket handling (linked pipelines, option 2 from OPEN-QUESTIONS)

## Performance

- [ ] Connection pooling tuning for Postgres
- [ ] Redis caching for dashboard queries
- [ ] Batch Asana API calls (reduce rate limit pressure)
