# Security Anomaly API

> Upload a Zscaler **NSS web-log** file, get back a clear timeline of events and a
> ranked list of suspicious activity — with an optional AI-written brief that
> explains what happened in plain English.

A full-stack prototype: a FastAPI backend that parses and normalizes web-proxy
logs, flags anomalies with transparent rule-based detection, and serves a
Next.js dashboard. It ships as a one-command Docker Compose stack, runs happily
without a GPU or an LLM, and treats every detection as explainable and testable.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-119%20passing-brightgreen">
</p>

---

## Table of contents

- [What it does](#what-it-does)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Local deployment](#local-deployment)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Detection rules](#detection-rules)
- [LLM narrative layer](#llm-narrative-layer)
- [Project structure](#project-structure)
- [Testing & quality](#testing--quality)
- [Security & operational notes](#security--operational-notes)
- [Design decisions](#design-decisions)
- [Author](#author)

---

## What it does

Security teams drown in proxy logs. The signal — a malware download, a DLP
violation, a host beaconing out at 3 a.m. — is buried in thousands of rows of
JSON. This project turns one log file into an answer a non-specialist can act on:

1. **Upload** a file in the browser.
2. The backend **parses** it (JSON array, NDJSON, or delimited CSV/TSV), maps it
   to a canonical schema, and **runs 8 deterministic detection rules**.
3. Everything is persisted to PostgreSQL, and the dashboard renders a **bucketed
   timeline, stat cards, an anomaly list, and a filterable events table**.
4. Optionally, an **LLM writes a short brief** from the pre-computed findings —
   it never sees raw logs, and it is not allowed to invent facts.

It supports exactly one input format, done well: Zscaler Nanolog Streaming
Service (NSS) *"Feed Output Format: Web Logs"*.

---

## Features

- **Multi-format parsing** — content-sniffed, not extension-driven: JSON array,
  single JSON object, NDJSON, and the 34-column delimited (CSV/TSV/pipe) feed,
  with or without a header row.
- **8 explainable detection rules** — 6 stateless (threat, high risk score,
  suspicious category, DLP, large upload, off-hours) and 2 aggregate (repeated
  blocks, request burst). Each rule is a small pure function.
- **Full-window timeline** — the observed range is split into "nice" buckets
  (1m/5m/15m/1h/6h/1d) and quiet gaps become zero-count buckets, so the chart's
  x-axis shows the real time window instead of only busy ticks.
- **Filterable events table** — paginate and filter by action, URL category, or
  "flagged by a rule only".
- **Optional AI brief** — schema-constrained, grounding-checked, cached per
  upload, with server-side risk scoring. Off by default (`LLM_ENABLED=false`).
- **One-command deployment** — `docker compose up --build` gives you the UI, API,
  and database.
- **Strong operational hygiene** — per-request `X-Request-ID`, structured stdlib
  logging, healthchecks, and PII-conscious logging.

---

## Architecture

![System architecture](docs/architecture.png)

The system has **three deployable units** and a clean layering rule:

| Layer | Files | May import | Must **not** import |
|---|---|---|---|
| Entry point | `app/main.py` | `routes` | service/data internals |
| HTTP | `app/routes.py` | `service`, `data.repository`, `llm`, `model` | raw SQLAlchemy, parsing internals |
| Logic | `app/service/*` | `model` | FastAPI, SQLAlchemy, httpx (kept pure) |
| LLM edge | `app/llm/*` | httpx, `service.narrative`, `service.timeline`, `data.repository`, `model` | FastAPI |
| Persistence | `app/data/*` | SQLAlchemy, `model` | FastAPI |
| Schemas | `app/model/*` | Pydantic | anything else |

`app/service/` is **pure Python** — no web framework, no database, no network —
so the interesting logic (parsing, detection, timeline, prompt building) is
trivially unit-testable. `app/data/` and `app/llm/` are the only impure edges.

### Upload request lifecycle

```mermaid
sequenceDiagram
    actor U as User
    participant W as Next.js (web/)
    participant R as app/routes.py
    participant P as service/parsing.py
    participant D as service/detection.py
    participant DB as PostgreSQL
    participant T as service/timeline.py

    U->>W: choose .json/.log/.csv file, click Upload
    W->>R: POST /api/logs (multipart/form-data)
    R->>R: validate extension + size (<= 25 MB)
    R->>P: parse_nss_feed(bytes)
    P-->>R: list[CanonicalEvent]
    R->>D: run_rules(events)
    D-->>R: list[DetectedAnomaly]
    R->>DB: INSERT upload + events + anomalies
    R-->>W: 201 UploadResponse {id, status, counts}
    opt status is uploaded / parsing
        loop poll until completed | failed
            W->>R: GET /api/uploads/{id}
            R-->>W: UploadStatus
        end
    end
    W->>R: GET /api/uploads/{id}/summary
    R->>DB: SELECT events, anomalies
    R->>T: build_summary(events, anomalies)
    T-->>R: SummaryResponse
    R-->>W: 200 summary JSON
    W-->>U: timeline + stat cards + anomaly list
```

Processing is **synchronous in the happy path**: files are small (≤ 25 MB), so
parsing and detection finish well under a second and `POST /api/logs` returns
`status: "completed"` with final counts. The frontend still supports an async
path (poll until `completed`/`failed`) so a page reload mid-processing resumes
cleanly.

### Narrative request lifecycle (optional)

```mermaid
sequenceDiagram
    participant C as NarrativeCard
    participant R as routes.py
    participant Repo as repository.py
    participant BG as generate.py (background)
    participant M as vLLM on Modal

    C->>R: POST /api/uploads/{id}/narrative
    R->>Repo: claim_narrative_generation (SELECT ... FOR UPDATE)
    alt claim acquired
        Repo-->>R: row, true
        R-->>C: 202 pending
        R->>BG: BackgroundTasks.generate_narrative
        BG->>BG: build_summary -> build_facts (sanitized)
        BG->>M: chat/completions (Bearer, JSON schema)
        M-->>BG: schema-constrained JSON
        BG->>BG: validate_sections (shape + grounding)
        BG->>Repo: upsert_narrative (ready | failed)
    else a live job already owns it
        Repo-->>R: row, false
        R-->>C: 202 pending (no second job)
    end
    loop every 2s until terminal
        C->>R: GET /api/uploads/{id}/narrative
        R-->>C: pending | ready | failed
    end
```

---

## Tech stack

| Area | Choice | Why |
|---|---|---|
| API | **FastAPI** + Uvicorn | Typed request/response models, async I/O, auto-generated OpenAPI docs at `/docs`. |
| Validation | **Pydantic v2** | One schema definition shared by routes, services, and tests. |
| Persistence | **SQLAlchemy 2.0** + **psycopg 3** | ORM-only query surface (no string SQL), easy test DB override. |
| Database | **PostgreSQL 16** | JSONB for preserving raw records, `SELECT … FOR UPDATE` for the narrative claim. |
| Frontend | **Next.js 15 (App Router)** + **React 19** + **TypeScript** | Server components, typed API client, file-based routing. |
| Styling | **Tailwind CSS** | Fast, consistent dark dashboard UI. |
| Charts | **Recharts** | Composable timeline bar chart. |
| LLM (optional) | **vLLM + Nemotron 3.5 Lightning on Modal** | 30B/3B-active MoE; scale-to-zero GPU that the API calls over an OpenAI-compatible endpoint. |
| Tooling | **uv**, **ruff**, **pytest** | Fast, reproducible Python workflow. |

---

## Local deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (Compose v2) — for the database
  and/or the full stack.
- [uv](https://docs.astral.sh/uv/) — Python 3.11 toolchain.
- [Node.js 22](https://nodejs.org/) — for running the frontend outside Docker.

Choose **Option A** for the fastest end-to-end run, or **Option B** for a local
dev loop with hot reload.

### Option A — full stack with Docker Compose

```bash
cp .env.example .env      # optional: edit POSTGRES_*/DATABASE_URL
docker compose up --build
```

Then open:

| Service | URL |
|---|---|
| Web UI | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Compose brings up `db` (Postgres, with a healthcheck), `api` (waits for the DB),
and `web`. The API creates its schema on startup. To stop:
`docker compose down` (add `-v` to also delete the database volume).

### Option B — local dev loop (hot reload)

**1. Start just the database**

```bash
docker compose up -d db
```

The init script in `docker/initdb/` creates both the dev database (`anomaly`) and
the throwaway test database (`anomaly_test`).

**2. Configure the backend**

```bash
cp .env.example .env
```

Set `DATABASE_URL` to point at `localhost` (Compose uses hostname `db`; your
laptop does not):

```dotenv
DATABASE_URL=postgresql+psycopg://anomaly:change-me@localhost:5432/anomaly
```

> The app rewrites `postgres://` and `postgresql://` to `postgresql+psycopg://`
> automatically, so a PaaS-injected URL works unchanged.

**3. Run the API**

```bash
uv sync
uv run fastapi dev app/main.py
```

API is at http://localhost:8000 (Swagger at `/docs`, health at `/health`).

**4. Run the frontend**

```bash
cd web
npm install
npm run dev
```

UI is at http://localhost:3000. It reads `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`).

**5. Try an upload**

Use one of the bundled fixtures:

```bash
curl -F file=@tests/fixtures/sample_nss_web.json http://localhost:8000/api/logs
curl -F file=@tests/fixtures/sample_nss_csv.txt http://localhost:8000/api/logs
```

Or drag the file onto the UI, then open the returned `/uploads/{id}` page.

> **LLM is optional.** With the default `LLM_ENABLED=false` everything works and
> the AI card is simply hidden. To enable it, point `LLM_BASE_URL` /
> `LLM_API_KEY` at any OpenAI-compatible server — see
> [`llm-service/README.md`](llm-service/README.md).

### Useful commands

```bash
uv run pytest -q                 # backend test suite (uses anomaly_test)
uv run pytest tests/test_api.py  # one module
uv run ruff check .              # lint
uv run ruff format .             # format

cd web && npm run build          # frontend typecheck + production build
cd web && npm run typecheck      # types only
```

---

## Configuration

All settings live in `app/config.py` and are read from environment variables
(`.env` locally, platform-injected in production). See `.env.example` for the
full annotated template.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly` | SQLAlchemy connection string. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `anomaly` | Used by the Compose `db` service. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Comma-separated allowed browser origins. |
| `CORS_ORIGIN_REGEX` | _(unset)_ | Optional regex for dynamic origins, e.g. Vercel preview URLs. |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. |
| `ENVIRONMENT` | `development` | `development` \| `production`. |
| `LLM_ENABLED` | `false` | Master switch for the narrative layer. |
| `LLM_BASE_URL` | _(empty)_ | OpenAI-compatible base URL, e.g. `https://…modal.run/v1`. |
| `LLM_API_KEY` | _(empty)_ | Sent as `Authorization: Bearer …`. |
| `LLM_MODEL` | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | Must match the server's `--served-model-name`. |
| `LLM_TIMEOUT_SECONDS` | `300` | Per-request timeout; sized to absorb a scale-to-zero cold start. |
| `LLM_REFRESH_COOLDOWN_SECONDS` | `300` | Minimum gap between forced regenerations (`?refresh=true`). |

---

## API reference

Base URL `http://localhost:8000`. All bodies are JSON unless noted. The full
contract — including every field and example payload — is in
[`spec.md`](spec.md) §5.

| Method | Path | Description | Key status codes |
|---|---|---|---|
| `POST` | `/api/logs` | Upload a log file (`multipart/form-data`, field `file`). | `201`, `400`, `413`, `422` |
| `GET` | `/api/uploads/{id}` | Upload metadata and processing status. | `200`, `404` |
| `GET` | `/api/uploads/{id}/events` | Paginated events; filters `action`, `url_category`, `anomalies_only`. | `200`, `404` |
| `GET` | `/api/uploads/{id}/summary` | The whole results page: stats, timeline, anomalies. | `200`, `404` |
| `POST` | `/api/uploads/{id}/narrative` | Request the AI brief (idempotent). | `200`, `202`, `404`, `409`, `429`, `503` |
| `GET` | `/api/uploads/{id}/narrative` | Poll the cached brief. | `200`, `404` |
| `GET` | `/health` | Liveness probe. | `200` |

**Upload response**

```json
{
  "id": 42,
  "filename": "nss_web.json",
  "status": "completed",
  "event_count": 6,
  "anomaly_count": 7
}
```

**Anomaly shape** (inside `summary.anomalies`)

```json
{
  "id": 7,
  "rule": "threat-detected",
  "severity": "high",
  "title": "Malware blocked: Trojan.Win32.FakeAV",
  "description": "carol.davis (10.1.4.22) downloaded payload.exe — detected as Trojan.Win32.FakeAV (risk 92).",
  "event_id": 3,
  "timestamp": "2026-09-10T10:03:41Z"
}
```

---

## Detection rules

All rules live in `app/service/detection.py`. Thresholds are module-level
constants so tests can nudge them, and every finding carries a one-line `title`
plus a human-readable `description`.

**Stateless rules** (evaluate one event at a time):

| Rule | Severity | Fires when |
|---|---|---|
| `threat-detected` | high | `threat_name` is set |
| `high-risk-score` | medium | `risk_score ≥ 75` |
| `suspicious-url-category` | medium | category ∈ {Gambling, Anonymizers, Phishing, Adult Content, Hacking, Piracy} |
| `dlp-violation` | high | `dlp_dictionary` is set |
| `large-upload` | high | `bytes_sent ≥ 10 MB` |
| `off-hours` | low | timestamp outside 07:00–19:00 UTC |

**Aggregate rules** (evaluate the whole event list):

| Rule | Severity | Fires when |
|---|---|---|
| `repeated-blocks` | medium | one `client_ip` is blocked ≥ 10 times |
| `request-burst` | medium | one `client_ip` makes > 100 requests in any 60 s window |

Per-event anomalies store an `event_index` so the UI can deep-link to the
offending event; aggregate anomalies have no single event.

---

## LLM narrative layer

The rules produce a list; the narrative layer turns that list into a short brief
a non-specialist can read. It is **strictly downstream** of the deterministic
layer and adds no new detections.

- **What the model sees** is only a *facts block* built by
  `service/narrative.build_facts` from the `SummaryResponse`: counts, top
  categories/hosts, and up to 15 anomalies. Raw events and user agents never
  leave the host.
- **PII scrubbing** — URLs and login identifiers are stripped from anomaly text
  before it enters the facts block (client IPs are kept for grounding).
- **Guardrails** — output is validated for shape, then *grounding-checked*: every
  IP and host-like token in the brief must appear in the facts, or the brief is
  rejected as `failed`. `risk_level` is computed in Python, never by the model.
- **Concurrency** — `claim_narrative_generation` uses `SELECT … FOR UPDATE` plus
  `INSERT … ON CONFLICT DO NOTHING`, so duplicate POSTs (or React's dev
  double-mount) never schedule two jobs.
- **Caching** — briefs are cached per upload and reused only if the
  `(model, prompt_version)` match; bumping `PROMPT_VERSION` invalidates every
  cached brief without a migration.
- **Resilience** — the background job never raises and always writes a terminal
  `ready`/`failed` row. A `pending` row older than
  `LLM_TIMEOUT_SECONDS + 60s` is treated as orphaned and recovered.

The deployment contract for the model server (Modal proxy auth, vLLM flags,
smoke test) is documented in [`llm-service/README.md`](llm-service/README.md).

---

## Project structure

```
security-anomaly-api/
├── app/                        # FastAPI backend
│   ├── main.py                 #   app factory: CORS, logging, /health, router mount
│   ├── routes.py               #   HTTP layer (thin handlers)
│   ├── config.py               #   env-driven settings
│   ├── log_config.py           #   stdlib logging + request-id context var
│   ├── service/                #   pure business logic (no FastAPI/DB)
│   │   ├── parsing.py          #     bytes -> CanonicalEvent
│   │   ├── detection.py        #     events -> anomalies (8 rules)
│   │   ├── timeline.py         #     events -> summary + buckets
│   │   └── narrative.py        #     facts block, prompt, validation
│   ├── data/                   #   persistence (SQLAlchemy)
│   │   ├── session.py          #     engine + session factory
│   │   ├── tables.py           #     ORM models
│   │   └── repository.py       #     every query in one place
│   ├── llm/                    #   model edge (httpx)
│   │   ├── client.py           #     OpenAI-compatible client
│   │   └── generate.py         #     background narrative job
│   └── model/                  #   Pydantic schemas shared by all layers
├── web/                        # Next.js + TypeScript + Tailwind frontend
│   ├── app/                    #   routes: /, /upload, /uploads/[id], /demo
│   ├── components/             #   Uploader, ResultsView, Timeline, NarrativeCard…
│   └── lib/api.ts              #   typed API client (mirrors the contract)
├── tests/                      # pytest suite + log fixtures
│   └── fixtures/               #   sample_nss_web.json, sample_nss_csv.txt
├── docker/initdb/              # Postgres bootstrap (creates anomaly_test)
├── docs/architecture.png       # this diagram
├── llm-service/README.md       # Modal/vLLM deployment contract
├── spec.md                     # design source of truth (architecture, rules, API)
├── docker-compose.yml          # db + api + web
└── pyproject.toml / uv.lock    # Python deps (uv-managed)
```

The frontend talks to the backend **only** through the typed client in
`web/lib/api.ts`, which mirrors the API contract. Change the contract in
`spec.md`, `app/routes.py`, and `web/lib/api.ts` together.

---

## Testing & quality

The suite has **119 tests** and runs against a dedicated throwaway database
(`anomaly_test`, created by `docker/initdb/`), so it never touches your dev data.

```bash
docker compose up -d db       # ensure Postgres is running
uv run pytest -q              # 119 passed
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
cd web && npm run build       # frontend typecheck + production build
```

The testing strategy:

- **Pure logic first** (`service/`) — positive *and* negative tests per rule,
  boundary tests just under/over each threshold, and parser tests for every
  input format and gotcha.
- **Repository** — round-trip tests, pagination/filtering, ordering, FK cascade,
  and the narrative claim concurrency path.
- **API** — `TestClient` with a `get_session` dependency override for the test DB.
- **Frontend** — `npm run build` is the verification gate; manual smoke of
  upload → results against a running backend.

---

## Security & operational notes

- **Upload validation** — extension allowlist + 25 MB cap; the filename is
  metadata only and is never used as a path; content is parsed as data, never
  executed or rendered raw.
- **SQL injection** — all database access goes through the SQLAlchemy ORM in
  `app/data/repository.py`, the only query site. No string-built SQL.
- **CORS** — env-driven allowlist plus an optional regex for dynamic origins.
- **Secrets** — DB credentials and the model token come from environment
  variables. `.env` is gitignored; `.env.example` contains no real values. The
  model credential lives only on the API host and is never sent to the browser.
- **LLM boundary** — the model receives only derived facts with URLs/usernames
  stripped, its output is schema-constrained and grounding-checked, and
  regeneration is rate-limited per upload because the endpoint is
  unauthenticated and each call costs GPU time.
- **Data sensitivity** — web logs contain usernames, IPs, and browsing history.
  This prototype stores them locally; don't point it at production logs without
  a PII conversation.
- **Observability** — every request gets a `request_id` (UUID) carried in a
  `ContextVar`, injected into every log record, and returned in the
  `X-Request-ID` header, so one ID greps a whole upload's lifecycle. Raw event
  contents and the `DATABASE_URL` password are never logged at `INFO`.

> **Not included by design:** authentication, multi-user support, other log
> formats, ML-based detection, streaming, retention policies, and RBAC. This is
> a focused single-user prototype.

---

## Design decisions

- **Keep `service/` pure.** No FastAPI or SQLAlchemy imports mean the logic is
  fast to test and impossible to accidentally couple to transport or storage.
- **Synchronous happy path.** At ≤ 25 MB, parsing and detection are sub-second,
  so a worker queue would be complexity without benefit. The frontend's polling
  path still handles the slow/failed cases.
- **One repository module.** Funneling every query through
  `app/data/repository.py` gives a single audit point for injection and makes the
  test-database override trivial.
- **Rule-based, not ML.** Deterministic rules are explainable in one sentence
  each, easy to unit-test, and produce the `description` text that makes the
  output human-readable.
- **Facts-in, prose-out LLM.** The model only narrates pre-computed findings —
  it cannot introduce a detection, and grounding checks catch it if it tries.
- **Prompt-versioned cache.** Storing `(model, prompt_version)` on each brief
  lets a prompt change invalidate caches without a schema migration.
- **Atomic narrative claim.** `SELECT … FOR UPDATE` plus
  `INSERT … ON CONFLICT DO NOTHING` closes the double-enqueue race that a naive
  "is it pending?" check leaves open.

---

## Author

Built by **Sammy Cayo** as a take-home exercise. The design source of truth,
including the full API contract and data model, is [`spec.md`](spec.md).
