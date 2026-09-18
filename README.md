# Security Anomaly API

Upload a Zscaler NSS web log. You get back a timeline, a ranked list of
suspicious events, and a summary written in plain English.

A FastAPI backend parses the logs and
runs 8 rule-based checks. A Next.js dashboard shows the results. One command
starts the whole stack, and it needs no GPU and no LLM.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-119%20passing-brightgreen">
</p>

---

## Table of contents

- [Demo login](#demo-login)
- [What it does](#what-it-does)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Run it locally](#run-it-locally)
- [Configuration](#configuration)
- [API](#api)
- [Detection rules](#detection-rules)
- [The AI summary](#the-ai-summary)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Security notes](#security-notes)
- [Why it is built this way](#why-it-is-built-this-way)
- [Author](#author)

---

## Demo login

The hosted UI is gated by a shared login (UI-only; the API stays open):

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `security` |

---

## What it does

Proxy logs are noisy. A malware download or a DLP violation hides inside
thousands of rows of JSON. This project turns one log file into something a
non-specialist can read.

1. Upload a file in the browser.
2. The backend parses it (JSON array, NDJSON, or CSV/TSV), maps it to a
   canonical schema, and runs 8 detection rules.
3. Results go into PostgreSQL. The dashboard renders a bucketed timeline, stat
   cards, an anomaly list, and a filterable events table.
4. When the inference endpoint is enabled, an LLM writes a short brief from the
   findings. It never sees raw logs, and it cannot add facts.

The only supported input is the Zscaler Nanolog Streaming Service (NSS) "Feed
Output Format: Web Logs". I kept the scope narrow on purpose.

---

## Features

- Parses by content, not by file extension. It reads a JSON array, a single
  JSON object, NDJSON, and the 34-column CSV/TSV/pipe feed, with or without a
  header row.
- Runs 8 explainable rules. 6 look at one event (threat, high risk score,
  suspicious category, DLP, large upload, off-hours). 2 look at the whole list
  (repeated blocks, request burst). Each rule is a small pure function.
- Shows a full-window timeline. The observed range is split into readable
  buckets (1m, 5m, 15m, 1h, 6h, 1d). Quiet gaps become zero-count buckets, so
  the chart shows the real time span instead of only the busy ticks.
- Lets you filter the events table by action, URL category, or "flagged by a
  rule only".
- Adds an AI brief. It is schema-constrained, grounding-checked, and cached per
  upload. Risk level is computed on the server. It is available when the
  inference endpoint is turned on (`LLM_ENABLED=true`); off by default.
- Starts with one command. `docker compose up --build` brings up the UI, API,
  and database.
- Logs a per-request `X-Request-ID` and uses structured stdlib logging.

---

## Architecture

![System architecture](docs/architecture.png)

The system has three deployable units and one layering rule: imports only flow
downward.

| Layer | Files | May import | Must **not** import |
|---|---|---|---|
| Entry point | `app/main.py` | `routes` | service/data internals |
| HTTP | `app/routes.py` | `service`, `data.repository`, `llm`, `model` | raw SQLAlchemy, parsing internals |
| Logic | `app/service/*` | `model` | FastAPI, SQLAlchemy, httpx (kept pure) |
| LLM edge | `app/llm/*` | httpx, `service.narrative`, `service.timeline`, `data.repository`, `model` | FastAPI |
| Persistence | `app/data/*` | SQLAlchemy, `model` | FastAPI |
| Schemas | `app/model/*` | Pydantic | anything else |

`app/service/` is pure Python. It imports no web framework, no database, and no
network library. That keeps the interesting logic (parsing, detection, timeline,
prompt building) easy to unit test. `app/data/` and `app/llm/` are the only
impure edges.

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

Processing is synchronous on the happy path. Files are at most 25 MB, so parsing
and detection finish well under a second. `POST /api/logs` returns
`status: "completed"` with the final counts. The frontend also handles an async
path. It polls until the status is `completed` or `failed`, so a page reload
mid-processing resumes cleanly.

### Narrative request lifecycle

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
| API | **FastAPI** + Uvicorn | Typed request and response models, async I/O, and OpenAPI docs at `/docs`. |
| Validation | **Pydantic v2** | One schema shared by routes, services, and tests. |
| Persistence | **SQLAlchemy 2.0** + **psycopg 3** | Queries go through the ORM only, and the test database is easy to swap in. |
| Database | **PostgreSQL 16** | JSONB keeps the raw record, and `SELECT ... FOR UPDATE` backs the narrative claim. |
| Frontend | **Next.js 15 (App Router)** + **React 19** + **TypeScript** | Server components, a typed API client, and file-based routing. |
| Styling | **Tailwind CSS** | A consistent dark dashboard UI, built quickly. |
| Charts | **Recharts** | A composable bar chart for the timeline. |
| LLM | **vLLM + Nemotron 3.5 Lightning on Modal** | A 30B/3B-active MoE. It scales to zero and speaks the OpenAI API. |
| Tooling | **uv**, **ruff**, **pytest** | A fast, reproducible Python workflow. |

---

## Run it locally

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (Compose v2) for the database or
  the full stack.
- [uv](https://docs.astral.sh/uv/) for Python 3.11.
- [Node.js 22](https://nodejs.org/) for the frontend outside Docker.

Use Option A for the fastest end-to-end run. Use Option B for a local dev loop
with hot reload.

### Option A: full stack with Docker Compose

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

Compose starts `db` (Postgres with a healthcheck), `api` (waits for the DB),
and `web`. The API creates its schema on startup. Stop it with
`docker compose down`. Add `-v` to delete the database volume too.

### Option B: local dev loop (hot reload)

**1. Start just the database**

```bash
docker compose up -d db
```

The init script in `docker/initdb/` creates the dev database (`anomaly`) and the
test database (`anomaly_test`).

**2. Configure the backend**

```bash
cp .env.example .env
```

Set `DATABASE_URL` to point at `localhost`. Compose uses the hostname `db`, but
your laptop does not:

```dotenv
DATABASE_URL=postgresql+psycopg://anomaly:change-me@localhost:5432/anomaly
```

The app rewrites `postgres://` and `postgresql://` to `postgresql+psycopg://`,
so a PaaS-injected URL works unchanged.

**3. Run the API**

```bash
uv sync
uv run fastapi dev app/main.py
```

The API is at http://localhost:8000 (Swagger at `/docs`, health at `/health`).

**4. Run the frontend**

```bash
cd web
npm install
npm run dev
```

The UI is at http://localhost:3000. It reads `NEXT_PUBLIC_API_URL`, which
defaults to `http://localhost:8000`.

**5. Try an upload**

Use one of the bundled fixtures:

```bash
curl -F file=@tests/fixtures/sample_nss_web.json http://localhost:8000/api/logs
curl -F file=@tests/fixtures/sample_nss_csv.txt http://localhost:8000/api/logs
```

Or drag the file onto the UI, then open the returned `/uploads/{id}` page.

The AI summary is available when the inference endpoint is turned on. With the
default `LLM_ENABLED=false`, everything works and the AI card is hidden. To
enable it, point `LLM_BASE_URL` and `LLM_API_KEY` at any OpenAI-compatible
server. See [`llm-service/README.md`](llm-service/README.md).

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

Settings live in `app/config.py` and come from environment variables. Locally
that is `.env`. In production the platform injects them. See `.env.example` for
the full annotated template.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://anomaly:anomaly@localhost:5432/anomaly` | SQLAlchemy connection string. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `anomaly` | Used by the Compose `db` service. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Comma-separated allowed browser origins. |
| `CORS_ORIGIN_REGEX` | (unset) | Optional regex for dynamic origins, such as Vercel preview URLs. |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. |
| `ENVIRONMENT` | `development` | `development` \| `production`. |
| `LLM_ENABLED` | `false` | Master switch for the narrative layer. |
| `LLM_BASE_URL` | (empty) | OpenAI-compatible base URL, for example `https://...modal.run/v1`. |
| `LLM_API_KEY` | (empty) | Sent as `Authorization: Bearer ...`. |
| `LLM_MODEL` | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | Must match the server's `--served-model-name`. |
| `LLM_TIMEOUT_SECONDS` | `300` | Per-request timeout, sized to absorb a scale-to-zero cold start. |
| `LLM_REFRESH_COOLDOWN_SECONDS` | `300` | Minimum gap between forced regenerations (`?refresh=true`). |

Frontend (`web/`, see [`web/.env.example`](web/.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser origin of the FastAPI API. |
| `AUTH_USERNAME` | (unset) | Shared UI login user. The gate is off unless all three `AUTH_*` are set. |
| `AUTH_PASSWORD` | (unset) | Shared UI login password. Env only, never `NEXT_PUBLIC_*`. |
| `AUTH_SECRET` | (unset) | HMAC key for the session cookie (`openssl rand -hex 32`). |

### Vercel (UI login)

Set these on the Vercel project (Production, and Preview if you want gated
previews too), then redeploy:

1. `AUTH_USERNAME=admin`, `AUTH_PASSWORD=security`, and a random
   `AUTH_SECRET` (`openssl rand -hex 32`). These are server-only, never
   `NEXT_PUBLIC_`.
2. Keep `NEXT_PUBLIC_API_URL` pointing at the Railway API, with no trailing
   slash.

After deploy, `/` redirects to `/login`, which shows the splash until the
signed cookie is set. Deep links like `/uploads/51` bounce to
`/login?next=/uploads/51`.

### Railway (API, no login env)

Do not add `AUTH_*` on Railway. The API stays unauthenticated. Keep:

- `CORS_ORIGINS` set to the exact Vercel origin, for example
  `https://your-app.vercel.app`, with no trailing slash.
- Optionally `CORS_ORIGIN_REGEX=https://.*\.vercel\.app` for preview URLs.

Anyone who knows the Railway URL can still call `/api/logs` with curl. The UI
splash only hides the dashboard.

---

## API

The base URL is `http://localhost:8000`. All bodies are JSON unless noted. The
full contract, including every field and example payload, is in
[`spec.md`](spec.md) section 5.

| Method | Path | Description | Key status codes |
|---|---|---|---|
| `POST` | `/api/logs` | Upload a log file (`multipart/form-data`, field `file`). | `201`, `400`, `413`, `422` |
| `GET` | `/api/uploads/{id}` | Upload metadata and processing status. | `200`, `404` |
| `GET` | `/api/uploads/{id}/events` | Paginated events. Filters: `action`, `url_category`, `anomalies_only`. | `200`, `404` |
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
  "description": "carol.davis (10.1.4.22) reached cdn-update.example-bad.net. Detected as Trojan.Win32.FakeAV (risk 92).",
  "event_id": 3,
  "timestamp": "2026-09-10T10:03:41Z"
}
```

---

## Detection rules

Rules live in `app/service/detection.py`. Thresholds are module-level constants
so tests can adjust them. Every finding has a one-line `title` and a readable
`description`.

These rules look at one event at a time:

| Rule | Severity | Fires when |
|---|---|---|
| `threat-detected` | high | `threat_name` is set |
| `high-risk-score` | medium | `risk_score` is 75 or higher |
| `suspicious-url-category` | medium | category is one of Gambling, Anonymizers, Phishing, Adult Content, Hacking, Piracy |
| `dlp-violation` | high | `dlp_dictionary` is set |
| `large-upload` | high | `bytes_sent` is 10 MB or more |
| `off-hours` | low | timestamp is outside 07:00 to 19:00 UTC |

These rules look at the whole list:

| Rule | Severity | Fires when |
|---|---|---|
| `repeated-blocks` | medium | one `client_ip` is blocked 10 or more times |
| `request-burst` | medium | one `client_ip` makes more than 100 requests in any 60 second window |

Per-event anomalies store an `event_index`, so the UI can deep-link to the
offending event. Aggregate anomalies have no single event.

---

## The AI summary

The rules produce a list. The narrative layer turns that list into a short brief
a non-specialist can read. It sits strictly downstream of the detection layer
and adds no new detections.

- The model only sees a facts block built by `service/narrative.build_facts`
  from the `SummaryResponse`. That block has counts, top categories and hosts,
  and up to 15 anomalies. Raw events and user agents never leave the host.
- URLs and login names are stripped from anomaly text before it enters the
  facts block. Client IPs stay, because grounding uses them.
- Guardrails: output is checked for shape, then grounding-checked. Every IP and
  host-like token in the brief must appear in the facts, or the brief is stored
  as `failed`. `risk_level` is computed in Python, never by the model.
- Concurrency: `claim_narrative_generation` uses `SELECT ... FOR UPDATE` plus
  `INSERT ... ON CONFLICT DO NOTHING`. Duplicate POSTs, including React's dev
  double-mount, never schedule two jobs.
- Caching: briefs are cached per upload and reused only if `(model,
  prompt_version)` match. Bumping `PROMPT_VERSION` invalidates every cached
  brief with no migration.
- Resilience: the background job never raises and always writes a terminal
  `ready` or `failed` row. A `pending` row older than
  `LLM_TIMEOUT_SECONDS + 60s` is treated as orphaned and recovered.

The model server contract (Modal proxy auth, vLLM flags, smoke test) is in
[`llm-service/README.md`](llm-service/README.md).

---

## Project layout

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
│   ├── app/                    #   routes: /, /login, /upload, /uploads/[id], /demo
│   ├── components/             #   Uploader, ResultsView, Timeline, NarrativeCard...
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

The frontend talks to the backend only through the typed client in
`web/lib/api.ts`, which mirrors the API contract. When the contract changes,
update `spec.md`, `app/routes.py`, and `web/lib/api.ts` together.

---

## Tests

The suite has 119 tests. It runs against a throwaway database (`anomaly_test`,
created by `docker/initdb/`), so it never touches your dev data.

```bash
docker compose up -d db       # ensure Postgres is running
uv run pytest -q              # 119 passed
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
cd web && npm run build       # frontend typecheck + production build
```

What the tests cover:

- Pure logic (`service/`): positive and negative tests for each rule, boundary
  tests just under and over each threshold, and parser tests for every input
  format and gotcha.
- Repository: round-trip reads, pagination and filtering, ordering, FK cascade,
  and the narrative claim concurrency path.
- API: `TestClient` with a `get_session` dependency override that points at the
  test database.
- Frontend: `npm run build` is the verification gate. I also smoke test upload
  to results against a running backend.

---

## Security notes

- Uploads are checked against an extension allowlist and capped at 25 MB. The
  filename is metadata only, never a path. Contents are parsed as data, never
  executed or rendered raw.
- All database access goes through the SQLAlchemy ORM in
  `app/data/repository.py`, which is the only query site. No string-built SQL.
- CORS is controlled by environment variables: an allowlist plus an optional
  regex for dynamic origins.
- The UI login gate is optional and Next.js only. When `AUTH_USERNAME`,
  `AUTH_PASSWORD`, and `AUTH_SECRET` are set (usually on Vercel), a signed
  cookie is required before the dashboard. There is no users table. The Railway
  API stays open.
- DB credentials and the model token come from environment variables. `.env` is
  gitignored, and `.env.example` has no real values. The model credential lives
  only on the API host and is never sent to the browser.
- The model receives only derived facts with URLs and usernames stripped. Its
  output is schema-constrained and grounding-checked. Regeneration is
  rate-limited per upload, because the endpoint is unauthenticated and each call
  costs GPU time.
- Web logs contain usernames, IPs, and browsing history. This prototype stores
  them locally. Do not point it at production logs without a PII conversation.
- Every request gets a `request_id` (UUID) in a `ContextVar`. It is injected
  into every log record and returned in the `X-Request-ID` header, so one ID
  traces a whole upload. Raw event contents and the `DATABASE_URL` password are
  never logged at `INFO`.

Out of scope, by design: API authentication, multi-user accounts, other log
formats, ML detection, streaming, retention policies, and RBAC. The optional UI
splash is a shared demo password in env, not an account system.

---

## Why it is built this way

- The service layer stays pure. `app/service/` imports no FastAPI and no
  SQLAlchemy, so the logic is easy to test and cannot couple to the web or the
  database by accident.
- The happy path is synchronous. At 25 MB or less, parsing and detection are
  sub-second, so a worker queue would add complexity for no gain. The frontend
  polling path still covers the slow and failed cases.
- Queries live in one module. Sending every query through
  `app/data/repository.py` gives one audit point for injection and makes the
  test database override trivial.
- Detection is rule-based, not ML. Each rule explains itself in one sentence, is
  easy to unit test, and produces the `description` text that makes the output
  readable.
- The LLM only narrates. It works from pre-computed findings, so it cannot
  introduce a detection. Grounding checks catch it if it tries.
- The cache is prompt-versioned. Storing `(model, prompt_version)` on each brief
  lets a prompt change invalidate caches with no schema migration.
- The narrative claim is atomic. `SELECT ... FOR UPDATE` plus
  `INSERT ... ON CONFLICT DO NOTHING` closes the double-enqueue race that a
  plain "is it pending?" check leaves open.

---

## Author

Built by **Sammy Cayo** as a take-home exercise. The design source of truth,
including the full API contract and data model, is [`spec.md`](spec.md).
