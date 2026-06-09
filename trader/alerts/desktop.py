"""Cross-platform desktop notifications.

macOS  : `osascript` displays a Notification Center toast.
Windows: PowerShell + Windows.UI.Notifications shows a native toast.
Linux  : `notify-send` (libnotify) — standard on most desktops.

Returns silently if the underlying tool is missing, so missing notifications
never crash the alert pipeline.
"""
from __future__ import annotations

import asyncio
import platform
import shutil

_SYSTEM = platform.system()


async def notify(title: str, message: str, subtitle: str | None = None) -> None:
    if _SYSTEM == "Darwin":
        await _notify_macos(title, message, subtitle)
    elif _SYSTEM == "Windows":
        await _notify_windows(title, message, subtitle)
    else:
        await _notify_linux(title, message, subtitle)


async def _notify_macos(title: str, message: str, subtitle: str | None) -> None:
    if not shutil.which("osascript"):
        return
    parts = [
        f'display notification "{_applescript_escape(message)}"',
        f'with title "{_applescript_escape(title)}"',
    ]
    if subtitle:
        parts.append(f'subtitle "{_applescript_escape(subtitle)}"')
    script = " ".join(parts)
    await _run("osascript", "-e", script)


async def _notify_windows(title: str, message: str, subtitle: str | None) -> None:
    if not shutil.which("powershell"):
        return
    body = message if not subtitle else f"{subtitle}\n{message}"
    # Use the WinRT toast API directly. Built into every Windows 10/11 box;
    # no extra modules required.
    ps = (
        '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;'
        '[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;'
        '$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;'
        '$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);'
        f'$xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{_ps_escape(title)}")) | Out-Null;'
        f'$xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{_ps_escape(body)}")) | Out-Null;'
        '$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);'
        '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("TradingAssistant").Show($toast);'
    )
    await _run("powershell", "-NoProfile", "-Command", ps)


async def _notify_linux(title: str, message: str, subtitle: str | None) -> None:
    if not shutil.which("notify-send"):
        return
    body = message if not subtitle else f"{subtitle}\n{message}"
    await _run("notify-send", title, body)


async def _run(*cmd: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


def _applescript_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _ps_escape(s: str) -> str:
    """Escape for embedding in a PowerShell double-quoted literal."""
    return s.replace("`", "``").replace('"', '`"').replace("$", "`$")
