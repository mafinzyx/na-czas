# Instructions for AI coding agents

"Na czas" is a commute planner: FastAPI + SQLite in `backend/`, React + TypeScript in
`frontend/`. It is a recruitment MVP, so clarity matters more than features.

## Commands

```bash
# backend (from backend/, with the virtualenv active)
uvicorn app.main:app --reload     # API on :8000
pytest                            # must pass before a change is done

# frontend (from frontend/)
npm run dev                       # UI on :5173
npm run build                     # type-check + build, must pass
npm run lint                      # must report no warnings
```

## Architecture rules

- **Routers stay thin.** `app/routers/` only validates input, calls a service and maps
  errors to HTTP status codes. No calculations there.
- **`services/planner.py` is pure.** No database, no network, no `datetime.now()`. Everything
  it needs arrives in `TripContext`. This is what keeps it unit-testable.
- **`services/journey.py` is the only place that gathers external data for a journey.** It
  queries the providers in parallel and hands the results to the planner.
- **External services must never break the app.** Transitous, BRouter, OSRM, Open-Meteo,
  Nominatim and the LLM each have a fallback (estimated transit, straight-line route, no
  weather, 502 for search, rule-based advice). Any new external call needs a timeout, a
  `User-Agent` from settings and a fallback too.
- **Only free, key-less data sources.** A reviewer must be able to run the project with no
  configuration. An API key may only ever unlock an optional extra.
- **The LLM describes, it does not calculate.** Numbers come from the planner. The model
  only receives the finished plan as JSON.
- **The API returns codes, the UI translates.** Warnings, tags and statuses are identifiers
  such as `rush_hour`; user-facing text lives in `frontend/src/i18n/`.
- **Model assumptions are named constants** at the top of `planner.py` and `traffic.py`,
  each with a comment saying what it means. No magic numbers inside functions.
- **Route shapes are sent only where a map shows them.** `/api/plan/journey` includes
  geometry, the week overview strips it.

## Conventions

- Backend: type hints everywhere, Pydantic models for every request and response,
  SQLAlchemy 2 style (`Mapped`, `select`).
- Frontend: function components, server state only through the hooks in `src/api/hooks.ts`
  (TanStack Query), no `any`, no enums (`erasableSyntaxOnly` is on).
- Every user-facing string goes through `t()` and must exist in both `en.ts` and `pl.ts`.
  `pl.ts` is typed against the keys of `en.ts`, so a missing key fails the build.
- Times are local and timezone-naive end to end. Timetables arrive in UTC and are converted
  once, in `services/transit.py`.
- Comments explain why, not what.

## When changing the planning model

1. Change or add the constant, with a comment.
2. Add or update a test in `backend/tests/test_planner.py` that states the expected
   behaviour in its name.
3. Check the result in the UI with the demo data, not only in tests.

## Out of scope

Authentication, multiple users, live vehicle positions and live traffic are deliberately
left out. Do not add them without being asked.
