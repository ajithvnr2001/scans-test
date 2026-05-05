from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TIMEFRAME_WEIGHTS = {
    "monthly": 1.35,
    "weekly": 1.25,
    "daily": 1.00,
}

STAGE_WEIGHTS = {
    "breakout_today": 55,
    "early_entry": 52,
    "follow_through": 42,
    "near_breakout": 25,
    "base": 8,
    "damaged_base": -100,
    "insufficient_data": -100,
}

ENTRY_STAGES = {"early_entry", "breakout_today", "follow_through"}
CONFIRMED_ENTRY_STAGES = {"early_entry", "breakout_today"}
MAX_ENTRY_EXTENSION = {
    "daily": 5.0,
    "weekly": 6.0,
    "monthly": 8.0,
}
MAX_CLEAN_RECENT_RANGE = {
    "daily": 22.0,
    "weekly": 25.0,
    "monthly": 25.0,
}
MAX_CLEAN_BASE_DRAWDOWN = {
    "daily": 30.0,
    "weekly": 30.0,
    "monthly": 34.0,
}
MIN_CONFIRMING_VOLUME = 1.40


@dataclass(frozen=True)
class TimeframeResult:
    timeframe: str
    symbol: str
    score: int
    rating: str
    stage: str
    actionable: bool
    reasons: tuple[str, ...]
    metrics: dict[str, Any]

    @classmethod
    def from_payload(cls, timeframe: str, payload: dict[str, Any]) -> "TimeframeResult":
        return cls(
            timeframe=timeframe,
            symbol=str(payload["symbol"]),
            score=int(payload.get("score", 0)),
            rating=str(payload.get("rating", "C")),
            stage=str(payload.get("stage", "")),
            actionable=bool(payload.get("actionable", False)),
            reasons=tuple(str(reason) for reason in payload.get("reasons", ())),
            metrics=dict(payload.get("metrics", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "score": self.score,
            "rating": self.rating,
            "stage": self.stage,
            "actionable": self.actionable,
            "reasons": list(self.reasons),
            "metrics": self.metrics,
        }


def combine_timeframe_outputs(
    outputs: dict[str, dict[str, Any]],
    *,
    min_overall_score: float = 85.0,
    include_near_only: bool = False,
    min_technical_upside_pct: float | None = None,
    min_timeframes: int = 1,
    require_weekly: bool = False,
    require_monthly: bool = False,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[TimeframeResult]] = {}

    for timeframe, output in outputs.items():
        for row in output.get("results", []):
            result = TimeframeResult.from_payload(timeframe, row)
            grouped.setdefault(result.symbol, []).append(result)

    candidates = [
        _score_symbol(symbol, results, include_near_only=include_near_only)
        for symbol, results in grouped.items()
    ]
    filtered = [
        candidate
        for candidate in candidates
        if candidate["overall_score"] >= min_overall_score
        and (include_near_only or candidate["high_probability"])
        and candidate["timeframe_count"] >= min_timeframes
        and (not require_weekly or candidate["has_weekly"])
        and (not require_monthly or candidate["has_monthly"])
        and (
            min_technical_upside_pct is None
            or candidate["technical_upside_pct"] >= min_technical_upside_pct
        )
    ]
    filtered.sort(
        key=lambda row: (
            row["overall_score"],
            row["timeframe_count"],
            row["has_monthly"],
            row["has_weekly"],
            row["technical_upside_pct"],
            row["best_single_score"],
        ),
        reverse=True,
    )
    return filtered


def _score_symbol(
    symbol: str,
    results: list[TimeframeResult],
    *,
    include_near_only: bool,
) -> dict[str, Any]:
    results = sorted(results, key=lambda item: _timeframe_rank(item.timeframe), reverse=True)
    has_entry_stage = any(result.stage in ENTRY_STAGES for result in results)
    has_confirmed_entry = any(result.stage in CONFIRMED_ENTRY_STAGES for result in results)
    has_clean_entry = any(_is_clean_entry(result) for result in results)
    has_confirming_volume = any(_has_confirming_volume(result) for result in results)
    has_monthly = any(result.timeframe == "monthly" for result in results)
    has_weekly = any(result.timeframe == "weekly" for result in results)
    has_daily = any(result.timeframe == "daily" for result in results)
    multi_timeframe = len(results) >= 2
    high_probability = _is_high_probability(
        results,
        has_clean_entry=has_clean_entry,
        has_confirming_volume=has_confirming_volume,
        include_near_only=include_near_only,
    )
    upside_by_timeframe = {
        result.timeframe: round(_technical_upside_pct(result), 2)
        for result in results
    }
    best_upside_timeframe = max(upside_by_timeframe, key=upside_by_timeframe.get)

    score = 0.0
    for result in results:
        tf_weight = TIMEFRAME_WEIGHTS.get(result.timeframe, 1.0)
        score += result.score * 6.0 * tf_weight
        score += STAGE_WEIGHTS.get(result.stage, 0) * tf_weight
        score += _metric_bonus(result) * tf_weight
        score += _cleanliness_adjustment(result) * tf_weight

    if has_monthly and has_weekly:
        score += 45
    if has_weekly and has_daily:
        score += 30
    if has_monthly and has_weekly and has_daily:
        score += 35
    if any(result.stage == "early_entry" for result in results):
        score += 24
    if any(result.stage == "breakout_today" for result in results):
        score += 28
    if has_clean_entry:
        score += 28
    if has_confirming_volume:
        score += 18
    if not multi_timeframe:
        score -= 25
    if not has_entry_stage and not include_near_only:
        score -= 200
    if not high_probability and not include_near_only:
        score -= 120

    best = max(results, key=lambda item: (_stage_rank(item.stage), item.score))
    return {
        "symbol": symbol,
        "overall_score": round(score, 2),
        "confirmation": _confirmation(score, results, has_entry_stage),
        "best_stage": best.stage,
        "best_timeframe": best.timeframe,
        "entry_plan": _entry_plan(results),
        "pine_confirmation": _pine_confirmation(results),
        "technical_upside_pct": upside_by_timeframe[best_upside_timeframe],
        "best_upside_timeframe": best_upside_timeframe,
        "upside_by_timeframe": upside_by_timeframe,
        "has_entry_stage": has_entry_stage,
        "has_confirmed_entry": has_confirmed_entry,
        "has_clean_entry": has_clean_entry,
        "has_confirming_volume": has_confirming_volume,
        "high_probability": high_probability,
        "has_monthly": has_monthly,
        "has_weekly": has_weekly,
        "has_daily": has_daily,
        "timeframe_count": len(results),
        "best_single_score": max(result.score for result in results),
        "timeframes": {result.timeframe: result.to_dict() for result in results},
    }


def _metric_bonus(result: TimeframeResult) -> float:
    metrics = result.metrics
    bonus = 0.0
    distance = abs(float(metrics.get("distance_to_pivot_pct", 100.0)))
    volume_ratio = float(metrics.get("breakout_volume_ratio", 0.0))
    recent_range = float(metrics.get("recent_range_pct", 100.0))
    base_drawdown = float(metrics.get("base_drawdown_pct", 100.0))

    bonus += max(0.0, 12.0 - distance * 2.0)
    bonus += min(volume_ratio, 3.0) * 4.0
    bonus += max(0.0, 14.0 - recent_range) * 0.8
    bonus += max(0.0, 28.0 - base_drawdown) * 0.4
    bonus += min(max(_technical_upside_pct(result), 0.0), 25.0) * 0.35
    return bonus


def _technical_upside_pct(result: TimeframeResult) -> float:
    metrics = result.metrics
    latest_close = float(metrics.get("latest_close", 0.0))
    pivot = float(metrics.get("pivot", 0.0))
    base_drawdown_pct = float(metrics.get("base_drawdown_pct", 0.0))

    if latest_close <= 0 or pivot <= 0 or base_drawdown_pct <= 0:
        return 0.0

    measured_target = pivot * (1.0 + base_drawdown_pct / 100.0)
    return ((measured_target - latest_close) / latest_close) * 100.0


def _cleanliness_adjustment(result: TimeframeResult) -> float:
    metrics = result.metrics
    adjustment = 0.0
    distance = float(metrics.get("distance_to_pivot_pct", 100.0))
    volume_ratio = float(metrics.get("breakout_volume_ratio", 0.0))
    recent_range = float(metrics.get("recent_range_pct", 100.0))
    base_drawdown = float(metrics.get("base_drawdown_pct", 100.0))

    if result.stage == "breakout_today" and distance > MAX_ENTRY_EXTENSION.get(result.timeframe, 5.0):
        adjustment -= 28
    if result.stage == "breakout_today" and volume_ratio < MIN_CONFIRMING_VOLUME:
        adjustment -= 22
    if recent_range > MAX_CLEAN_RECENT_RANGE.get(result.timeframe, 22.0):
        adjustment -= 18
    if base_drawdown > MAX_CLEAN_BASE_DRAWDOWN.get(result.timeframe, 30.0):
        adjustment -= 18
    if result.stage == "follow_through" and volume_ratio < 0.75:
        adjustment -= 12

    return adjustment


def _is_clean_entry(result: TimeframeResult) -> bool:
    if result.stage not in ENTRY_STAGES:
        return False

    metrics = result.metrics
    distance = float(metrics.get("distance_to_pivot_pct", 100.0))
    recent_range = float(metrics.get("recent_range_pct", 100.0))
    base_drawdown = float(metrics.get("base_drawdown_pct", 100.0))

    if recent_range > MAX_CLEAN_RECENT_RANGE.get(result.timeframe, 22.0):
        return False
    if base_drawdown > MAX_CLEAN_BASE_DRAWDOWN.get(result.timeframe, 30.0):
        return False
    if result.stage == "breakout_today" and distance > MAX_ENTRY_EXTENSION.get(result.timeframe, 5.0):
        return False

    return True


def _has_confirming_volume(result: TimeframeResult) -> bool:
    if result.stage == "early_entry":
        return True
    if result.stage not in ENTRY_STAGES:
        return False
    return float(result.metrics.get("breakout_volume_ratio", 0.0)) >= MIN_CONFIRMING_VOLUME


def _is_high_probability(
    results: list[TimeframeResult],
    *,
    has_clean_entry: bool,
    has_confirming_volume: bool,
    include_near_only: bool,
) -> bool:
    if include_near_only:
        return True
    if not has_clean_entry:
        return False
    if not has_confirming_volume:
        return False

    stages = {result.timeframe: result.stage for result in results}
    clean_timeframes = {result.timeframe for result in results if _is_clean_entry(result)}

    if stages.get("monthly") in ENTRY_STAGES and stages.get("weekly") in {"near_breakout", *ENTRY_STAGES}:
        return True
    if stages.get("weekly") in ENTRY_STAGES and stages.get("daily") in {"near_breakout", *ENTRY_STAGES}:
        return True
    if "weekly" in clean_timeframes and len(results) >= 2:
        return True

    single = results[0] if len(results) == 1 else None
    return bool(
        single
        and single.stage in CONFIRMED_ENTRY_STAGES
        and single.score >= 10
        and _has_confirming_volume(single)
        and _is_clean_entry(single)
    )


def _entry_plan(results: list[TimeframeResult]) -> str:
    stages = {result.timeframe: result.stage for result in results}

    if stages.get("monthly") in ENTRY_STAGES and stages.get("weekly") in ENTRY_STAGES:
        return "Highest probability: monthly and weekly both confirm entry; use daily for timing/add."
    if stages.get("weekly") in ENTRY_STAGES and stages.get("daily") in ENTRY_STAGES:
        return "Strong timing combo: weekly entry plus daily entry/follow-through confirmation."
    if stages.get("monthly") == "early_entry" and stages.get("weekly") in {"near_breakout", "early_entry", "breakout_today"}:
        return "Clean position-building combo: monthly early with weekly near/entry."
    if any(stage == "breakout_today" for stage in stages.values()):
        return "Confirmed entry: breakout signal is active; check volume and risk."
    if any(stage == "follow_through" for stage in stages.values()):
        return "Follow-through entry: already moving; prefer pullback/risk-controlled entry."
    if any(stage == "early_entry" for stage in stages.values()):
        return "Aggressive early entry only; keep size smaller until breakout confirms."
    return "Watchlist only: wait for EARLY or BO confirmation."


def _pine_confirmation(results: list[TimeframeResult]) -> list[str]:
    paths = {
        "daily": "daily/five_star_setup.pine on 1D chart",
        "weekly": "weekly/five_star_setup.pine on 1W chart",
        "monthly": "monthly/five_star_setup.pine on 1M chart",
    }
    priority = {"monthly": 3, "weekly": 2, "daily": 1}
    instructions: list[str] = []

    for result in sorted(results, key=lambda item: priority.get(item.timeframe, 0), reverse=True):
        marker = {
            "early_entry": "EARLY",
            "breakout_today": "BO",
            "follow_through": "FT",
            "near_breakout": "NEAR",
        }.get(result.stage, result.stage.upper())
        instructions.append(f"{paths[result.timeframe]}: look for {marker}")

    return instructions


def _confirmation(score: float, results: list[TimeframeResult], has_entry_stage: bool) -> str:
    timeframes = {result.timeframe for result in results}
    if score >= 210 and {"monthly", "weekly"}.issubset(timeframes) and has_entry_stage:
        return "A+ multi-timeframe confirmation"
    if score >= 160 and has_entry_stage:
        return "A confirmation"
    if score >= 115 and has_entry_stage:
        return "B confirmation"
    return "watchlist"


def _timeframe_rank(timeframe: str) -> int:
    return {"monthly": 3, "weekly": 2, "daily": 1}.get(timeframe, 0)


def _stage_rank(stage: str) -> int:
    return {
        "breakout_today": 5,
        "early_entry": 4,
        "follow_through": 3,
        "near_breakout": 2,
        "base": 1,
    }.get(stage, 0)
