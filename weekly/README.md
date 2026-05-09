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

## Recent correctness fixes

The weekly scanner received seven fixes in its most recent update. See the
top-level [`FIXES.md`](../FIXES.md) for full detail. Highlights specific
to weekly:

```text
1. Sort key. Matches are now ordered by a five-level trading-priority
   hierarchy: score -> stage tier (BO/EARLY > NEAR > FT) -> volume ->
   asymmetric distance bucket -> proximity. A confirmed BO at +1%
   correctly ranks above a NEAR at -1%. Score still dominates.
2. Retry. fetch_history retries empty/failed Yahoo frames up to 3 times
   with exponential backoff (0.75s, 1.5s). Silent drops from transient
   rate limiting are much rarer.
3. Reason string. The 50-MA reason reads "price is above the 50-week
   average" instead of "50-day average".
4. Atomic writes. results.json is written via .tmp + os.replace so
   Ctrl+C mid-write leaves the previous complete file intact.
5. Truncation surfaced. results.json now includes
   error_details_truncated (bool) and error_details_limit (25).
6. Dead locals. Unused highs/lows list-comprehensions were removed from
   analyze_five_star_setup. No behavior change.
```

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
- Writes `output/results.json` atomically (via a `.tmp` sibling + `os.replace`).
- Returns only actionable setups by default: near breakout, breakout today, or recent follow-through.
- Adds `early_entry` for clean weekly candidates before breakout. It requires a strong prior move,
  tight weekly base, volume dry-up, a strong close near the pivot, and no post-peak crash damage.
- Retries up to 3 Yahoo fetches per symbol on empty/failed responses
  (exponential backoff, ~2.25s worst case per stuck symbol). Reduces
  non-reproducibility when Yahoo rate-limits the full universe scan.

Weekly tuning:

- Base window: 26 weeks.
- Early entry must be within 2% below pivot.
- Recent weekly range must be 10% or tighter.
- Post-peak drawdown damage is checked over 45 weeks.

### Match ordering

Within `results.json`, matches are sorted by a five-level
trading-priority hierarchy:

```
1. score                    (higher wins)
2. stage tier               BO/EARLY (0) > NEAR (1) > FT (2)
3. breakout_volume_ratio    (higher wins)
4. distance bucket          asymmetric:
                              0%   to  +3%   best
                             -3%   to   0%   watch
                             +3%   to  +8%   later
                             extended       last
5. |distance_to_pivot_pct|  within-bucket tiebreaker (closer wins)
```

The asymmetric bucket captures the fact that a confirmed breakout
just above pivot is strictly better than one still below pivot, even
though both are "close" to the pivot in absolute terms. Score is
still the primary key, so a high-score FT will beat a low-score BO.

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

## Weekly Pine Script

Use this file on a TradingView `1W` chart:

```text
weekly/five_star_setup.pine
```

(Path is relative to the repo root.)

Default Pine display:

```text
Signal Mode = Early image only
Show Status Table = true
Show Current Status Label = true
Show Recent Signals = true
Show Historical Signals = false
Show BAD Signals = false
```

If the chart only shows lines, enable `Show Status Table` and `Show Recent Signals`. For debugging, set `Signal Mode = All actionable`; for full history, enable `Show Historical Signals`.

Marker meaning:

```text
EARLY = clean aggressive weekly entry near pivot
BO    = weekly breakout
FT    = weekly follow-through, already moving
NEAR  = watchlist/prepare only
BAD   = avoid
```

Best weekly use:

```text
Monthly EARLY/BO/NEAR + Weekly EARLY/BO = strong setup
Weekly EARLY/BO + Daily EARLY/BO        = strong timing
Weekly NEAR only                        = watchlist, not entry
```

## Scoring

The scanner scores each stock on:

- Price above key moving averages (50-week MA).
- Prior vertical move showing strong buying force.
- Controlled pause instead of a deep crash.
- Tight/contraction behavior in the base.
- Volume dry-up before the breakout area.
- Breakout, near-breakout, or fast follow-through behavior.
- Breakout volume confirmation.

Deep or wide bases are capped as `damaged_base` so they do not pass just because
the last candle jumps above an old pivot.

## How To Read Weekly Results

Important fields in `weekly/output/results.json`:

```text
stage
score
rating
metrics.distance_to_pivot_pct
metrics.breakout_volume_ratio
metrics.recent_range_pct
metrics.base_drawdown_pct
metrics.post_peak_drawdown_pct
```

Scanner-level fields at the top of `results.json`:

```text
total_requested
total_with_data
matches
errors
error_details            # up to 25 {symbol, error} entries
error_details_truncated  # true if total errors > 25
error_details_limit      # always 25 today
```

Use `overall/output/results.json` for final priority because it combines weekly with daily and monthly confirmation.

## Validate

The tests are offline and use synthetic candles shaped like the reference charts.

```bash
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/models.py src/universe.py src/data.py src/strategy.py src/scanner.py config/__init__.py config/settings.py tests/__init__.py tests/fixtures.py tests/test_strategy.py tests/test_universe.py tests/test_scanner.py
```

Current count: **10 / 10 tests pass**.
