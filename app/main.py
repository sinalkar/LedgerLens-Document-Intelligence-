import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.providers import get_provider
from app.routers import documents, ingest, review
from app.services.redaction import install_redaction_filter
from app.storage.db import get_engine, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()  # fail fast: a misconfigured deploy dies here
    logging.basicConfig(level=settings.log_level.upper())
    if settings.pii_redaction_enabled:
        install_redaction_filter()
    init_db()
    logger.info(
        "LedgerLens up: provider=%s model=%s storage=%s env=%s",
        settings.llm_provider,
        settings.extraction_model,
        settings.storage_backend,
        settings.environment,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LedgerLens",
        description=(
            "Document intelligence: receipt/invoice image → schema-validated "
            "structured data with per-field confidence and a human review queue."
        ),
        lifespan=lifespan,
    )
    app.include_router(ingest.router)
    app.include_router(review.router)
    app.include_router(documents.router)

    @app.get("/health")
    def health(prov=Depends(get_provider)):
        settings = get_settings()
        db_ok = True
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "error",
            "provider": prov.name,
            "model": settings.extraction_model,
            "provider_healthy": prov.health_check(),
            "environment": settings.environment,
        }

    @app.get("/metrics")
    def metrics():
        if not get_settings().metrics_enabled:
            return Response(status_code=404)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
