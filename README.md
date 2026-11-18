# AI Workflow Builder

Build AI pipelines visually: drag nodes onto a canvas, connect them, save the pipeline to your
account, and run it. Runs execute in a background worker and the editor shows each node's status
live (pending → running → succeeded/failed) with the final outputs.

**Stack:** React + React Flow + Zustand (Vite) · FastAPI · PostgreSQL (SQLAlchemy + Alembic) ·
Redis + RQ workers · Claude (Anthropic API) · Docker · GitHub Actions

## Architecture

```
 Browser (React)  ──HTTP/JSON──▶  FastAPI (backend)  ──▶  PostgreSQL   users, pipelines, runs
       ▲                              │
       │ polls GET /runs/{id}         └── enqueue ──▶  Redis  ──▶  RQ worker(s)
       └──────────────────────────────────────────────────────────── execute nodes, write status
```

- The API never runs pipelines itself. It stores a `Run`, enqueues it, and returns `202`.
- Workers run the nodes in topological order and write each node's state to the database as it changes.
- The API and the workers are stateless, so each can be scaled out on its own.

## Node types

The backend's registry ([backend/app/engine/registry.py](backend/app/engine/registry.py)) is the
single list of node types. The editor loads it from `GET /api/v1/node-types` (labels, handles,
default data, naming rule, template syntax, which nodes can run), so adding a node is one
`NodeSpec` there, plus an entry in `frontend/src/nodes/registry.js` only if it needs custom UI.

| Node     | Executable | Behaviour |
| -------- | ---------- | --------- |
| Input    | ✅ | Provides a value entered in the run panel (keyed by the node's *Name*; blank = `input_<n>`). |
| Text     | ✅ | Template with `{{variables}}`; each variable becomes an input handle. |
| LLM      | ✅ | Calls Claude (`claude-opus-5-5` by default, streamed) with `prompt` and optional `system` inputs. |
| Output   | ✅ | Collects its input as a named run output. |
| API, Database, Email, Filter, Math | ⏳ | Shown greyed out in the toolbar ("soon"); a run that needs one is rejected up front. |

When a pipeline has Output nodes, only the nodes that feed an Output run; anything else on the
canvas is marked *skipped* (so a stray node can't fail the run or spend tokens).

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, middleware, /health, /api/v1 routers
│   │   ├── config.py         # settings from environment variables (+ production checks)
│   │   ├── db.py, models.py  # SQLAlchemy engine + User / Pipeline / Run
│   │   ├── schemas.py        # request/response validation (graph and field limits)
│   │   ├── security.py       # bcrypt passwords, JWT auth with revocation
│   │   ├── rate_limit.py     # fixed-window limits (memory or Redis)
│   │   ├── pagination.py     # cursor pagination for list endpoints
│   │   ├── observability.py  # JSON logs, request ids, Sentry, body-size limit
│   │   ├── healthcheck.py    # DB/Redis checks (API /health and worker healthcheck)
│   │   ├── graph.py          # DAG check / topological order
│   │   ├── jobs.py           # enqueue to RQ (or in-process without Redis)
│   │   ├── maintenance.py    # reaper for runs whose worker died
│   │   ├── engine/           # node registry, executor, node handlers
│   │   └── routers/          # auth, node-types, pipelines, runs
│   ├── alembic/              # database migrations
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/                  # editor, nodes, store (incl. run polling), tests in __tests__/
│   ├── nginx/                # nginx config templates (CSP and security headers)
│   └── Dockerfile
├── docker-compose.yml
└── .github/workflows/        # ci.yml, publish.yml
```

## Run with Docker (recommended)

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY and a SECRET_KEY
docker compose up --build
```

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

Compose starts PostgreSQL, Redis, a one-off `migrate` job, the API, one worker and the frontend.
To add workers: `docker compose up --scale worker=3`.

## Run without Docker

You don't need Postgres or Redis for this. The backend falls back to SQLite and runs pipelines in-process.

```bash
# Backend: http://127.0.0.1:8000
cd backend
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                # set ANTHROPIC_API_KEY
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend: http://localhost:3000 (Node 22+)
cd frontend
npm install
npm run dev
```

## Tests and linting

```bash
cd backend && pytest && ruff check .
cd frontend && npm run lint && npm test && npm run build
```

## Configuration

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./dev.db` | `postgres://` URLs are accepted and normalized. |
| `REDIS_URL` | unset | Unset: runs execute in-process. Set it to use RQ workers and shared rate limits. |
| `SECRET_KEY` | dev value | JWT signing key. With `ENVIRONMENT=production`, startup fails unless it is ≥32 characters and not one of this repo's placeholder/dev keys. |
| `ENVIRONMENT` | `development` | `production` enforces the `SECRET_KEY` check and switches logs to JSON. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed frontend origins. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxies whose `X-Forwarded-For` is trusted (set to your load balancer so rate limits see client IPs). |
| `ANTHROPIC_API_KEY` | none | Required by the LLM node (read from the environment or `backend/.env`). |
| `LLM_MODEL` / `LLM_EFFORT` | `claude-opus-5-5` / `medium` | Default model and effort for the LLM node. |
| `LLM_ALLOWED_MODELS` | empty | Extra models users may pick per node (comma-separated); `LLM_MODEL` is always allowed. |
| `MAX_LLM_NODES_PER_RUN` / `MAX_ACTIVE_RUNS_PER_USER` | `10` / `3` | Cost controls (`0` disables). |
| `DAILY_TOKEN_BUDGET_PER_USER` | `1000000` | LLM tokens per user per UTC day (`0` disables). |
| `RATE_LIMIT_LOGIN` / `_REGISTER` / `_RUNS` | `5`/min, `5`/hour, `20`/min | Per IP (auth) or per user (runs); each has a `..._WINDOW_SECONDS`. |
| `MAX_BODY_BYTES` / `MAX_FIELD_CHARS` | `1000000` / `50000` | Request size limit (413) and max length of any text field in a node. |
| `MAX_NODES` / `MAX_EDGES` | `200` / `500` | Size limits per pipeline. |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / auto | `LOG_FORMAT=json` or `text` (default: JSON in production). |
| `SENTRY_DSN` | unset | Send errors to Sentry. |
| `VITE_API_URL` (frontend, build time) | `http://localhost:8000` | Backend URL the browser calls. |
| `API_ORIGIN` (frontend container) | `http://localhost:8000` | API origin allowed by the Content-Security-Policy. |

## API (prefix `/api/v1`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| POST | `/auth/register` | none | Create an account, returns a JWT. Rate limited per IP. |
| POST | `/auth/login` | none | Form fields `username` (email) and `password`, returns a JWT. Rate limited per IP. |
| POST | `/auth/logout` | ✅ | Revokes every token issued to the user so far. |
| GET | `/auth/me` | ✅ | Current user. |
| GET | `/node-types` | none | Node catalogue used by the editor. |
| POST | `/pipelines/parse` | none | `{nodes, edges}` → `{num_nodes, num_edges, is_dag}`. |
| GET / POST | `/pipelines` | ✅ | List (`{items, next_cursor}`, `?limit=&cursor=`) / create your pipelines. |
| GET / PATCH / DELETE | `/pipelines/{id}` | ✅ | Load / update / delete. |
| POST | `/runs` | ✅ | `{graph?, pipeline_id?, inputs}`, validates, checks quotas, queues the run and returns `202`. |
| GET | `/runs` | ✅ | Run history, newest first (`{items, next_cursor}`, `?pipeline_id=&limit=&cursor=`). |
| GET | `/runs/{id}` | ✅ | Live status (`node_states`, `outputs`, `error`, `input_tokens`, `output_tokens`). |
| GET | `/health` | none | 200 when the database (and Redis, if configured) answer; 503 otherwise. |

Every response carries an `X-Request-ID` (send your own to correlate); the same id appears in the
API's and the worker's log lines for that run.

## CI/CD

- **`ci.yml`** runs on every push and PR:
  - Backend: ruff, then the Alembic migrations against a real PostgreSQL (upgrade, check, downgrade), then pytest.
  - Frontend: ESLint, Vitest, then a production build.
  - Docker: builds every image.
- **`publish.yml`** runs after CI passes on `main`. It pushes `backend` and `frontend` images to GitHub Container Registry as `ghcr.io/<owner>/<repo>-backend` and `-frontend`, tagged `latest` and with the commit SHA. Set the repository variable `PUBLIC_API_URL` so the frontend image calls your deployed API.
