"""Native desktop window wrapping the FastAPI dashboard.

Spawns uvicorn on a background thread, waits for the server to come up, then
opens a chromeless WKWebView window pointed at it. Single process, no Node, no
Electron — looks like a real Mac app.
"""
from __future__ import annotations

import socket
import threading
import time
from contextlib import closing

import uvicorn
import webview
from loguru import logger

from trader.config import get_config
from trader.web.server import create_app

_DEFAULT_TITLE = "Trading Assistant"


def _wait_for_port(host: str, port: int, timeout: float = 8.0) -> None:
    """Block until uvicorn is accepting connections, or raise."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"FastAPI server didn't bind {host}:{port} within {timeout}s")


class _ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True, name="uvicorn")
        self.config = uvicorn.Config(
            create_app(),
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(self.config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def launch(
    *,
    title: str = _DEFAULT_TITLE,
    host: str = "127.0.0.1",
    port: int | None = None,
    width: int = 1400,
    height: int = 900,
    debug: bool = False,
) -> None:
    """Run uvicorn + a pywebview window.

    Returns when the window is closed; the daemon server thread exits with the
    process. `debug=True` enables WKWebView devtools (right-click → Inspect).
    """
    cfg = get_config()
    port = port or cfg.server.port

    server = _ServerThread(host=host, port=port)
    server.start()

    try:
        _wait_for_port(host, port)
    except RuntimeError:
        server.stop()
        raise

    logger.info(f"Opening desktop window → http://{host}:{port}")
    webview.create_window(
        title,
        f"http://{host}:{port}",
        width=width,
        height=height,
        resizable=True,
        confirm_close=False,
    )
    try:
        webview.start(debug=debug)
    finally:
        server.stop()
