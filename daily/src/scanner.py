from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from config.settings import default_max_workers
from src.data import YahooDataProvider
from src.models import Candle, ScanSummary, StockScan
from src.strategy import analyze_five_star_setup
from src.universe import load_all_nse_symbols, unique_yahoo_symbols


class HistoryProvider(Protocol):
    def fetch_history(self, symbol: str) -> list[Candle]:
        ...


def process_stock(
    symbol: str,
    provider: HistoryProvider,
    min_score: int = 7,
    actionable_only: bool = True,
) -> tuple[StockScan | None, bool, dict[str, str] | None]:
    try:
        candles = provider.fetch_history(symbol)
        if not candles:
            return None, False, None

        signal = analyze_five_star_setup(candles)
        is_match = signal.score >= min_score and (signal.actionable or not actionable_only)
        if not is_match:
            return None, True, None

        return StockScan(symbol=symbol, signal=signal), True, None
    except Exception as exc:
        return None, False, {"symbol": symbol, "error": str(exc)}


def run_scan(
    symbols: list[str] | None = None,
    *,
    provider: HistoryProvider | None = None,
    min_score: int = 7,
    max_workers: int | None = None,
    actionable_only: bool = True,
) -> ScanSummary:
    scan_symbols = unique_yahoo_symbols(symbols) if symbols is not None else load_all_nse_symbols()
    history_provider = provider or YahooDataProvider()
    worker_count = max_workers or default_max_workers()

    matches: list[StockScan] = []
    errors: list[dict[str, str]] = []
    total_with_data = 0

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(process_stock, symbol, history_provider, min_score, actionable_only): symbol
            for symbol in scan_symbols
        }

        for future in as_completed(futures):
            match, had_data, error = future.result()
            if had_data:
                total_with_data += 1
            if error:
                errors.append(error)
            if match:
                matches.append(match)

    matches.sort(
        key=lambda item: (
            item.signal.score,
            item.signal.metrics.get("breakout_volume_ratio", 0),
            item.signal.metrics.get("distance_to_pivot_pct", -100),
        ),
        reverse=True,
    )

    return ScanSummary(
        total_requested=len(scan_symbols),
        total_with_data=total_with_data,
        matches=tuple(matches),
        errors=tuple(errors),
    )
