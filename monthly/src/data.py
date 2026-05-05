from __future__ import annotations

from typing import Any

from src.models import Candle
from src.universe import normalize_symbol, to_yahoo_symbol


class DataProviderError(RuntimeError):
    pass


class YahooDataProvider:
    def __init__(
        self,
        period: str = "1y",
        interval: str = "1d",
        validate_symbols: bool = False,
    ) -> None:
        self.period = period
        self.interval = interval
        self.validate_symbols = validate_symbols

    def ensure_available(self) -> None:
        try:
            import yfinance  # noqa: F401
        except ModuleNotFoundError as exc:
            raise DataProviderError(
                "yfinance is not installed. Run `pip install -r requirements.txt` before live scans."
            ) from exc

    def fetch_history(self, symbol: str) -> list[Candle]:
        self.ensure_available()

        if self.validate_symbols and not is_valid_nse_symbol(symbol):
            return []

        import yfinance as yf

        yahoo_symbol = to_yahoo_symbol(symbol)
        try:
            frame = yf.download(
                yahoo_symbol,
                period=self.period,
                interval=self.interval,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:
            raise DataProviderError(f"{yahoo_symbol}: failed to fetch history: {exc}") from exc

        return dataframe_to_candles(frame)


def is_valid_nse_symbol(symbol: str) -> bool:
    try:
        from nsetools import Nse
    except ModuleNotFoundError:
        return True

    try:
        quote = Nse().get_quote(normalize_symbol(symbol))
    except Exception:
        return False

    return quote is not None


def dataframe_to_candles(frame: Any) -> list[Candle]:
    if frame is None or getattr(frame, "empty", True):
        return []

    data = frame.copy()
    if getattr(data.columns, "nlevels", 1) > 1:
        data.columns = [column[0] for column in data.columns]

    required = ("Open", "High", "Low", "Close", "Volume")
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise DataProviderError(f"history is missing columns: {', '.join(missing)}")

    data = data.loc[:, list(required)].dropna()
    candles: list[Candle] = []

    for index, row in data.iterrows():
        try:
            volume = float(row["Volume"])
            candles.append(
                Candle(
                    date=str(getattr(index, "date", lambda: index)()),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=volume,
                )
            )
        except (TypeError, ValueError):
            continue

    return candles

