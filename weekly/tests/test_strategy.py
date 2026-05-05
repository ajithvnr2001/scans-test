from __future__ import annotations

import unittest

from src.strategy import analyze_five_star_setup
from tests.fixtures import five_star_breakout_candles


class StrategyTests(unittest.TestCase):
    def test_detects_breakout_that_matches_reference_charts(self) -> None:
        signal = analyze_five_star_setup(five_star_breakout_candles())

        self.assertGreaterEqual(signal.score, 9)
        self.assertEqual(signal.stage, "breakout_today")
        self.assertTrue(signal.actionable)
        self.assertIn("breakout volume confirms demand", signal.reasons)
        self.assertLessEqual(signal.metrics["recent_range_pct"], 14)

    def test_rejects_crash_after_vertical_move(self) -> None:
        signal = analyze_five_star_setup(five_star_breakout_candles(crash_base=True))

        self.assertLess(signal.score, 7)
        self.assertFalse(signal.actionable)
        self.assertEqual(signal.stage, "damaged_base")
        self.assertGreater(signal.metrics["post_peak_drawdown_pct"], 28)

    def test_middle_of_base_is_not_actionable_by_default(self) -> None:
        signal = analyze_five_star_setup(
            five_star_breakout_candles(latest_close=150.0, latest_volume=700.0)
        )

        self.assertEqual(signal.stage, "base")
        self.assertFalse(signal.actionable)
        self.assertGreaterEqual(signal.score, 6)

    def test_strict_weekly_early_entry_before_breakout(self) -> None:
        signal = analyze_five_star_setup(
            five_star_breakout_candles(latest_close=158.0, latest_volume=700.0)
        )

        self.assertEqual(signal.stage, "early_entry")
        self.assertTrue(signal.actionable)
        self.assertGreaterEqual(signal.score, 8)
        self.assertLessEqual(abs(signal.metrics["distance_to_pivot_pct"]), 2.0)

    def test_requires_enough_history(self) -> None:
        signal = analyze_five_star_setup(five_star_breakout_candles()[:30])

        self.assertEqual(signal.stage, "insufficient_data")
        self.assertFalse(signal.actionable)


if __name__ == "__main__":
    unittest.main()
