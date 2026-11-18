# AI Workflow Builder

Build AI pipelines visually: drag nodes onto a canvas, connect them, save the pipeline to your
account, and run it. Runs execute in a background worker and the editor shows each node's status
live (pending → running → succeeded/failed) with the final outputs.

**Stack:** React + React Flow + Zustand · FastAPI · PostgreSQL (SQLAlchemy + Alembic) ·
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

| Node     | Executable | Behaviour |
| -------- | ---------- | --------- |
| Input    | ✅ | Provides a value entered in the run panel (keyed by the node's *Name*). |
| Text     | ✅ | Template with `{{variables}}`; each variable becomes an input handle. |
| LLM      | ✅ | Calls Claude (`claude-opus-5-5` by default) with `prompt` and optional `system` inputs. |
| Output   | ✅ | Collects its input as a named run output. |
| API, Database, Email, Filter, Math | ⏳ | Shown in the editor, but running a pipeline that contains them fails with a clear message. |

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, /health, /api/v1 routers
│   │   ├── config.py        # settings from environment variables
│   │   ├── db.py, models.py # SQLAlchemy engine + User / Pipeline / Run
│   │   ├── schemas.py       # request/response validation (graph limits, edge checks)
│   │   ├── security.py      # bcrypt passwords, JWT auth
│   │   ├── graph.py         # DAG check / topological order
│   │   ├── jobs.py          # enqueue to RQ (or in-process without Redis)
│   │   ├── engine/          # executor + per-node handlers
│   │   └── routers/         # auth, pipelines, runs
│   ├── alembic/             # database migrations
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/                 # editor, nodes, auth, run panel
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
└── .github/workflows/       # ci.yml, publish.yml
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

# Frontend: http://localhost:3000
cd frontend
npm install
npm start
```

## Tests and linting

```bash
cd backend && pytest && ruff check .
cd frontend && CI=true npm run build     # lint warnings fail the build
```

## Configuration

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./dev.db` | `postgres://` URLs are accepted and normalized. |
| `REDIS_URL` | unset | Unset: runs execute in-process. Set it to use RQ workers. |
| `SECRET_KEY` | dev value | JWT signing key. In production it must be at least 32 characters, or startup fails. |
| `ENVIRONMENT` | `development` | Set to `production` to enforce the `SECRET_KEY` check. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed frontend origins. |
| `ANTHROPIC_API_KEY` | none | Required by the LLM node. |
| `LLM_MODEL` / `LLM_EFFORT` | `claude-opus-5-5` / `medium` | Model and effort for the LLM node. |
| `MAX_NODES` / `MAX_EDGES` | `200` / `500` | Size limits per pipeline. |
| `REACT_APP_API_URL` (frontend, build time) | `http://localhost:8000` | Backend URL the browser calls. |

## API (prefix `/api/v1`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| POST | `/auth/register` | none | Create an account, returns a JWT. |
| POST | `/auth/login` | none | Form fields `username` (email) and `password`, returns a JWT. |
| GET | `/auth/me` | ✅ | Current user. |
| POST | `/pipelines/parse` | none | `{nodes, edges}` → `{num_nodes, num_edges, is_dag}`. |
| GET / POST | `/pipelines` | ✅ | List / create your pipelines. |
| GET / PATCH / DELETE | `/pipelines/{id}` | ✅ | Load / update / delete. |
| POST | `/runs` | ✅ | `{graph?, pipeline_id?, inputs}`, queues a run and returns `202`. |
| GET | `/runs`, `/runs/{id}` | ✅ | Run history and live status (`node_states`, `outputs`, `error`). |
| GET | `/health` | none | Liveness check, including the database connection. |

## CI/CD

- **`ci.yml`** runs on every push and PR:
  - Backend: ruff, then the Alembic migrations against a real PostgreSQL (upgrade, check, downgrade), then pytest.
  - Frontend: a strict production build.
  - Docker: builds every image.
- **`publish.yml`** runs after CI passes on `main`. It pushes `backend` and `frontend` images to GitHub Container Registry as `ghcr.io/<owner>/<repo>-backend` and `-frontend`, tagged `latest` and with the commit SHA. Set the repository variable `PUBLIC_API_URL` so the frontend image calls your deployed API.
