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
auth_app = typer.Typer(help="Broker authentication (Alpaca keys / Schwab OAuth).")
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
# desktop — launch as a native window
# ─────────────────────────────────────────────────────────────────
@app.command()
def desktop(
    port: Optional[int] = typer.Option(None, help="Override server port"),
    width: int = typer.Option(1400, help="Window width"),
    height: int = typer.Option(900, help="Window height"),
    debug: bool = typer.Option(False, "--debug", help="Enable WKWebView devtools"),
):
    """Open the dashboard in a native macOS window (no browser tab)."""
    from trader.desktop import launch

    launch(port=port, width=width, height=height, debug=debug)


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
    if not results:
        console.print("[dim]Try lowering --min-confidence or check broker/yfinance connectivity.[/dim]")


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
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
):
    """Preview, confirm, and submit a trade order."""
    from trader.broker import orders as order_builders
    from trader.broker.factory import get_broker
    from trader.broker.risk_guard import run_all_checks
    from trader.config import get_config
    from trader.sizing.calculator import position_size

    ticker = ticker.upper()
    side_lc = side.lower()
    if side_lc not in {"buy", "sell"}:
        console.print(f"[red]Invalid side '{side}'. Use buy or sell.[/red]")
        raise typer.Exit(1)
    if order_type not in {"market", "limit", "bracket"}:
        console.print(f"[red]Unsupported --type '{order_type}'. Use market / limit / bracket.[/red]")
        raise typer.Exit(1)
    if order_type == "bracket" and (stop is None or target is None):
        console.print("[red]bracket orders require both --stop and --target.[/red]")
        raise typer.Exit(1)

    cfg = get_config()
    try:
        broker = get_broker()
        account = broker.get_account()
    except Exception as e:
        console.print(f"[red]Broker unavailable: {e}[/red]")
        raise typer.Exit(1)

    equity = float(account.get("equity") or 0)
    settled_cash = float(account.get("settled_cash") or account.get("cash") or 0)

    # ── Sizing ──
    if qty is None:
        if stop is None:
            console.print("[red]Need --stop to compute size from --risk. Pass --qty to override.[/red]")
            raise typer.Exit(1)
        risk = risk_pct if risk_pct is not None else cfg.risk.default_risk_pct
        sized = position_size(account_equity=equity, risk_pct=risk, entry=entry, stop=stop)
        if sized.shares < 1:
            console.print(f"[red]{sized.note}[/red]")
            raise typer.Exit(1)
        qty = sized.shares
        dollar_risk = sized.dollar_risk
    else:
        dollar_risk = abs(entry - stop) * qty if stop is not None else 0.0

    order_value = qty * entry

    # ── Risk guard ──
    checks = run_all_checks(
        side=side_lc,
        account_equity=equity,
        settled_cash=settled_cash,
        order_value=order_value,
        dollar_risk=dollar_risk,
        entry=entry,
        stop=stop,
        cfg_max_position_pct=cfg.risk.max_position_pct,
        cfg_max_risk_pct=cfg.risk.max_risk_per_trade_pct,
        cfg_max_stop_distance_pct=cfg.risk.max_stop_distance_pct,
    )
    failures = [c for c in checks if not c.ok]
    if failures:
        console.print("[red]Risk guard blocked the order:[/red]")
        for c in failures:
            console.print(f"  • {c.reason}")
        raise typer.Exit(1)

    # ── Build spec ──
    if order_type == "market":
        spec = order_builders.market(ticker, side_lc, qty)
    elif order_type == "bracket":
        spec = order_builders.bracket(ticker, side_lc, qty, entry, stop, target)
    else:
        spec = order_builders.limit(ticker, side_lc, qty, entry)

    # ── Preview ──
    rr = (abs(target - entry) / abs(entry - stop)) if (stop and target) else None
    console.print(
        f"\n[bold]Preview:[/bold] {side_lc.upper()} {qty} {ticker} via {order_type} @ {entry}"
    )
    console.print(f"  Stop {stop} | Target {target} | R:R {rr:.2f}" if rr else f"  Stop {stop} | Target {target}")
    console.print(f"  Order value ${order_value:,.2f} ({order_value / equity * 100:.1f}% of ${equity:,.2f} equity)")
    console.print(f"  Dollar risk ${dollar_risk:,.2f} ({dollar_risk / equity * 100:.2f}% of equity)")

    if not yes:
        if not typer.confirm("Submit this order?", default=False):
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    # ── Submit ──
    try:
        result = broker.place_order(spec)
    except Exception as e:
        console.print(f"[red]Broker rejected order: {e}[/red]")
        raise typer.Exit(1)

    order_id = result.get("id") or result.get("order_id") or ""
    console.print(f"[green]✓ Order submitted: {order_id}[/green]")

    # ── Journal log ──
    try:
        from trader.journal.entry import add_trade
        trade_id = add_trade(
            ticker=ticker,
            side=side_lc,
            quantity=qty,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            schwab_order_id=str(order_id) if order_id else None,
        )
        console.print(f"[dim]Journaled as trade #{trade_id}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Order placed but journal log failed: {e}[/yellow]")


# ─────────────────────────────────────────────────────────────────
# auth subcommands
# ─────────────────────────────────────────────────────────────────
@auth_app.command("login")
def auth_login():
    """Authenticate with the configured broker.

    - Alpaca: validates ALPACA_API_KEY / ALPACA_SECRET_KEY by hitting /v2/account.
    - Schwab: runs the OAuth browser flow.
    """
    from trader.broker.auth import run_auth
    result = run_auth()
    console.print(result)


@auth_app.command("status")
def auth_status():
    """Show broker auth status (keys valid? token expiry? account snapshot?)."""
    from trader.broker.auth import auth_status as _auth_status
    console.print(_auth_status())


@auth_app.command("refresh")
def auth_refresh():
    """Force a refresh of the Schwab access token. (Alpaca: no-op.)"""
    from trader.config import get_config
    from trader.broker.auth import refresh_token

    if get_config().broker.provider == "alpaca":
        console.print("[yellow]Alpaca uses static API keys — nothing to refresh.[/yellow]")
        return
    refresh_token()


# ─────────────────────────────────────────────────────────────────
# journal subcommands
# ─────────────────────────────────────────────────────────────────
@journal_app.command("sync")
def journal_sync(
    since_days: int = typer.Option(30, help="Pull fills from the last N days"),
):
    """Pull latest broker fills into the local journal and FIFO-pair them."""
    from trader.journal.sync import sync_fills

    console.print(f"[bold cyan]Syncing fills from the last {since_days} days...[/bold cyan]")
    try:
        result = sync_fills(since_days=since_days)
    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/red]")
        raise typer.Exit(1)
    console.print(
        f"[green]✓ {result['new_entries']} new entries, "
        f"{result['matched_exits']} exits matched, "
        f"{result['skipped']} skipped.[/green]"
    )


@journal_app.command("annotate")
def journal_annotate(
    trade_id: int,
    setup_type: Optional[str] = typer.Option(None, help="Setup name (breakout, flag, ...)"),
    thesis: Optional[str] = typer.Option(None, help="Thesis at entry"),
    catalysts: Optional[str] = typer.Option(None, help="Catalysts (comma-separated)"),
    mistakes: Optional[str] = typer.Option(None, help="Mistakes / lessons"),
    exit_reason: Optional[str] = typer.Option(None, help="Why did you exit"),
    notes: Optional[str] = typer.Option(None, help="Free-form notes"),
):
    """Annotate a trade with setup/thesis/notes."""
    from trader.journal.entry import annotate

    fields = {k: v for k, v in {
        "setup_type": setup_type,
        "thesis_at_entry": thesis,
        "catalysts": catalysts,
        "mistakes": mistakes,
        "exit_reason": exit_reason,
        "notes": notes,
    }.items() if v is not None}
    if not fields:
        console.print("[yellow]Nothing to update — pass at least one field.[/yellow]")
        raise typer.Exit(1)
    try:
        annotate(trade_id, **fields)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓ Trade {trade_id} updated: {', '.join(fields)}[/green]")


@journal_app.command("stats")
def journal_stats(since: str = typer.Option("30d", help="Lookback window e.g. 30d, 90d, 1y")):
    """Show win rate, R-multiple, expectancy by setup type."""
    from trader.journal.analytics import stats

    days = _parse_window(since)
    result = stats(since_days=days)
    if not result.get("total"):
        console.print(f"[dim]No closed trades in the last {since}.[/dim]")
        return
    _print_stats_table(result, since)


@journal_app.command("grade")
def journal_grade(trade_id: int):
    """Have Claude grade a closed trade against its entry thesis."""
    from trader.journal.db import Trade, get_session
    from trader.llm.grade import grade_trade

    session = get_session()
    trade = session.get(Trade, trade_id)
    if trade is None:
        console.print(f"[red]Trade {trade_id} not found.[/red]")
        raise typer.Exit(1)
    if trade.exit_price is None:
        console.print(f"[yellow]Trade {trade_id} is still open — close it first.[/yellow]")
        raise typer.Exit(1)

    bars = _bars_around_trade(trade)
    payload = {
        "ticker": trade.ticker,
        "side": trade.side,
        "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
        "entry_price": trade.entry_price,
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "exit_price": trade.exit_price,
        "size": trade.quantity,
        "stop": trade.stop_price,
        "target": trade.target_price,
        "thesis_at_entry": trade.thesis_at_entry,
        "exit_reason": trade.exit_reason,
        "realized_pnl": trade.realized_pnl,
        "r_multiple": trade.r_multiple,
    }

    console.print(f"[bold cyan]Grading trade {trade_id} ({trade.ticker})...[/bold cyan]")
    result = grade_trade(payload, bars)

    grade = result.get("grade") if isinstance(result, dict) else None
    lesson = result.get("lesson") if isinstance(result, dict) else None
    if grade:
        trade.llm_grade = grade
    if lesson:
        trade.llm_lesson = lesson
    if isinstance(result, dict) and (tags := result.get("tags")):
        trade.llm_tags = ",".join(tags) if isinstance(tags, list) else str(tags)
    session.commit()

    console.print(f"[green]Grade: {grade or '?'}[/green]")
    if lesson:
        console.print(f"[dim]{lesson}[/dim]")


# ─────────────────────────────────────────────────────────────────
# backtest
# ─────────────────────────────────────────────────────────────────
@app.command()
def backtest(
    strategy: str = typer.Argument(..., help="Strategy name (e.g. ema_pullback)"),
    ticker: str = typer.Option("SPY", help="Ticker symbol"),
    period: str = typer.Option("5y", help="Lookback period (1y, 2y, 5y, 10y, max)"),
    initial_cash: float = typer.Option(10_000.0, help="Starting cash"),
):
    """Backtest a strategy on historical daily data."""
    import importlib

    from trader.backtest.engine import run_backtest
    from trader.data.yfinance_bars import get_bars

    ticker = ticker.upper()
    console.print(f"[bold cyan]Backtesting {strategy} on {ticker} ({period})...[/bold cyan]")

    try:
        module = importlib.import_module(f"trader.backtest.strategies.{strategy}")
    except ImportError as e:
        console.print(f"[red]Strategy '{strategy}' not found: {e}[/red]")
        raise typer.Exit(1)

    strategy_fn = getattr(module, "signals", None) or getattr(module, "strategy", None)
    if strategy_fn is None:
        console.print(f"[red]Strategy module needs a `signals(df)` or `strategy(df)` function.[/red]")
        raise typer.Exit(1)

    df = get_bars(ticker, timeframe="1d", period=period)
    if df.empty:
        console.print(f"[red]No bars returned for {ticker}.[/red]")
        raise typer.Exit(1)

    try:
        result = run_backtest(df, strategy_fn, initial_cash=initial_cash)
    except Exception as e:
        console.print(f"[red]Backtest failed: {e}[/red]")
        raise typer.Exit(1)

    _print_backtest_result(strategy, ticker, period, result)


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


def _print_backtest_result(strategy: str, ticker: str, period: str, result: dict) -> None:
    from rich.table import Table

    table = Table(title=f"{strategy} — {ticker} ({period})", show_header=False)
    table.add_column("metric", style="cyan")
    table.add_column("value", justify="right")
    table.add_row("Trades", str(result.get("trade_count", 0)))
    table.add_row("Win rate", f"{result.get('win_rate', 0):.1f}%")
    table.add_row("Total return", f"{result.get('total_return', 0):.2f}%")
    table.add_row("CAGR", f"{result.get('cagr', 0):.2f}%")
    table.add_row("Sharpe", f"{result.get('sharpe', 0):.2f}")
    table.add_row("Max drawdown", f"{result.get('max_drawdown', 0):.2f}%")
    table.add_row("Avg win", f"${result.get('avg_win', 0):.2f}")
    table.add_row("Avg loss", f"${result.get('avg_loss', 0):.2f}")
    table.add_row("Expectancy", f"${result.get('expectancy', 0):.2f}")
    table.add_row("Final value", f"${result.get('final_value', 0):,.2f}")
    console.print(table)


def _parse_window(s: str) -> int:
    """'30d' → 30, '12w' → 84, '1y' → 365. Defaults to days if no suffix."""
    s = s.strip().lower()
    if not s:
        return 30
    suffix, n = s[-1], s[:-1]
    if suffix == "d" and n.isdigit():
        return int(n)
    if suffix == "w" and n.isdigit():
        return int(n) * 7
    if suffix == "m" and n.isdigit():
        return int(n) * 30
    if suffix == "y" and n.isdigit():
        return int(n) * 365
    if s.isdigit():
        return int(s)
    return 30


def _print_stats_table(result: dict, since: str) -> None:
    from rich.table import Table

    overall = result.get("overall", {})
    console.print(f"\n[bold]Closed trades — last {since}[/bold]   total: {result['total']}")
    if overall:
        console.print(
            f"  Win rate {overall.get('win_rate', 0) * 100:.1f}%   "
            f"avg R {overall.get('avg_r', 0):.2f}   "
            f"expectancy ${overall.get('expectancy', 0):.2f}   "
            f"P&L ${overall.get('total_pnl', 0):+,.2f}"
        )

    by_setup = result.get("by_setup", {})
    if not by_setup:
        return
    table = Table(title="By setup")
    table.add_column("Setup", style="bold")
    table.add_column("N", justify="right")
    table.add_column("Win%", justify="right")
    table.add_column("Avg R", justify="right")
    table.add_column("Expectancy", justify="right")
    table.add_column("Total P&L", justify="right")
    for name, agg in sorted(by_setup.items(), key=lambda kv: -kv[1].get("count", 0)):
        table.add_row(
            name,
            str(agg.get("count", 0)),
            f"{agg.get('win_rate', 0) * 100:.1f}",
            f"{agg.get('avg_r', 0):.2f}",
            f"{agg.get('expectancy', 0):.2f}",
            f"{agg.get('total_pnl', 0):+,.2f}",
        )
    console.print(table)


def _bars_around_trade(trade) -> list[dict]:
    """Pull daily bars from a few days before entry through a few days past exit."""
    from datetime import timedelta

    if not trade.entry_time or not trade.exit_time:
        return []
    try:
        from trader.data.yfinance_bars import get_bars
        df = get_bars(trade.ticker, timeframe="1d", period="6mo")
        if df.empty:
            return []
        start = trade.entry_time - timedelta(days=3)
        end = trade.exit_time + timedelta(days=5)
        df = df.loc[start.replace(tzinfo=None):end.replace(tzinfo=None)] \
            if df.index.tz is None else df.loc[start:end]
        return [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
            }
            for idx, row in df.iterrows()
        ]
    except Exception:
        return []


if __name__ == "__main__":
    app()
