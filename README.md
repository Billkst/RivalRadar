# RivalRadar

**English** · [简体中文](./README.zh-CN.md)

> AI multi-agent competitive-analysis system. Give it a product and a list of rivals; it collects, analyzes, writes, and quality-checks, then returns a structured competitive report.

**Live demo**: https://rival-radar-seven.vercel.app (frontend on Vercel + backend on Render + Supabase Postgres persistence; the free Render tier cold-starts for ~1 minute on first hit, which is normal)

---

## Architecture (6-node StateGraph, fully observable in real time)

```
POST /run  ──►  streamed back over SSE (collect → analyze → write → qc, every step visible)
    │
    ▼
  LangGraph StateGraph · 6 nodes
  collect ─► analyze ─► write ─► qc ─► decide ─► finalize
     ▲          ▲              │
     │  Doubao function-calling │  qc fails  → rewrite / re-collect (closed loop, ≤2 rounds)
     │  Tavily primary / Exa    │  qc passes → curate (drop unsupported cells) → decide
     └──────── retry loop ◄─────┘
    │
    ▼  intermediate artifacts streamed item by item (query · source · cell_row · verdict_recheck …)
GET /stream/:run_id  ──►  rebuild process events from persisted state (refresh / deep-link replay)
```

**What each node does:**

| Node | Responsibility |
|---|---|
| collect | Parallel search per dimension × language (Tavily primary / Exa fallback), extract Evidence, emit each query and source as it lands |
| analyze | Doubao function-calling structured extraction (features / pricing / personas / SWOT) plus comparison discipline (`_COMPARE_RULE`: no cross-product conflation, no derived marketing numbers); builds the comparison matrix cell by cell |
| write | Deterministic Markdown rendering + LLM grounded lede (two-step streamed drafting) → full report |
| qc | Curator model: per-cell `support_verdict` in three states (supported / partial / unsupported); unsupported cells are dropped and recorded in `curation_drops`, missing cells render as "—" with a coverage note (anti-hallucination hard gates stay intact) |
| decide | Synthesizes decision recommendations from curated evidence (decision-level three-state + causal bridge) |

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/Billkst/RivalRadar.git
cd RivalRadar
python -m venv .venv
.venv/bin/pip install -e .
```

### 2. Configure environment variables

Create a `.env` file in the project root with the values for these keys:

```
ARK_API_KEY=          # optional; server-side Doubao key. Unset → BYOK mode: each request carries X-LLM-* headers from the frontend 模型设置 page
TAVILY_API_KEY=        # required (or EXA_API_KEY)
EXA_API_KEY=           # optional; Tavily is primary, Exa is fallback
RIVALRADAR_DB=         # optional, defaults to rivalradar.db
RIVALRADAR_PORT=       # optional, defaults to 8000
RIVALRADAR_HOST=       # optional, defaults to 127.0.0.1 (use 0.0.0.0 for cross-host access)
RIVALRADAR_RUN_BUDGET_S=  # optional, defaults to 900; per-run wall-clock budget (seconds); aborts on timeout to avoid hangs
DATABASE_URL=          # optional; set a postgres:// URL (e.g. Supabase) to switch to Postgres persistence; unset uses local SQLite
```

> **Key discipline**: `.env` is in `.gitignore` and must never be committed. Leaking an API key violates the contest rules and is immediate disqualification. The `/healthz` endpoint returns only `{"ok": true}` and never exposes key values.

### 3. Run the services

The repo ships dev scripts (they handle the local proxy boundary and run from any directory). **Open one terminal for each:**

```bash
# Terminal 1 — backend FastAPI (http://127.0.0.1:8000)
./scripts/dev-backend.sh

# Terminal 2 — frontend Vite (http://localhost:3000, /api/* auto-proxied to the backend)
./scripts/dev-frontend.sh
```

Open **http://localhost:3000** to start. Stop both services:

```bash
./scripts/stop-dev.sh        # kills :8000 and :3000 by port
```

> **Two things to know**
> - **No `--reload` on the backend**: after editing `rivalradar/**` or `main.py`, restart `dev-backend.sh` for changes to take effect (the frontend hot-reloads via HMR, no restart needed).
> - **WSL2 + Clash**: the backend script preserves an explicitly configured proxy; otherwise it probes `RIVALRADAR_DEV_PROXY` (default `http://127.0.0.1:7897`) and prints the selected path. Only localhost is forced to bypass the proxy. The frontend script clears proxy variables because it talks only to localhost.
>
> Backend only, directly: `.venv/bin/python main.py` (listens on `http://127.0.0.1:8000`).

---

## API endpoints (21 routes)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/run` | Start a competitive-analysis run, streamed back over SSE |
| `POST` | `/discover-competitors` | Discover candidate rivals from a product name |
| `POST` | `/llm/ping` | BYOK connectivity test — sends the real run-shaped request; returns latency + (for thinking models) completion tokens |
| `GET` | `/stream/{run_id}` | Replay the rich process events of a finished run |
| `GET` | `/runs` | List all run summaries (includes the `degraded` field) |
| `GET` | `/run/{run_id}` | Get a single run's detail |
| `POST` | `/run/{run_id}/cancel` | Cancel an in-flight run (cooperatively stops the live LLM call) |
| `GET` | `/runs/{run_id}/queries` | Real search queries (each query + hit count) |
| `GET` | `/runs/{run_id}/evidence` | All evidence for the run |
| `GET` | `/runs/{run_id}/curation-drops` | Cells dropped by QC curation (three-state support) |
| `GET` | `/evidence/{evidence_id}` | Get a single evidence item |
| `GET` | `/analysis/{run_id}` | Structured analysis (with per-cell three-state) |
| `GET` | `/decisions/{run_id}` | Decision recommendations (decision-level three-state) |
| `GET` | `/insight/{run_id}` | AI synthesized headline (3 sections) |
| `GET` | `/report/{run_id}` | The Markdown report |
| `GET` | `/qc/{run_id}` | QC result (verdict + gaps) |
| `GET` | `/trace/{run_id}` | LangGraph node execution trace |
| `GET`·`PUT`·`DELETE` | `/agent-skills[/{agent_id}/{skill_id}]` | Agent skill catalog subsystem |
| `POST` | `/annotations` | Add a manual-challenge annotation (challenge-rate stats) |
| `GET` | `/healthz` | Health check |

**BYOK headers (optional, all-or-nothing on the first three):** `X-LLM-Base-URL` / `X-LLM-API-Key` / `X-LLM-Model` override the model per request (partial → 422); optional `X-LLM-Max-Tokens` declares the vendor output cap. Unset → the server env key (if any) is used. Keys live only in the browser and in per-request memory — never persisted.

**SSE event types:**
- Live `POST /run`: `start` / `node` / `query` / `query_hit` / `source` / `cell_row` / `verdict_recheck` / `error` / `cancelled` / `done`
- Replay `GET /stream/:run_id`: rebuilt from persisted trace / evidence as `start` / `trace` / query station / source / matrix / retry loop / `done`

**Request body example (`POST /run`):**

```json
{
  "competitors": ["RivalA", "RivalB"],
  "dimensions": ["core_workflows", "pricing"]
}
```

Limits: `competitors` ≤ 5, `dimensions` ≤ 6, each string 1-200 chars.

---

## Running the tests

```bash
./scripts/verify.sh backend   # version consistency + backend tests
./scripts/verify.sh frontend  # typecheck + lint + production build
./scripts/verify.sh all       # both
```

Backend tests mock external services and never include `spikes/`. See [`TESTING.md`](TESTING.md).

---

## Tech stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + sse-starlette (SSE streaming) |
| Agent orchestration | LangGraph `StateGraph` (6 nodes: collect/analyze/write/qc/decide/finalize + conditional routing + closed-loop retry) |
| LLM | Doubao (ByteDance ARK platform, function-calling / tools path) |
| Search | Tavily (primary) + Exa (fallback), `FallbackSearch` auto-switch |
| Storage | **SQLite / Supabase Postgres dual-dialect** — SQLite by default (WAL, 12 tables); set `DATABASE_URL=postgres://` to switch to Postgres (psycopg3, lazily imported); one repository codebase runs on both via standard `ON CONFLICT`. 12 tables: `runs / evidence / analysis / decisions / insight / qc_result / report / trace / annotations / queries / curation_drops / agent_skills` |
| Frontend | React 19 + Vite + Tailwind 3 + Zustand 5 + framer-motion (real-time SSE workbench + decision cockpit) |
| Validation | Pydantic v2: `Evidence / CompetitorAnalysis / QCResult` schemas |
| Packaging | `pyproject.toml` (PEP 517), Python ≥ 3.11 |

---

## Deployment

The live demo is the frontend on **Vercel** (Vite static build) + the backend on **Render** (long-running FastAPI container, single worker, long-lived SSE) + **Supabase Postgres** persistence (set Render's `DATABASE_URL` to connect; data survives container restarts).

Full step-by-step deployment (Render / Vercel setup + Supabase) is in [`DEPLOY.md`](DEPLOY.md).

---

## Project layout

```
rivalradar/
  agents/      # Agent roles (collector / analyst / writer / qc; decide synthesis lives in graph/)
  api/         # FastAPI routers (runs / reads / annotations / sse / agent_skills)
  collect/     # Collection pipeline (search + safe_fetch + rate limiting)
  graph/       # LangGraph StateGraph + routing logic
  llm/         # Doubao structured_call wrapper
  schema/      # Pydantic schemas (Evidence / CompetitorAnalysis / QCResult)
  search/      # SearchProvider protocol + TavilyProvider + ExaProvider + FallbackSearch
  storage/     # db.py dialect routing (SQLite / Postgres) + repository CRUD
  config.py    # Environment variable reads (never exposes key values)
tests/         # automated backend tests (external services mocked)
spikes/        # Real end-to-end spikes against Doubao / Tavily / Supabase (see SPIKE_RESULTS.md)
docs/superpowers/specs/  # Design specs
main.py        # Service entrypoint
```

---

## Documentation

| File | Contents |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | Version history, latest v0.6.2.0 |
| [`DEPLOY.md`](DEPLOY.md) | Deployment guide (Vercel + Render + Supabase Postgres) |
| [`TESTING.md`](TESTING.md) | Testing guide, commands, boundaries, and conventions |
| [`TODOS.md`](TODOS.md) | Non-blocking backlog (grouped + P0-P4) |
| [`DESIGN.md`](DESIGN.md) | Frontend design system v5 (type / color / spacing / motion / decision cockpit) |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | Data-source compliance statement |
| [`SKILLS.md`](SKILLS.md) | Claude Code skill cheat sheet |
| [`docs/superpowers/specs/2026-05-21-rivalradar-design.md`](docs/superpowers/specs/2026-05-21-rivalradar-design.md) | Full design spec |

---

## Version

Current version: **v0.6.2.0** (BYOK and token usage metering, 2026-07-15)

Version format: `MAJOR.MINOR.PATCH.MICRO` (< 1.0 means the API is unstable and breaking changes are allowed)

---

## License

See [`LICENSE`](LICENSE).
