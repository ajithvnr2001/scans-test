from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from config.settings import default_max_workers
from src.data import YahooDataProvider
from src.models import Candle, ScanSummary, StockScan
from src.strategy import analyze_five_star_setup
from src.universe import load_all_nse_symbols, unique_yahoo_symbols


# Trading-priority tiers for ranking.
#
# Tier 0 is the "act now" bucket: fresh breakouts and strict pre-breakout
# early entries. Both are highest conviction for entries at current levels.
# Tier 1 is NEAR: pressed up against the pivot but not yet through, so it
# is a preparation candidate rather than a trigger. Tier 2 is FT, which is
# already in progress and therefore a lower-priority *entry* than a fresh
# setup, even though it is confirmed.
_STAGE_TIER = {
    "early_entry": 0,
    "breakout_today": 0,
    "near_breakout": 1,
    "follow_through": 2,
}


# Distance buckets penalize extension asymmetrically. A stock just above
# pivot is better than one just below pivot (confirmed vs not), and a stock
# that has already run away from its pivot is the worst entry regardless
# of score.
def _distance_bucket(distance_pct: float) -> int:
    if 0.0 <= distance_pct <= 3.0:
        return 0  # best: fresh BO at/just above pivot
    if -3.0 <= distance_pct < 0.0:
        return 1  # watch / early: just below pivot
    if 3.0 < distance_pct <= 8.0:
        return 2  # acceptable, but already moving
    return 3      # extended (>8%) or too far below (<-3%)


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

    # Strict "clean entry only" trading-priority sort.
    # Each key is ascending (lower = better):
    #   1. score desc                 primary conviction
    #   2. stage tier                 BO/EARLY > NEAR > FT > other
    #   3. distance bucket            pivot quality:
    #                                   0% to +3% = best (fresh BO at pivot)
    #                                  -3% to  0% = watch (just below)
    #                                  +3% to +8% = acceptable but extending
    #                                  else       = extended/too far below
    #   4. breakout volume desc       within-bucket: higher volume wins
    #   5. |distance_to_pivot_pct|    final tiebreaker: closer wins
    #
    # Distance bucket is placed ABOVE volume so a clean setup at/just
    # above pivot is not displaced by a high-volume but already-extended
    # name. Within the same bucket, volume still matters.
    matches.sort(
        key=lambda item: (
            -item.signal.score,
            _STAGE_TIER.get(item.signal.stage, 99),
            _distance_bucket(item.signal.metrics.get("distance_to_pivot_pct", 100)),
            -item.signal.metrics.get("breakout_volume_ratio", 0),
            abs(item.signal.metrics.get("distance_to_pivot_pct", 100)),
        ),
    )

    return ScanSummary(
        total_requested=len(scan_symbols),
        total_with_data=total_with_data,
        matches=tuple(matches),
        errors=tuple(errors),
    )
