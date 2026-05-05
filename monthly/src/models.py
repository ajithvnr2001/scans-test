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

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requested": self.total_requested,
            "total_with_data": self.total_with_data,
            "matches": len(self.matches),
            "errors": len(self.errors),
            "results": [match.to_dict() for match in self.matches],
            "error_details": list(self.errors[:25]),
        }

