"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import Settings, get_settings
from backend.core.errors import AppError
from backend.routes.ask import router as ask_router
from backend.routes.files import router as files_router
from backend.services.assistant_service import AssistantService
from backend.services.context_service import ContextService
from backend.services.embeddings_service import EmbeddingsService
from backend.services.file_store import FileStore
from backend.services.llm_service import LLMService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None, llm: LLMService | None = None) -> FastAPI:
    # Settings are validated here, at startup: a missing API key fails fast.
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        llm_service = llm or LLMService(settings)
        embeddings = EmbeddingsService(settings) if settings.embeddings_provider != "none" else None
        files = FileStore(settings.files_dir, settings.file_ttl_seconds)
        context = ContextService(embeddings, settings.chunk_size_chars, settings.chunk_overlap_chars)
        app.state.files = files
        app.state.assistant = AssistantService(settings, llm_service, context, files)
        yield
        await llm_service.aclose()
        if embeddings:
            await embeddings.aclose()

    app = FastAPI(title="AI Browser Assistant API", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {
            "status": "ok",
            "version": app.version,
            # Set by Render for git deploys, or by the Docker build (APP_COMMIT).
            "commit": os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_COMMIT") or "unknown",
            "provider": settings.llm_provider,
            "fallback": settings.llm_fallback_provider,
        }

    app.include_router(ask_router)
    app.include_router(files_router)
    return app


# `uvicorn backend.app:app` entry point.
app = create_app()
