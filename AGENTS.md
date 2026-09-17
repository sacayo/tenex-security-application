# AGENTS.md

## What this repo is

Prototype: upload web-log files in NSS output format → parse → rule-based anomaly
detection → human-readable timeline. **`spec.md` is the design source of
truth** (architecture, API contract, data model, detection rules, build
order). Read it before touching backend code.

## Layout

- `app/` — FastAPI backend (Python). `main.py` = wiring/entry point,
  `routes.py` = HTTP layer, `service/` = pure business logic (parsing,
  detection, timeline), `data/` = SQLAlchemy persistence, `model/` =
  Pydantic schemas.
- `web/` — Next.js + TypeScript + Tailwind frontend.
- `tests/` — pytest, at root. Fixture: `tests/fixtures/sample_nss_web.json`.
- Root: `pyproject.toml` / `uv.lock` (Python 3.11, uv-managed), and the
  user-authored `docker-compose.yml` + `Dockerfile`s.

## Division of labor (read first)

- **`app/`, `tests/`, `docker-compose.yml`, `Dockerfile`s are user-written
  learning code.** Guide, review, explain, debug — do NOT implement backend
  logic unless the user explicitly asks. Stub files intentionally
  `raise NotImplementedError` with TODO guidance; do not "fix" them.
- **`web/` is agent-maintained.** Full changes are fine there.
- The API contract is a three-way sync: change `spec.md` §5 ⇔ backend
  routes ⇔ `web/lib/api.ts` + `web/lib/types.ts` together, never just one.

## Commands

Run from repo root unless noted:

- `uv sync` / `uv add <pkg>` — dependencies (uv only; never pip/poetry)
- `uv run fastapi dev app/main.py` — backend dev server (:8000)
- `uv run pytest` — tests (skipped tests are the user's TODO checklist;
  don't remove their skip markers)
- `uv run ruff check .` / `uv run ruff format .` — lint/format (no config
  file; defaults are the convention)
- `cd web && npm install && npm run dev` — frontend (:3000);
  `npm run build` = frontend verification gate

## Gotchas

- No CI / pre-commit / ruff or pytest config — verification is the commands
  above, run locally.
- SQLAlchemy is deliberately NOT a dependency yet; the user adds it during
  the build (`uv add sqlalchemy "psycopg[binary]"`). `app/data/` stubs must
  not import sqlalchemy until then.
- Keep `app/service/` pure Python (no FastAPI/sqlalchemy imports) — that
  layering is the point of the exercise.
- No auth anywhere by design (local single-user prototype); don't add it
  without being asked.
