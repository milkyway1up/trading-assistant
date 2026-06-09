"""macOS desktop notification via osascript. Phase 1."""
from __future__ import annotations

import asyncio
import shutil


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


async def notify(title: str, message: str, subtitle: str | None = None) -> None:
    if not shutil.which("osascript"):
        return
    parts = [f'display notification "{_escape(message)}"', f'with title "{_escape(title)}"']
    if subtitle:
        parts.append(f'subtitle "{_escape(subtitle)}"')
    script = " ".join(parts)
    proc = await asyncio.create_subprocess_exec("osascript", "-e", script)
    await proc.wait()
