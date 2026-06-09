"""macOS audio alerts via `say` and `afplay`. Phase 1."""
from __future__ import annotations

import asyncio
import shutil


async def speak(message: str) -> None:
    if not shutil.which("say"):
        return
    proc = await asyncio.create_subprocess_exec("say", message)
    await proc.wait()


async def beep(sound_path: str = "/System/Library/Sounds/Ping.aiff") -> None:
    if not shutil.which("afplay"):
        return
    proc = await asyncio.create_subprocess_exec("afplay", sound_path)
    await proc.wait()
