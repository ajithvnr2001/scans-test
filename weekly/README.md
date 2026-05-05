# NSE Weekly 5-Star Setup Scanner

This is the organized weekly timeframe scanner. It is a sibling of `daily/` and `monthly/`.

This repo scans NSE stocks for the chart pattern shown in the reference images:

1. Vertical move first.
2. Pause, not a crash.
3. Tight controlled price action.
4. Volume confirmation.
5. Buy the breakout, not the middle.
6. Do not sell too early.
7. Strong setups work fast, or they fail.

The important change is that the scanner now defaults to the full NSE equity universe.
It does not use a hard-coded single stock or fixed group of stocks.

## Project Structure

```text
.
├── config/
│   └── settings.py
├── output/
├── src/
│   ├── data.py
│   ├── models.py
│   ├── scanner.py
│   ├── strategy.py
│   └── universe.py
├── tests/
├── requirements.txt
└── run.py
```

## Install

```bash
pip install -r requirements.txt
```

`yfinance` is required for live OHLC data. `nsetools` is optional and is only used
when `--validate-symbols` is passed.

## Run A Full NSE Scan

```bash
python run.py
```

Default behavior:

- Loads all NSE `EQ` series symbols from the NSE equity list.
- Converts them to Yahoo symbols such as `RELIANCE.NS`.
- Downloads 5 years of weekly candles by default: `period=5y`, `interval=1wk`.
- Scores every stock in parallel. Worker count is automatic:
  `min(64, max(10, CPU threads * 8))`.
- Writes `output/results.json`.
- Returns only actionable setups by default: near breakout, breakout today, or recent follow-through.
- Adds `early_entry` for clean weekly candidates before breakout. It requires a strong prior move,
  tight weekly base, volume dry-up, a strong close near the pivot, and no post-peak crash damage.

Weekly tuning:

- Base window: 26 weeks.
- Early entry must be within 2% below pivot.
- Recent weekly range must be 10% or tighter.
- Post-peak drawdown damage is checked over 45 weeks.

## Useful Commands

Dry-run the full universe without downloading price data:

```bash
python run.py --dry-run
```

Scan only specific symbols:

```bash
python run.py --universe symbols --symbols "RELIANCE,TCS,HEG"
```

Scan symbols from a file:

```bash
python run.py --universe file --symbols-file symbols.txt
```

Include high-scoring bases that are not yet near breakout:

```bash
python run.py --include-watchlist
```

Use a smaller development sample:

```bash
python run.py --limit 50
```

Override parallel workers manually:

```bash
python run.py --max-workers 32
```

## Scoring

The scanner scores each stock on:

- Price above key moving averages.
- Prior vertical move showing strong buying force.
- Controlled pause instead of a deep crash.
- Tight/contraction behavior in the base.
- Volume dry-up before the breakout area.
- Breakout, near-breakout, or fast follow-through behavior.
- Breakout volume confirmation.

Deep or wide bases are capped as `damaged_base` so they do not pass just because
the last candle jumps above an old pivot.

## Validate

The tests are offline and use synthetic candles shaped like the reference charts.

```bash
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/models.py src/universe.py src/data.py src/strategy.py src/scanner.py config/__init__.py config/settings.py tests/__init__.py tests/fixtures.py tests/test_strategy.py tests/test_universe.py tests/test_scanner.py
```
