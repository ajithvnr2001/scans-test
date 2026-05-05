from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.ranker import combine_timeframe_outputs


ROOT = Path(__file__).resolve().parents[1]
TIMEFRAMES = {
    "daily": ROOT / "daily",
    "weekly": ROOT / "weekly",
    "monthly": ROOT / "monthly",
}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = Path(args.input_dir) if args.input_dir else output_dir
    if not input_dir.is_absolute():
        input_dir = Path.cwd() / input_dir

    timeframe_outputs = (
        load_existing_outputs(input_dir)
        if args.combine_only
        else run_timeframe_scans(args, output_dir)
    )
    candidates = combine_timeframe_outputs(
        timeframe_outputs,
        min_overall_score=args.min_overall_score,
        include_near_only=args.include_near_only,
        min_technical_upside_pct=args.min_technical_upside,
        min_timeframes=args.min_timeframes,
        require_weekly=args.require_weekly,
        require_monthly=args.require_monthly,
    )

    payload = {
        "mode": "combine_only" if args.combine_only else "scan_and_combine",
        "input_dir": str(input_dir) if args.combine_only else None,
        "output_dir": str(output_dir),
        "min_overall_score": args.min_overall_score,
        "include_near_only": args.include_near_only,
        "filters": {
            "min_technical_upside_pct": args.min_technical_upside,
            "min_timeframes": args.min_timeframes,
            "require_weekly": args.require_weekly,
            "require_monthly": args.require_monthly,
        },
        "pine_scripts": {
            "daily": "../daily/five_star_setup.pine on TradingView 1D chart",
            "weekly": "../weekly/five_star_setup.pine on TradingView 1W chart",
            "monthly": "../monthly/five_star_setup.pine on TradingView 1M chart",
        },
        "timeframes": {
            timeframe: {
                "total_requested": output.get("total_requested", 0),
                "total_with_data": output.get("total_with_data", 0),
                "matches": output.get("matches", 0),
                "errors": output.get("errors", 0),
            }
            for timeframe, output in timeframe_outputs.items()
        },
        "matches": len(candidates),
        "results": candidates[: args.top],
    }

    output_path = output_dir / "results.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily/weekly/monthly scans and rank best confirmations.")
    parser.add_argument("--symbols", default="", help="Comma or space separated symbols for all scans.")
    parser.add_argument("--symbols-file", default="", help="Symbols file to pass to all scans.")
    parser.add_argument("--limit", type=int, default=None, help="Development limit for all scans.")
    parser.add_argument("--max-workers", type=int, default=None, help="Worker override for all scans.")
    parser.add_argument("--min-score", type=int, default=7, help="Minimum score inside each timeframe scan.")
    parser.add_argument("--min-overall-score", type=float, default=85.0, help="Minimum combined score.")
    parser.add_argument(
        "--min-technical-upside",
        type=float,
        default=None,
        help="Minimum estimated measured-move upside percent from any confirming timeframe.",
    )
    parser.add_argument(
        "--min-timeframes",
        type=int,
        default=1,
        help="Minimum number of matching timeframes required in the combined result.",
    )
    parser.add_argument("--require-weekly", action="store_true", help="Require weekly confirmation.")
    parser.add_argument("--require-monthly", action="store_true", help="Require monthly confirmation.")
    parser.add_argument("--include-near-only", action="store_true", help="Allow candidates that are only NEAR.")
    parser.add_argument("--combine-only", action="store_true", help="Do not scan; combine existing output JSON files.")
    parser.add_argument(
        "--input-dir",
        default="",
        help="When --combine-only is used, read daily/weekly/monthly JSON from this directory.",
    )
    parser.add_argument("--output-dir", default="output", help="Output directory for timeframe and combined JSON.")
    parser.add_argument("--top", type=int, default=100, help="Maximum combined rows to print/write.")
    return parser.parse_args()


def run_timeframe_scans(args: argparse.Namespace, output_dir: Path) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}

    for timeframe, cwd in TIMEFRAMES.items():
        output_path = output_dir / f"{timeframe}.json"
        cmd = [sys.executable, "run.py", "--output", str(output_path), "--min-score", str(args.min_score)]

        if args.symbols:
            cmd.extend(["--universe", "symbols", "--symbols", args.symbols])
        elif args.symbols_file:
            cmd.extend(["--universe", "file", "--symbols-file", args.symbols_file])

        if args.limit is not None:
            cmd.extend(["--limit", str(args.limit)])
        if args.max_workers is not None:
            cmd.extend(["--max-workers", str(args.max_workers)])

        completed = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise SystemExit(
                f"{timeframe} scan failed with exit code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        outputs[timeframe] = read_json(output_path)

    return outputs


def load_existing_outputs(output_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        timeframe: read_json(output_dir / f"{timeframe}.json")
        for timeframe in TIMEFRAMES
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing output file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
