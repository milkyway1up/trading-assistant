"""FastAPI app + uvicorn launcher for the local dashboard."""
from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from trader.config import get_config

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Assistant",
        description="Local dashboard for swing-trading.",
        version="0.1.0",
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Routers
    from trader.web.api import quotes, stream

    app.include_router(quotes.router, prefix="/api")
    app.include_router(stream.router)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        cfg = get_config()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "watchlist": cfg.watchlist or ["SPY", "AAPL", "NVDA", "TSLA"],
                "default_ticker": (cfg.watchlist or ["SPY"])[0],
            },
        )

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return app


# Module-level app for `uvicorn trader.web.server:app --reload`
app = create_app()


def run(host: str = "127.0.0.1", port: int = 8765, reload: bool = False) -> None:
    """Launch uvicorn programmatically (called by `trader serve`)."""
    if reload:
        uvicorn.run(
            "trader.web.server:app",
            host=host,
            port=port,
            reload=True,
        )
    else:
        uvicorn.run(app, host=host, port=port)
