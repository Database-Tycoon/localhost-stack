"""``tycoon serve`` — start the FastAPI dashboard server."""

from __future__ import annotations

import typer

app = typer.Typer()


def serve_cmd(
    port: int = typer.Option(8888, help="Port to listen on."),
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
    reload: bool = typer.Option(False, help="Enable auto-reload for development."),
) -> None:
    """Start the Tycoon FastAPI dashboard server."""
    import uvicorn

    from tycoon.utils.console import info

    info(f"Starting Tycoon server on {host}:{port}")
    uvicorn.run(
        "tycoon.server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )
