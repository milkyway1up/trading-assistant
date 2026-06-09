"""Build a standalone `Trading Assistant.app` bundle via py2app.

Usage:
    uv sync --group app
    uv run python setup_app.py py2app

Outputs `dist/Trading Assistant.app`. Drag to /Applications. Double-click to
launch — uvicorn boots in-process and a native WKWebView window opens.
"""
from setuptools import setup

APP = ["app_main.py"]
DATA_FILES = [
    ("trader/web/templates", [
        "trader/web/templates/base.html",
        "trader/web/templates/dashboard.html",
    ]),
    ("trader/web/static/css", ["trader/web/static/css/app.css"]),
    ("trader/web/static/js", [
        "trader/web/static/js/chart.js",
        "trader/web/static/js/ws.js",
    ]),
]

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "trader",
        "uvicorn",
        "fastapi",
        "starlette",
        "jinja2",
        "webview",
        "loguru",
        "pandas",
        "numpy",
        "yfinance",
        "anthropic",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "loguru",
        "typer",
        "rich",
        "questionary",
    ],
    "includes": [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    "excludes": ["tkinter", "PyQt5", "PyQt6", "matplotlib", "vectorbt"],
    "plist": {
        "CFBundleName": "Trading Assistant",
        "CFBundleDisplayName": "Trading Assistant",
        "CFBundleIdentifier": "com.millaway.tradingassistant",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # No menubar item, no dock-only weirdness. Standard app.
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
