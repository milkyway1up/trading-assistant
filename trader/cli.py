"""Trader CLI — typer entrypoint with all subcommands."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="trader",
    help="Personal swing-trading assistant.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# Subcommand groups
auth_app = typer.Typer(help="Schwab OAuth flow.")
journal_app = typer.Typer(help="Trade journal: sync, annotate, stats.")
app.add_typer(auth_app, name="auth")
app.add_typer(journal_app, name="journal")


# ─────────────────────────────────────────────────────────────────
# serve — launch web dashboard
# ─────────────────────────────────────────────────────────────────
@app.command()
def serve(
    host: Optional[str] = typer.Option(None, help="Override server host"),
    port: Optional[int] = typer.Option(None, help="Override server port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Launch the web dashboard at http://localhost:8765."""
    from trader.config import get_config
    from trader.web.server import run

    cfg = get_config()
    run(
        host=host or cfg.server.host,
        port=port or cfg.server.port,
        reload=reload,
    )


# ─────────────────────────────────────────────────────────────────
# analyze — LLM thesis on a ticker
# ─────────────────────────────────────────────────────────────────
@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. AAPL"),
    with_position: bool = typer.Option(False, help="Include current Schwab position context"),
):
    """Generate an LLM-powered thesis for a ticker."""
    from trader.llm.analysis import analyze_ticker

    ticker = ticker.upper()
    console.print(f"[bold cyan]Analyzing {ticker}...[/bold cyan]")
    result = analyze_ticker(ticker, with_position=with_position)
    _print_analysis(result)


# ─────────────────────────────────────────────────────────────────
# prep — weekly research doc
# ─────────────────────────────────────────────────────────────────
@app.command()
def prep(
    output: Optional[Path] = typer.Option(None, help="Override output path"),
):
    """Generate a weekly market prep document (Sunday-night ritual)."""
    from trader.llm.prep import generate_weekly_prep

    console.print("[bold cyan]Generating weekly prep — this can take ~30 sec...[/bold cyan]")
    path = generate_weekly_prep(output_path=output)
    console.print(f"[green]✓ Saved to {path}[/green]")


# ─────────────────────────────────────────────────────────────────
# scan — run setup detectors
# ─────────────────────────────────────────────────────────────────
@app.command()
def scan(
    setup: Optional[str] = typer.Option(None, help="Limit to a single setup type"),
    min_confidence: float = typer.Option(0.5, help="Minimum confidence 0-1"),
    top: int = typer.Option(20, help="Show top N results"),
):
    """Scan the universe for setups."""
    from trader.scanner.runner import run_scan

    console.print("[bold cyan]Running scanner...[/bold cyan]")
    results = run_scan(setup=setup, min_confidence=min_confidence)
    _print_scan_table(results[:top])


# ─────────────────────────────────────────────────────────────────
# order — preview, confirm, submit
# ─────────────────────────────────────────────────────────────────
@app.command()
def order(
    ticker: str = typer.Argument(...),
    side: str = typer.Argument(..., help="buy or sell"),
    risk_pct: Optional[float] = typer.Option(None, "--risk", help="% of equity to risk (e.g. 1.5)"),
    qty: Optional[int] = typer.Option(None, help="Explicit share quantity (overrides --risk)"),
    entry: float = typer.Option(..., help="Entry limit price"),
    stop: Optional[float] = typer.Option(None, help="Stop-loss price"),
    target: Optional[float] = typer.Option(None, help="Take-profit price"),
    order_type: str = typer.Option("limit", "--type", help="limit / bracket / market"),
):
    """Preview, confirm, and submit a trade order."""
    console.print("[yellow]Order command — implement in Phase 3.[/yellow]")
    console.print(f"  Would place: {side} {qty or '?'} {ticker.upper()} @ {entry}, stop {stop}, target {target}, type {order_type}")


# ─────────────────────────────────────────────────────────────────
# auth subcommands
# ─────────────────────────────────────────────────────────────────
@auth_app.command("login")
def auth_login():
    """Run the Schwab OAuth browser flow."""
    from trader.broker.auth import run_oauth_flow
    run_oauth_flow()


@auth_app.command("status")
def auth_status():
    """Show Schwab token status and expiry."""
    from trader.broker.auth import token_status
    status = token_status()
    console.print(status)


@auth_app.command("refresh")
def auth_refresh():
    """Force a refresh of the Schwab access token."""
    from trader.broker.auth import refresh_token
    refresh_token()


# ─────────────────────────────────────────────────────────────────
# journal subcommands
# ─────────────────────────────────────────────────────────────────
@journal_app.command("sync")
def journal_sync():
    """Pull latest Schwab transactions into the local journal DB."""
    console.print("[yellow]Journal sync — implement in Phase 4.[/yellow]")


@journal_app.command("annotate")
def journal_annotate(trade_id: int):
    """Add reason/tags/notes to a trade."""
    console.print(f"[yellow]Annotate trade {trade_id} — implement in Phase 4.[/yellow]")


@journal_app.command("stats")
def journal_stats(since: str = typer.Option("30d", help="Lookback window")):
    """Show win rate, R-multiple, expectancy, mistakes."""
    console.print(f"[yellow]Stats since {since} — implement in Phase 4.[/yellow]")


@journal_app.command("grade")
def journal_grade(trade_id: int):
    """Have Claude grade a closed trade against its entry thesis."""
    console.print(f"[yellow]Grade trade {trade_id} — implement in Phase 5.[/yellow]")


# ─────────────────────────────────────────────────────────────────
# backtest
# ─────────────────────────────────────────────────────────────────
@app.command()
def backtest(
    strategy: str = typer.Argument(..., help="Strategy name (e.g. ema_pullback)"),
    ticker: str = typer.Option("SPY", help="Ticker symbol"),
    since: str = typer.Option("2020-01-01", help="Start date YYYY-MM-DD"),
):
    """Backtest a strategy on historical data."""
    console.print(f"[yellow]Backtest {strategy} on {ticker} since {since} — implement in Phase 6.[/yellow]")


# ─────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────
def _print_analysis(result: dict) -> None:
    """Render a Claude analysis result as a Rich panel."""
    from rich.panel import Panel
    from rich.table import Table

    ticker = result.get("ticker", "?")
    confidence = result.get("confidence", "?")

    body_lines = [
        f"[bold]Thesis:[/bold] {result.get('thesis', '—')}",
        "",
        f"[bold]Catalysts:[/bold] {', '.join(result.get('catalysts', [])) or '—'}",
        f"[bold]Risks:[/bold] {', '.join(result.get('risks', [])) or '—'}",
        "",
    ]

    levels = Table.grid(padding=(0, 2))
    levels.add_column(style="cyan")
    levels.add_column()
    for k in ("ideal_entry", "stop_level", "target", "time_horizon", "suggested_size_pct"):
        if k in result:
            levels.add_row(k.replace("_", " ").title(), str(result[k]))

    console.print(Panel(
        "\n".join(body_lines),
        title=f"{ticker} — confidence {confidence}/10",
        border_style="cyan",
    ))
    console.print(levels)


def _print_scan_table(results: list[dict]) -> None:
    from rich.table import Table

    if not results:
        console.print("[dim]No setups found.[/dim]")
        return

    table = Table(title="Top setups", show_lines=False)
    table.add_column("Ticker", style="bold")
    table.add_column("Setup")
    table.add_column("Confidence", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("Stop", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("R:R", justify="right")

    for r in results:
        rr = r.get("risk_reward")
        rr_str = f"{rr:.1f}" if isinstance(rr, (int, float)) else "—"
        table.add_row(
            r.get("ticker", "?"),
            r.get("setup", "?"),
            f"{r.get('confidence', 0):.2f}",
            f"{r.get('entry', 0):.2f}",
            f"{r.get('stop', 0):.2f}",
            f"{r.get('target', 0):.2f}",
            rr_str,
        )
    console.print(table)


if __name__ == "__main__":
    app()
