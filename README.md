# NSE 5-Star Multi-Timeframe Scanner

This workspace contains four scanners for the chart setup shown in the reference images:

1. Strong vertical move first.
2. Pause, not a crash.
3. Tight controlled price action.
4. Volume confirmation.
5. Buy the breakout or strict early entry, not the middle of the base.
6. Hold winners by rules instead of selling too early.
7. Strong setups work fast; weak ones fail or become avoid/watchlist names.

The scanner is built for all NSE `EQ` stocks by default. It is not hard-coded to one stock or a small symbol group.

## Folder Map

```text
scans-test/
├── daily/                  # Daily 1D scanner and daily Pine script
│   ├── config/settings.py
│   ├── five_star_setup.pine
│   ├── output/
│   ├── src/
│   ├── tests/
│   └── run.py
├── weekly/                 # Weekly 1W scanner and weekly Pine script
│   ├── five_star_setup.pine
│   ├── output/
│   ├── src/
│   ├── tests/
│   └── run.py
├── monthly/                # Monthly 1M scanner and monthly Pine script
│   ├── five_star_setup.pine
│   ├── output/
│   ├── src/
│   ├── tests/
│   └── run.py
├── overall/                # Combines daily + weekly + monthly results
│   ├── output/
│   ├── src/ranker.py
│   ├── tests/
│   └── run.py
├── FIXES.md                # Detailed weekly/monthly correctness fix notes
├── requirements.txt
└── README.md
```

> All paths below are shown relative to the repo root. On your machine the
> repo may live anywhere; use your actual checkout path as the starting
> directory for the commands.

## Recent Correctness Fixes (weekly + monthly)

The weekly and monthly scanners received seven targeted correctness and
robustness fixes. See [`FIXES.md`](./FIXES.md) for in-depth reasoning,
diffs, and validation evidence. Summary:

| # | What changed | Where |
|---|--------------|-------|
| 1 | Sort key no longer ranks extended breakouts above near-pivot setups. Score still dominates; proximity tie-breaks on ties. | `weekly/src/scanner.py`, `monthly/src/scanner.py` |
| 2 | `yf.download` now retries up to 3 times with exponential backoff (0.75s, 1.5s) on empty or failed responses. Reduces silent drops from transient Yahoo rate limiting. | `weekly/src/data.py`, `monthly/src/data.py` |
| 3 | 50-MA reason string reads `"50-week average"` on weekly and `"50-month average"` on monthly (previously always said `"50-day"`). | `weekly/src/strategy.py`, `monthly/src/strategy.py` |
| 4 | `results.json` is now written atomically via a `.tmp` file + `os.replace`. Ctrl+C mid-write no longer corrupts the file. | `weekly/run.py`, `monthly/run.py` |
| 5 | `error_details` truncation (previously silent at 25 rows) is now surfaced via `error_details_truncated` and `error_details_limit` fields. | `weekly/src/models.py`, `monthly/src/models.py` |
| 6 | Unused `highs` / `lows` locals removed from `analyze_five_star_setup`. Pure cleanup, no behavior change. | `weekly/src/strategy.py`, `monthly/src/strategy.py` |
| 7 | Ranking upgraded to a five-level trading-priority hierarchy: **score → stage tier (BO/EARLY > NEAR > FT) → volume → asymmetric distance bucket → proximity**. A confirmed BO at +1% now correctly ranks above a NEAR at -1%. | `weekly/src/scanner.py`, `monthly/src/scanner.py` |

All 35 unit tests pass and targeted end-to-end validation covers each fix.

## Install

From the workspace root:

```bash
python -m pip install -r requirements.txt
```

`yfinance` is required for live OHLC data. `nsetools` is optional and is only used when `--validate-symbols` is passed.

## Best Run Order

Use this order when scanning seriously:

```bash
cd overall
python run.py --output-dir output
```

That command runs all three timeframe scanners and writes:

```text
overall/output/daily.json
overall/output/weekly.json
overall/output/monthly.json
overall/output/results.json
```

For a clean rerun from scratch, remove old JSON output first:

```bash
find daily/output weekly/output monthly/output overall/output -type f -name '*.json' -delete
cd overall
python run.py --output-dir output
```

Then rerank the already scanned data using stricter upside and timeframe filters:

```bash
python run.py --combine-only --input-dir output --output-dir output/weekly-upside --min-timeframes 2 --require-weekly --min-technical-upside 8
```

Reference-image early setup list:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image --early-image-only --min-timeframes 1 --min-technical-upside 8
```

Weekly-supported early setup list:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image-weekly --early-image-only --require-weekly --min-timeframes 1 --min-technical-upside 8
```

Very strict version:

```bash
python run.py --combine-only --input-dir output --output-dir output/high-upside-entry --min-timeframes 2 --require-weekly --min-technical-upside 15
```

Monthly + weekly early watchlist:

```bash
python run.py --combine-only --input-dir output --output-dir output/monthly-weekly-watchlist --require-monthly --require-weekly --min-timeframes 2 --min-technical-upside 8 --include-near-only
```

Broader early watchlist, including `NEAR` names:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image-watchlist --early-image-only --include-near-only --min-technical-upside 8
```

## Output Priority

Open the outputs in this order:

```text
1. overall/output/early-image-weekly/results.json
   Best image-style list with weekly support. This is the cleanest entry list.

2. overall/output/early-image/results.json
   Image-style daily/weekly/monthly entries. Good for finding fresh BO or EARLY setups.

3. overall/output/weekly-upside/results.json
   Balanced high-probability list with weekly confirmation and 8%+ measured upside.

4. overall/output/high-upside-entry/results.json
   Stricter list with weekly confirmation, two timeframes, and 15%+ measured upside.

5. overall/output/early-image-watchlist/results.json
   Broader list that includes NEAR names. Use this for preparation, not automatic entry.

6. overall/output/monthly-weekly-watchlist/results.json
   Higher-timeframe watchlist requiring monthly + weekly alignment.
```

## How To Analyse Results

Start with `overall/output/early-image-weekly/results.json`. For each symbol:

```text
best_stage = BO or EARLY  -> entry-stage candidate
best_stage = NEAR         -> watchlist, wait for EARLY or BO
best_stage = FT           -> already moved; prefer pullback/risk-controlled entry
confirmation = A/A+       -> stronger multi-timeframe support
technical_upside_pct      -> measured upside from base; prefer 8%+, stronger at 15%+
pine_confirmation         -> exact TradingView Pine script and timeframe to check
```

Then inspect the timeframe metrics:

```text
metrics.distance_to_pivot_pct
  Near 0 is best for entry. The new ranking is asymmetric: +0% to +3%
  (fresh above pivot) ranks above -3% to 0% (just below), which ranks
  above +3% to +8% (acceptable but later), which ranks above anything
  more extended. Stage (BO/EARLY vs NEAR vs FT) sits above this key,
  so a confirmed BO near pivot correctly outranks a NEAR just below.

metrics.recent_range_pct
  lower means tighter controlled action. Tightness is important for the reference-image pattern.

metrics.base_drawdown_pct
  lower means pause, not crash.

metrics.breakout_volume_ratio
  1.4x+ confirms demand on breakout bars.

metrics.vertical_gain_pct
  confirms the first strong buying-force move.
```

### Ranking tiebreaker (trading-priority hierarchy)

Within each timeframe's `results.json`, matches are sorted by a
five-level hierarchy designed to surface the best entries first:

```
1. score                    (higher wins)              primary conviction
2. stage tier               BO/EARLY (0) > NEAR (1) > FT (2)
3. breakout_volume_ratio    (higher wins)              demand confirmation
4. distance bucket          asymmetric, see below      entry quality
5. |distance_to_pivot_pct|  (closer wins)              within-bucket tiebreaker
```

The distance buckets are deliberately **asymmetric**:

```
bucket 0   0%   to  +3%   best    fresh BO at or just above pivot
bucket 1  -3%   to   0%   watch   pressed to pivot, not yet through
bucket 2  +3%   to  +8%   later   confirmed but starting to extend
bucket 3  anything else   last    > +8% extended or < -3% too far below
```

Why this matters:

- Previously the tiebreaker was `abs(distance_to_pivot_pct)`, which
  treated `-3%` and `+3%` as equivalent. For a confirmed-breakout
  scanner, a stock just above pivot with volume is strictly better
  than one still below pivot, and the new rule captures that.
- Stage tier sits above volume/distance, so a NEAR with huge volume
  does not outrank a confirmed BO at the same score.
- FT is demoted below NEAR on purpose: FT is already moving and is
  a lower-priority *entry* than a fresh setup at the same score, even
  though it is technically confirmed.

Score is still the primary key — a score-11 FT still ranks above a
score-8 BO, so the overall "best setup wins" intuition is preserved.

Decision hierarchy:

```text
Monthly EARLY/BO + Weekly EARLY/BO/FT = highest probability
Weekly EARLY/BO + Daily EARLY/BO      = best timing combo
Daily BO alone                        = valid entry, but lower confidence
NEAR only                             = watchlist only
BAD/damaged base                      = avoid
```

## Individual Timeframe Commands

Daily:

```bash
cd daily
python run.py
```

Weekly:

```bash
cd weekly
python run.py
```

Monthly:

```bash
cd monthly
python run.py
```

## Useful Scanner Parameters

Use all NSE stocks from inside the desired timeframe folder:

```bash
cd daily
python run.py
```

Dry-run symbol loading without downloading price data:

```bash
python run.py --dry-run
```

Scan only selected symbols:

```bash
python run.py --universe symbols --symbols "RELIANCE,TCS,HEG"
```

Scan symbols from a file:

```bash
python run.py --universe file --symbols-file symbols.txt
```

Include broader watchlist bases:

```bash
python run.py --include-watchlist
```

Limit for fast development testing:

```bash
python run.py --limit 50
```

Override parallel workers:

```bash
python run.py --max-workers 32
```

Default worker count is automatic:

```text
min(64, max(10, CPU threads * 8))
```

## Data Fetching Behavior

On weekly and monthly, `YahooDataProvider.fetch_history` wraps each
`yf.download` call in a retry loop:

```text
attempts       = 3 (default)
backoff        = 0.75s, 1.5s between attempts (exponential)
empty frame    = counts as a failure and triggers a retry
exception      = caught, retried, and only bubbles as DataProviderError
                 if every attempt raises
persistent 429 = eventually returns [] (same as "no data" today), but only
                 after the retries are exhausted
```

The scanner's public behavior is unchanged: it still sees either
`list[Candle]` or a `DataProviderError`. The retry settings are
constructor parameters (`max_retries`, `retry_backoff`) if you want to
override them programmatically.

## Pine Scripts

Place each Pine script on the matching TradingView timeframe:

```text
Daily   -> daily/five_star_setup.pine   on 1D chart
Weekly  -> weekly/five_star_setup.pine  on 1W chart
Monthly -> monthly/five_star_setup.pine on 1M chart
```

Marker hierarchy:

```text
EARLY = strict clean early entry before breakout
BO    = breakout today
FT    = recent follow-through after breakout
NEAR  = watchlist only, wait for EARLY or BO
BAD   = damaged base, avoid
```

The overall output includes `pine_confirmation`, which tells you which Pine script to open and which marker to look for.

The Pine scripts default to `Signal Mode = Early image only`. That matches the reference images more closely. They also show a current status table by default, so the chart should not look blank even when there is no active signal.

```text
shown by default = status table, current status label, recent EARLY/NEAR/BO markers
hidden by default = old full-history signal spam, BAD spam, and late FT markers
optional mode     = set Signal Mode to All actionable and Show Historical Signals to true
if only lines show = make sure Show Status Table and Show Recent Signals are enabled
```

## How The Python Scanner Works

Each timeframe scanner does the same job with timeframe-specific defaults:

1. Load the NSE equity universe.
2. Convert symbols to Yahoo format like `RELIANCE.NS`.
3. Download OHLCV candles with `yfinance` (with retry on empty/failed frames).
4. Score every symbol in parallel.
5. Write JSON output atomically (`.tmp` → `os.replace`) so the file is never half-written.

The strategy checks:

```text
trend above moving averages
prior vertical gain
pause/base drawdown
recent tightness and contraction
volume dry-up
near pivot, breakout, or follow-through stage
breakout volume confirmation
damaged-base rejection
```

## Output Fields

Important fields in each timeframe JSON:

```text
symbol
score
rating
stage
actionable
reasons
metrics.latest_close
metrics.pivot
metrics.distance_to_pivot_pct
metrics.breakout_volume_ratio
metrics.recent_range_pct
metrics.base_drawdown_pct
```

Scanner-level fields at the top of each `results.json`:

```text
total_requested         # symbols that were scanned
total_with_data         # symbols that returned candles
matches                 # number of matched setups in `results`
errors                  # total number of per-symbol fetch errors
error_details           # up to error_details_limit rows of {symbol, error}
error_details_truncated # true if errors > error_details_limit
error_details_limit     # current cap (25)
```

Important fields in `overall/output/results.json`:

```text
overall_score
confirmation
best_stage
best_timeframe
entry_plan
pine_confirmation
technical_upside_pct
best_upside_timeframe
upside_by_timeframe
has_monthly
has_weekly
has_daily
high_probability
```

## Potential Upside Filters

`technical_upside_pct` is a measured-move filter:

```text
estimated target = pivot + base depth
technical upside = estimated target vs current close
```

It is not a guaranteed target. It is used to avoid stocks that already moved too far from the base.

Recommended hierarchy:

```text
Monthly EARLY/BO + Weekly EARLY/BO/FT = highest probability
Weekly EARLY + Daily EARLY/BO         = strong timing combo
Daily BO alone                        = entry, but lower confidence
NEAR only                             = watchlist, not entry
BAD                                   = avoid
```

For the reference-image "early" view, use `--early-image-only`. It keeps:

```text
EARLY        = strict pre-breakout entry
NEAR         = watchlist near pivot, only included directly when --include-near-only is also used
BO first day = fresh breakout near pivot with volume
FT           = excluded from the early-image view because it is already moving
```

## Validation

Daily:

```bash
cd daily
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/models.py src/universe.py src/data.py src/strategy.py src/scanner.py config/__init__.py config/settings.py tests/__init__.py tests/fixtures.py tests/test_strategy.py tests/test_universe.py tests/test_scanner.py
```

Weekly:

```bash
cd weekly
python -m unittest discover -v
```

Monthly:

```bash
cd monthly
python -m unittest discover -v
```

Overall:

```bash
cd overall
python -m unittest discover -v
python run.py --symbols "RELIANCE,TCS,HEG" --max-workers 3 --output-dir output/smoke
```

Current test counts (unchanged by the recent fixes):

```text
daily     10 / 10
weekly    10 / 10
monthly   10 / 10
overall    5 /  5
total     35 / 35
```

## Pending Manual Work

Nothing is pending in the Python organization itself. The remaining manual work is market-operation work:

```text
1. Paste each Pine script into TradingView on its matching timeframe.
2. Compare Python result markers with the chart marker.
3. Reject names with poor liquidity, news risk, or bad market context.
4. Decide risk per trade and stop placement manually.
5. Tune thresholds later only after reviewing enough real candidates.
```

The scanner finds setups. It does not replace risk management, position sizing, or manual chart review.

## Known follow-up work (not in this round)

The following items are real but deliberately **not** addressed in the
weekly/monthly fix rounds, either because they are daily-only or because
they are bigger refactors that deserve their own PR:

```text
daily only     Identical sort bug in daily/src/scanner.py
daily only     Missing post_peak_drawdown guard in daily strategy
daily only     Reason string labels on daily
refactor       data.py/scanner.py/universe.py/models.py are byte-identical
               across daily/weekly/monthly; a shared common/ package would
               eliminate the triplication
refactor       Per-symbol yf.download instead of batched group_by="ticker"
edge case      --validate-symbols is a silent no-op when nsetools is missing
```
