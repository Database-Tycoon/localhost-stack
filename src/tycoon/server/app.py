"""FastAPI application factory for the Tycoon dashboard server."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from tycoon.server.routes import router as api_router
from tycoon.server.spa import SPA_HTML
from tycoon.server.websocket import router as ws_router


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Tycoon Dashboard",
        description="Local-first analytics dashboard for NYC transit data.",
    )

    # CORS — allow all origins for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router)

    # WebSocket routes
    app.include_router(ws_router)

    # SPA catch-all — serve the embedded HTML at root
    @app.get("/", response_class=HTMLResponse)
    async def spa_root() -> str:
        return SPA_HTML

    return app
