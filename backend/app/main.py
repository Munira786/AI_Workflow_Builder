import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import auth, pipelines, runs

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

if settings.environment == "production" and (
    settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32
):
    raise RuntimeError("SECRET_KEY must be set to a random value of at least 32 characters")

app = FastAPI(title="AI Workflow Builder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # auth uses a bearer token header, not cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

api = APIRouter(prefix="/api/v1")
api.include_router(auth.router)
api.include_router(pipelines.router)
api.include_router(runs.router)
app.include_router(api)


@app.get("/health", tags=["health"])
def health() -> dict:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
