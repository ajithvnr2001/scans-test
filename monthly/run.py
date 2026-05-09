from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from config.settings import (
    DEFAULT_INTERVAL,
    DEFAULT_MIN_SCORE,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PERIOD,
    cpu_thread_count,
    default_max_workers,
)
from src.data import YahooDataProvider
from src.scanner import run_scan
from src.universe import load_all_nse_symbols, load_symbols_file, unique_yahoo_symbols


def main() -> None:
    args = parse_args()
    symbols = resolve_symbols(args)
    max_workers = args.max_workers or default_max_workers()

    if args.limit is not None:
        symbols = symbols[: args.limit]

    if args.dry_run:
        payload = {
            "universe": args.universe,
            "total_symbols": len(symbols),
            "cpu_threads": cpu_thread_count(),
            "max_workers": max_workers,
            "symbols": symbols[:50],
        }
        print(json.dumps(payload, indent=2))
        return

    provider = YahooDataProvider(
        period=args.period,
        interval=args.interval,
        validate_symbols=args.validate_symbols,
    )
    provider.ensure_available()

    summary = run_scan(
        symbols,
        provider=provider,
        min_score=args.min_score,
        max_workers=max_workers,
        actionable_only=not args.include_watchlist,
    )

    payload = {
        "universe": args.universe,
        "min_score": args.min_score,
        "cpu_threads": cpu_thread_count(),
        "max_workers": max_workers,
        "actionable_only": not args.include_watchlist,
        **summary.to_dict(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to a temp file next to the target, then rename.
    # This guarantees results.json is either the previous complete file or
    # the new complete file, never a half-written one (e.g. after Ctrl+C).
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, output_path)

    print(json.dumps(payload, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan NSE stocks for the 5-star breakout setup.")
    parser.add_argument(
        "--universe",
        choices=("all", "symbols", "file"),
        default="all",
        help="Default is all NSE EQ-series stocks.",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma or space separated NSE symbols. Used with --universe symbols.",
    )
    parser.add_argument(
        "--symbols-file",
        default="",
        help="File containing symbols separated by newlines, commas, or spaces.",
    )
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Parallel download workers. Default is auto: min(64, max(10, CPU threads * 8)).",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--include-watchlist",
        action="store_true",
        help="Include high-scoring bases that are not yet near breakout.",
    )
    parser.add_argument(
        "--validate-symbols",
        action="store_true",
        help="Use nsetools quote validation before downloading history.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Development/testing limit. Omit this for the full stock universe.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and print the symbol universe without downloading price data.",
    )
    return parser.parse_args()


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    if args.universe == "symbols":
        if not args.symbols:
            raise SystemExit("--symbols is required when --universe symbols is used")
        return unique_yahoo_symbols(args.symbols.replace(",", " ").split())

    if args.universe == "file":
        if not args.symbols_file:
            raise SystemExit("--symbols-file is required when --universe file is used")
        return load_symbols_file(args.symbols_file)

    return load_all_nse_symbols()


if __name__ == "__main__":
    main()
