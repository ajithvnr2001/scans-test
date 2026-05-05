from __future__ import annotations

import unittest

from src.ranker import combine_timeframe_outputs


class RankerTests(unittest.TestCase):
    def test_prefers_multi_timeframe_entry_confirmation(self) -> None:
        outputs = {
            "daily": {"results": [_row("ABC.NS", "breakout_today", 9, 1.8, 0.5)]},
            "weekly": {"results": [_row("ABC.NS", "early_entry", 8, 1.2, -1.0)]},
            "monthly": {"results": [_row("ABC.NS", "near_breakout", 8, 1.0, -3.0)]},
        }

        results = combine_timeframe_outputs(outputs, min_overall_score=0)

        self.assertEqual(results[0]["symbol"], "ABC.NS")
        self.assertTrue(results[0]["has_entry_stage"])
        self.assertEqual(results[0]["timeframe_count"], 3)
        self.assertIn("confirmation", results[0]["confirmation"])

    def test_excludes_near_only_by_default(self) -> None:
        outputs = {
            "daily": {"results": [_row("ABC.NS", "near_breakout", 8, 1.0, -1.0)]},
            "weekly": {"results": [_row("ABC.NS", "near_breakout", 8, 1.0, -2.0)]},
            "monthly": {"results": []},
        }

        self.assertEqual(combine_timeframe_outputs(outputs, min_overall_score=0), [])
        self.assertEqual(
            combine_timeframe_outputs(outputs, min_overall_score=0, include_near_only=True)[0]["symbol"],
            "ABC.NS",
        )

    def test_filters_by_technical_upside_and_timeframe_hierarchy(self) -> None:
        outputs = {
            "daily": {"results": [_row("ABC.NS", "breakout_today", 10, 2.0, 1.0)]},
            "weekly": {"results": [_row("ABC.NS", "breakout_today", 9, 2.0, 1.0)]},
            "monthly": {"results": []},
        }

        results = combine_timeframe_outputs(
            outputs,
            min_overall_score=0,
            min_technical_upside_pct=8.0,
            min_timeframes=2,
            require_weekly=True,
        )

        self.assertEqual(results[0]["symbol"], "ABC.NS")
        self.assertGreaterEqual(results[0]["technical_upside_pct"], 8.0)
        self.assertIn("weekly/five_star_setup.pine", results[0]["pine_confirmation"][0])

    def test_early_image_filter_excludes_late_follow_through_only(self) -> None:
        outputs = {
            "daily": {"results": [_row("ABC.NS", "follow_through", 10, 2.0, -2.0)]},
            "weekly": {"results": [_row("ABC.NS", "follow_through", 9, 2.0, -2.0)]},
            "monthly": {"results": []},
        }

        self.assertEqual(
            combine_timeframe_outputs(outputs, min_overall_score=0, early_image_only=True),
            [],
        )

    def test_early_image_filter_allows_near_watchlist_when_requested(self) -> None:
        outputs = {
            "daily": {"results": []},
            "weekly": {"results": [_row("ABC.NS", "near_breakout", 8, 0.8, -1.5)]},
            "monthly": {"results": []},
        }

        results = combine_timeframe_outputs(
            outputs,
            min_overall_score=0,
            early_image_only=True,
            include_near_only=True,
        )

        self.assertEqual(results[0]["symbol"], "ABC.NS")
        self.assertTrue(results[0]["has_early_image_setup"])
        self.assertEqual(results[0]["early_image_timeframes"], ["weekly"])


def _row(symbol: str, stage: str, score: int, volume_ratio: float, distance: float) -> dict:
    return {
        "symbol": symbol,
        "score": score,
        "rating": "A",
        "stage": stage,
        "actionable": True,
        "reasons": ["test"],
        "metrics": {
            "breakout_volume_ratio": volume_ratio,
            "distance_to_pivot_pct": distance,
            "recent_range_pct": 6.0,
            "base_drawdown_pct": 12.0,
            "vertical_gain_pct": 60.0,
            "latest_close": 100.0,
            "pivot": 100.0,
        },
    }


if __name__ == "__main__":
    unittest.main()
