from __future__ import annotations

import unittest

from src.models import Candle
from src.scanner import run_scan
from tests.fixtures import five_star_breakout_candles


class FakeProvider:
    def __init__(self, histories: dict[str, list[Candle]]) -> None:
        self.histories = histories
        self.calls: list[str] = []

    def fetch_history(self, symbol: str) -> list[Candle]:
        self.calls.append(symbol)
        return self.histories.get(symbol, [])


class ScannerTests(unittest.TestCase):
    def test_scans_every_unique_symbol_and_returns_actionable_matches(self) -> None:
        provider = FakeProvider(
            {
                "GOOD.NS": five_star_breakout_candles(),
                "BASE.NS": five_star_breakout_candles(latest_close=150.0, latest_volume=700.0),
                "CRASH.NS": five_star_breakout_candles(crash_base=True),
            }
        )

        summary = run_scan(
            ["good", "base", "crash", "GOOD.NS"],
            provider=provider,
            max_workers=3,
            min_score=7,
        )

        self.assertEqual(summary.total_requested, 3)
        self.assertEqual(summary.total_with_data, 3)
        self.assertEqual(sorted(provider.calls), ["BASE.NS", "CRASH.NS", "GOOD.NS"])
        self.assertEqual([match.symbol for match in summary.matches], ["GOOD.NS"])

    def test_can_include_watchlist_bases_when_requested(self) -> None:
        provider = FakeProvider(
            {
                "BASE.NS": five_star_breakout_candles(latest_close=150.0, latest_volume=700.0),
            }
        )

        summary = run_scan(
            ["base"],
            provider=provider,
            max_workers=1,
            min_score=6,
            actionable_only=False,
        )

        self.assertEqual(len(summary.matches), 1)
        self.assertEqual(summary.matches[0].signal.stage, "base")


if __name__ == "__main__":
    unittest.main()
