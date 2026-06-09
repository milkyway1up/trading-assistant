"""Cross-platform audio alerts.

macOS  : `say` (TTS) + `afplay` (sound file)
Windows: PowerShell SAPI.SpVoice (TTS) + `winsound` (system sounds)
Linux  : `spd-say` or `espeak` (TTS) + `paplay`/`aplay` (sound file)

Each function returns silently if the underlying tool isn't available, so
alerts never crash the caller — the worst case is no audible cue.
"""
from __future__ import annotations

import asyncio
import platform
import shutil

_SYSTEM = platform.system()


async def speak(message: str) -> None:
    """Speak `message` aloud using the platform's text-to-speech."""
    if _SYSTEM == "Darwin":
        await _run_if_available("say", message)
    elif _SYSTEM == "Windows":
        # SAPI ships with every modern Windows install.
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech;"
            "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
            f".Speak('{_ps_escape(message)}')"
        )
        await _run_if_available("powershell", "-NoProfile", "-Command", ps_cmd)
    else:
        # Linux: try the most common screen-reader frontends in order.
        for binary in ("spd-say", "espeak", "espeak-ng"):
            if shutil.which(binary):
                await _run_if_available(binary, message)
                return


async def beep(sound_path: str | None = None) -> None:
    """Play an alert sound. `sound_path` is honored on macOS/Linux; on Windows
    we always use the system 'Asterisk' sound for consistency."""
    if _SYSTEM == "Darwin":
        path = sound_path or "/System/Library/Sounds/Ping.aiff"
        await _run_if_available("afplay", path)
    elif _SYSTEM == "Windows":
        # winsound is stdlib on Windows. Run in a thread so we don't block
        # the asyncio loop.
        try:
            import winsound
            await asyncio.to_thread(
                winsound.MessageBeep, winsound.MB_ICONASTERISK
            )
        except Exception:
            pass
    else:
        # Linux: try paplay (PulseAudio) then aplay (ALSA).
        path = sound_path or "/usr/share/sounds/freedesktop/stereo/message.oga"
        for binary in ("paplay", "aplay"):
            if shutil.which(binary):
                await _run_if_available(binary, path)
                return


async def _run_if_available(binary: str, *args: str) -> None:
    if not shutil.which(binary):
        return
    proc = await asyncio.create_subprocess_exec(
        binary, *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


def _ps_escape(s: str) -> str:
    """Escape a string for embedding in a PowerShell single-quoted literal."""
    return s.replace("'", "''")
