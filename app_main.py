"""py2app entrypoint — what gets executed when the user double-clicks the .app.

Kept dead-simple on purpose: just delegate to `trader.desktop.launch`. This file
exists separately from `trader/cli.py` because py2app freezes a single script as
the bundle's main, and we don't want to drag the typer/CLI surface in here.
"""
from trader.desktop import launch

if __name__ == "__main__":
    launch()
