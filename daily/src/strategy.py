from __future__ import annotations

from statistics import mean

from src.models import Candle, SetupSignal


MIN_CANDLES = 90
EARLY_MAX_BELOW_PIVOT = 0.01
EARLY_MAX_RECENT_RANGE = 0.08
EARLY_MAX_BASE_DRAWDOWN = 0.22


def analyze_five_star_setup(candles: list[Candle]) -> SetupSignal:
    candles = [candle for candle in candles if candle.close > 0 and candle.high > 0 and candle.low > 0]

    if len(candles) < MIN_CANDLES:
        return SetupSignal(
            score=0,
            rating="insufficient_data",
            stage="insufficient_data",
            actionable=False,
            reasons=(f"needs at least {MIN_CANDLES} daily candles",),
            metrics={"candles": len(candles)},
        )

    closes = [candle.close for candle in candles]
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    volumes = [candle.volume for candle in candles]

    latest = candles[-1]
    latest_close = latest.close
    ma20 = mean(closes[-20:])
    ma50 = mean(closes[-50:])
    vertical_gain = _best_prior_gain(closes[:-15], max_window=45)
    base = candles[-45:-1]
    base_high = max(candle.high for candle in base)
    base_low = min(candle.low for candle in base)
    base_range = _range_pct(base)
    recent_range = _range_pct(candles[-15:-1])
    c45 = _window_range_pct(candles, 45, exclude_latest=True)
    c25 = _window_range_pct(candles, 25, exclude_latest=True)
    c12 = _window_range_pct(candles, 12, exclude_latest=True)
    base_drawdown = (base_high - base_low) / base_high if base_high else 1.0
    damaged_base = base_drawdown > 0.33 or base_range > 0.45
    pivot = base_high
    distance_to_pivot = (latest_close - pivot) / pivot if pivot else -1.0
    volume_20 = mean(volumes[-21:-1])
    recent_base_volume = mean(volumes[-11:-1])
    prior_base_volume = mean(volumes[-31:-11])
    breakout_volume_ratio = latest.volume / volume_20 if volume_20 else 0.0
    stage, days_since_breakout, breakout_pivot = _breakout_stage(candles)
    strong_close = (latest.close - latest.low) / (latest.high - latest.low) >= 0.65 if latest.high > latest.low else True

    score = 0
    reasons: list[str] = []

    if latest_close > ma50 and ma20 >= ma50 * 0.98:
        score += 1
        reasons.append("price is above the 50-day average")

    if vertical_gain >= 0.40:
        score += 3
        reasons.append("vertical move shows strong buying force")
    elif vertical_gain >= 0.25:
        score += 2
        reasons.append("vertical move is present")

    if base_drawdown <= 0.28 and latest_close >= base_low * 1.08:
        score += 1
        reasons.append("pause is controlled rather than a crash")

    contracting = c45 > c25 * 1.03 and c25 >= c12 * 0.95 and c12 <= 0.18
    tight = recent_range <= 0.14 and latest_close >= ma20 * 0.98
    if contracting or tight:
        score += 2
        reasons.append("recent price action is tight and controlled")

    volume_dry_up = recent_base_volume < prior_base_volume * 0.90
    if volume_dry_up:
        score += 1
        reasons.append("base volume dried up before the breakout area")

    if stage == "breakout_today":
        score += 2
        reasons.append("price is breaking out now instead of sitting in the middle")
    elif stage == "near_breakout":
        score += 1
        reasons.append("price is within 2 percent of the breakout pivot")
    elif stage == "follow_through":
        score += 1
        reasons.append("recent breakout is following through quickly")

    if stage in {"breakout_today", "follow_through", "extended"} and breakout_volume_ratio >= 1.40:
        score += 1
        reasons.append("breakout volume confirms demand")

    if stage == "follow_through" and days_since_breakout <= 8 and latest_close >= breakout_pivot * 1.05:
        score += 1
        reasons.append("post-breakout move is working fast")

    early_entry = (
        stage == "near_breakout"
        and score >= 8
        and vertical_gain >= 0.40
        and volume_dry_up
        and recent_range <= EARLY_MAX_RECENT_RANGE
        and base_drawdown <= EARLY_MAX_BASE_DRAWDOWN
        and latest_close >= pivot * (1 - EARLY_MAX_BELOW_PIVOT)
        and latest_close > latest.open
        and strong_close
    )

    if early_entry:
        stage = "early_entry"
        reasons.append("strict daily early-entry candidate near pivot")

    if damaged_base:
        score = min(score, 5)
        stage = "damaged_base"
        reasons.append("base is too deep to count as a pause")

    actionable = stage in {"early_entry", "near_breakout", "breakout_today", "follow_through"} and not damaged_base

    metrics = {
        "candles": len(candles),
        "latest_close": round(latest_close, 4),
        "ma20": round(ma20, 4),
        "ma50": round(ma50, 4),
        "vertical_gain_pct": round(vertical_gain * 100, 2),
        "base_range_pct": round(base_range * 100, 2),
        "recent_range_pct": round(recent_range * 100, 2),
        "base_drawdown_pct": round(base_drawdown * 100, 2),
        "pivot": round(pivot, 4),
        "distance_to_pivot_pct": round(distance_to_pivot * 100, 2),
        "breakout_volume_ratio": round(breakout_volume_ratio, 2),
        "days_since_breakout": days_since_breakout,
    }

    return SetupSignal(
        score=score,
        rating=_rating(score),
        stage=stage,
        actionable=actionable,
        reasons=tuple(reasons),
        metrics=metrics,
    )


def _best_prior_gain(closes: list[float], max_window: int) -> float:
    if len(closes) < 2:
        return 0.0

    best = 0.0
    for end in range(1, len(closes)):
        start = max(0, end - max_window)
        prior_low = min(closes[start:end])
        if prior_low <= 0:
            continue
        best = max(best, (closes[end] - prior_low) / prior_low)

    return best


def _range_pct(candles: list[Candle]) -> float:
    if not candles:
        return 1.0

    low = min(candle.low for candle in candles)
    high = max(candle.high for candle in candles)
    if low <= 0:
        return 1.0

    return (high - low) / low


def _window_range_pct(candles: list[Candle], window: int, exclude_latest: bool) -> float:
    end = -1 if exclude_latest else None
    selected = candles[-window:end]
    return _range_pct(selected)


def _breakout_stage(candles: list[Candle]) -> tuple[str, int, float]:
    closes = [candle.close for candle in candles]
    highs = [candle.high for candle in candles]
    latest_close = closes[-1]
    pivot = max(highs[-45:-1])

    first_breakout_index = None
    first_breakout_pivot = pivot
    start = max(45, len(candles) - 12)

    for index in range(start, len(candles)):
        rolling_pivot = max(highs[index - 45 : index])
        if closes[index] >= rolling_pivot * 1.005:
            first_breakout_index = index
            first_breakout_pivot = rolling_pivot
            break

    if first_breakout_index is None:
        if latest_close >= pivot * 0.98:
            return "near_breakout", 0, pivot
        return "base", 0, pivot

    days_since_breakout = len(candles) - 1 - first_breakout_index
    extension = latest_close / first_breakout_pivot if first_breakout_pivot else 0.0

    if days_since_breakout == 0:
        return "breakout_today", 0, first_breakout_pivot
    if days_since_breakout <= 10 and extension <= 1.25:
        return "follow_through", days_since_breakout, first_breakout_pivot
    return "extended", days_since_breakout, first_breakout_pivot


def _rating(score: int) -> str:
    if score >= 10:
        return "A+"
    if score >= 8:
        return "A"
    if score >= 6:
        return "B"
    return "C"
