from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen


NSE_EQUITY_LIST_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


class UniverseLoadError(RuntimeError):
    pass


def normalize_symbol(symbol: str) -> str:
    clean = symbol.strip().upper()
    if clean.endswith(".NS"):
        clean = clean[:-3]
    return clean


def to_yahoo_symbol(symbol: str) -> str:
    clean = normalize_symbol(symbol)
    if not clean:
        raise ValueError("empty symbol")
    return f"{clean}.NS"


def unique_yahoo_symbols(symbols: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw_symbol in symbols:
        symbol = to_yahoo_symbol(raw_symbol)
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
    return output


def parse_nse_equity_csv(content: str, allowed_series: tuple[str, ...] = ("EQ",)) -> list[str]:
    reader = csv.DictReader(content.splitlines())
    symbols: list[str] = []

    for row in reader:
        normalized_row = {key.strip().upper(): value.strip() for key, value in row.items() if key}
        symbol = normalized_row.get("SYMBOL")
        series = normalized_row.get("SERIES", "")

        if not symbol:
            continue
        if allowed_series and series.upper() not in allowed_series:
            continue

        symbols.append(symbol)

    if not symbols:
        raise UniverseLoadError("NSE equity CSV did not contain any matching symbols")

    return unique_yahoo_symbols(symbols)


def load_all_nse_symbols(
    source_url: str = NSE_EQUITY_LIST_URL,
    timeout: int = 20,
    allowed_series: tuple[str, ...] = ("EQ",),
) -> list[str]:
    request = Request(
        source_url,
        headers={
            "User-Agent": "Mozilla/5.0 NSE setup scanner",
            "Accept": "text/csv,*/*",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            content = response.read().decode("utf-8-sig")
    except (OSError, URLError) as exc:
        raise UniverseLoadError(f"Unable to load NSE symbol universe from {source_url}: {exc}") from exc

    return parse_nse_equity_csv(content, allowed_series=allowed_series)


def load_symbols_file(path: str | Path) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    symbols: list[str] = []

    for line in lines:
        clean = line.split("#", 1)[0].strip()
        if not clean:
            continue
        symbols.extend(part for part in clean.replace(",", " ").split() if part)

    if not symbols:
        raise UniverseLoadError(f"No symbols found in {path}")

    return unique_yahoo_symbols(symbols)

