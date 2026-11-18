from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.healthcheck import check_dependencies
from app.observability import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    setup_observability,
)
from app.routers import auth, node_types, pipelines, runs

# get_settings() validates configuration, including the production SECRET_KEY check.
settings = get_settings()
setup_observability()

app = FastAPI(title="AI Workflow Builder API", version="1.1.0")

# Added in reverse order of execution: RequestContext runs first, then CORS, then the size limit.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # auth uses a bearer token header, not cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.add_middleware(RequestContextMiddleware)

api = APIRouter(prefix="/api/v1")
api.include_router(auth.router)
api.include_router(node_types.router)
api.include_router(pipelines.router)
api.include_router(runs.router)
app.include_router(api)


@app.get("/health", tags=["health"])
def health() -> JSONResponse:
    """200 when the database (and Redis, if configured) are reachable, otherwise 503."""
    checks = check_dependencies()
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status_code=200 if healthy else 503,
    )
