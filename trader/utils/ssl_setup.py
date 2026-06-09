"""SSL trust setup for environments behind a corporate proxy (e.g. Zscaler).

curl-cffi (used by yfinance) ships its own bundled CA list and doesn't see the
roots installed in the macOS keychain. On a managed Mac with TLS interception,
every yfinance call fails with `curl: (60) SSL certificate problem: self
signed certificate in certificate chain`.

`ensure_system_ca_bundle()` exports the macOS System keychain to a PEM file at
~/.config/trader/system-ca.pem and points the relevant env vars at it. Run
once at process start; cheap and idempotent.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from loguru import logger

_BUNDLE_PATH = Path.home() / ".config" / "trader" / "system-ca.pem"
_KEYCHAINS = [
    "/Library/Keychains/System.keychain",
    "/System/Library/Keychains/SystemRootCertificates.keychain",
]


def export_macos_ca_bundle(target: Path = _BUNDLE_PATH) -> Path:
    """Dump every cert in the System keychains to a single PEM file."""
    if platform.system() != "Darwin":
        raise RuntimeError("export_macos_ca_bundle only supports macOS")
    if not shutil.which("security"):
        raise RuntimeError("`security` CLI not on PATH — cannot export keychain")

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as out:
        for kc in _KEYCHAINS:
            if not Path(kc).exists():
                continue
            res = subprocess.run(
                ["security", "find-certificate", "-a", "-p", kc],
                capture_output=True, text=True, check=False,
            )
            if res.returncode == 0:
                out.write(res.stdout)
    target.chmod(0o644)
    return target


def ensure_system_ca_bundle() -> Path | None:
    """Export the keychain bundle if missing and set CURL_CA_BUNDLE / SSL_CERT_FILE.
    Safe to call repeatedly. Returns the bundle path, or None on non-macOS."""
    if platform.system() != "Darwin":
        return None
    if not _BUNDLE_PATH.exists():
        try:
            export_macos_ca_bundle(_BUNDLE_PATH)
            logger.info(f"Exported system CA bundle → {_BUNDLE_PATH}")
        except Exception as e:
            logger.warning(f"Could not export system CA bundle: {e}")
            return None

    # Don't clobber if user has set their own.
    os.environ.setdefault("CURL_CA_BUNDLE", str(_BUNDLE_PATH))
    os.environ.setdefault("SSL_CERT_FILE", str(_BUNDLE_PATH))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_BUNDLE_PATH))
    return _BUNDLE_PATH
