"""Trading Assistant — personal swing-trading helper."""
__version__ = "0.1.0"

# Set CURL_CA_BUNDLE / SSL_CERT_FILE before any submodule imports yfinance,
# anthropic, requests, etc. — otherwise corp TLS interception (Zscaler) breaks
# every outbound HTTPS call. No-op on non-macOS; idempotent if the bundle
# already exists.
try:
    from trader.utils.ssl_setup import ensure_system_ca_bundle
    ensure_system_ca_bundle()
except Exception:
    pass
