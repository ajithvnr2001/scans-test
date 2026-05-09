from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Candle:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class SetupSignal:
    score: int
    rating: str
    stage: str
    actionable: bool
    reasons: tuple[str, ...]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StockScan:
    symbol: str
    signal: SetupSignal

    def to_dict(self) -> dict[str, Any]:
        payload = self.signal.to_dict()
        payload["symbol"] = self.symbol
        return payload


@dataclass(frozen=True)
class ScanSummary:
    total_requested: int
    total_with_data: int
    matches: tuple[StockScan, ...]
    errors: tuple[dict[str, str], ...]

    ERROR_DETAIL_LIMIT = 25

    def to_dict(self) -> dict[str, Any]:
        # error_details is capped to avoid bloating results.json when Yahoo
        # has a bad day. We surface the truncation explicitly so downstream
        # readers do not silently assume error_details contains every error.
        truncated = len(self.errors) > self.ERROR_DETAIL_LIMIT
        return {
            "total_requested": self.total_requested,
            "total_with_data": self.total_with_data,
            "matches": len(self.matches),
            "errors": len(self.errors),
            "results": [match.to_dict() for match in self.matches],
            "error_details": list(self.errors[: self.ERROR_DETAIL_LIMIT]),
            "error_details_truncated": truncated,
            "error_details_limit": self.ERROR_DETAIL_LIMIT,
        }

