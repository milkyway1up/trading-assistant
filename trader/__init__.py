"""Trading Assistant — personal swing-trading helper."""
__version__ = "0.1.0"

# Isolate ourselves from the user's shell environment.
#
# This Mac is configured for Leidos LiteLLM (ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL
# point at the corporate proxy with a Leidos-issued token). The trading assistant
# uses the *personal* Anthropic account, so we must:
#   1. Drop the corporate ANTHROPIC_API_KEY so pydantic-settings falls back to .env
#   2. Drop ANTHROPIC_BASE_URL so the Anthropic SDK hits api.anthropic.com directly
import os as _os
for _var in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    _os.environ.pop(_var, None)
del _os, _var

# Set CURL_CA_BUNDLE / SSL_CERT_FILE before any submodule imports yfinance,
# anthropic, requests, etc. — otherwise corp TLS interception (Zscaler) breaks
# every outbound HTTPS call. No-op on non-macOS; idempotent if the bundle
# already exists.
try:
    from trader.utils.ssl_setup import ensure_system_ca_bundle
    ensure_system_ca_bundle()
except Exception:
    pass
