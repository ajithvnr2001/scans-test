from __future__ import annotations

from src.models import Candle


def five_star_breakout_candles(
    *,
    latest_close: float = 166.0,
    latest_volume: float = 4200.0,
    crash_base: bool = False,
) -> list[Candle]:
    candles: list[Candle] = []
    day = 1

    for index in range(45):
        close = 100.0 + (index % 5 - 2) * 0.25
        candles.append(_candle(day, close, close + 1.0, close - 1.0, 900 + index * 2))
        day += 1

    for index in range(25):
        close = 103.0 + index * 2.35
        candles.append(_candle(day, close, close * 1.025, close * 0.985, 2200 + index * 50))
        day += 1

    if crash_base:
        for index in range(44):
            close = 158.0 - index * 1.1
            candles.append(_candle(day, close, close + 3.0, close - 12.0, 1200 - index * 8))
            day += 1
    else:
        for index in range(44):
            if index < 16:
                center = 153.0
                amplitude = 8.0 - index * 0.18
            elif index < 32:
                center = 156.0
                amplitude = 4.4 - (index - 16) * 0.08
            else:
                center = 157.0
                amplitude = 2.0 - (index - 32) * 0.04

            close = center + (0.35 if index % 2 == 0 else -0.35)
            volume = 1250.0 - index * 18.0
            candles.append(_candle(day, close, center + amplitude, center - amplitude, volume))
            day += 1

    candles.append(_candle(day, latest_close, latest_close + 2.0, latest_close - 5.0, latest_volume))
    return candles


def _candle(day: int, close: float, high: float, low: float, volume: float) -> Candle:
    return Candle(
        date=f"2026-01-{day:03d}",
        open=close * 0.995,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )

