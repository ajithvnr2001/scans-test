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
/workspaces/scans-test/
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
├── requirements.txt
└── README.md
```

## Install

From the workspace root:

```bash
cd /workspaces/scans-test
python -m pip install -r requirements.txt
```

`yfinance` is required for live OHLC data. `nsetools` is optional and is only used when `--validate-symbols` is passed.

## Best Run Order

Use this order when scanning seriously:

```bash
cd /workspaces/scans-test/overall
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
cd /workspaces/scans-test
find daily/output weekly/output monthly/output overall/output -type f -name '*.json' -delete
cd /workspaces/scans-test/overall
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
  near 0 is best for entry. Too far above pivot means late/extended.

metrics.recent_range_pct
  lower means tighter controlled action. Tightness is important for the reference-image pattern.

metrics.base_drawdown_pct
  lower means pause, not crash.

metrics.breakout_volume_ratio
  1.4x+ confirms demand on breakout bars.

metrics.vertical_gain_pct
  confirms the first strong buying-force move.
```

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
cd /workspaces/scans-test/daily
python run.py
```

Weekly:

```bash
cd /workspaces/scans-test/weekly
python run.py
```

Monthly:

```bash
cd /workspaces/scans-test/monthly
python run.py
```

## Useful Scanner Parameters

Use all NSE stocks from inside the desired timeframe folder:

```bash
cd /workspaces/scans-test/daily
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

## Pine Scripts

Place each Pine script on the matching TradingView timeframe:

```text
Daily   -> /workspaces/scans-test/daily/five_star_setup.pine    on 1D chart
Weekly  -> /workspaces/scans-test/weekly/five_star_setup.pine   on 1W chart
Monthly -> /workspaces/scans-test/monthly/five_star_setup.pine  on 1M chart
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
3. Download OHLCV candles with `yfinance`.
4. Score every symbol in parallel.
5. Write JSON output with matched setups only.

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

For the reference-image “early” view, use `--early-image-only`. It keeps:

```text
EARLY        = strict pre-breakout entry
NEAR         = watchlist near pivot, only included directly when --include-near-only is also used
BO first day = fresh breakout near pivot with volume
FT           = excluded from the early-image view because it is already moving
```

## Validation

Daily:

```bash
cd /workspaces/scans-test/daily
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/models.py src/universe.py src/data.py src/strategy.py src/scanner.py config/__init__.py config/settings.py tests/__init__.py tests/fixtures.py tests/test_strategy.py tests/test_universe.py tests/test_scanner.py
```

Weekly:

```bash
cd /workspaces/scans-test/weekly
python -m unittest discover -v
```

Monthly:

```bash
cd /workspaces/scans-test/monthly
python -m unittest discover -v
```

Overall:

```bash
cd /workspaces/scans-test/overall
python -m unittest discover -v
python run.py --symbols "RELIANCE,TCS,HEG" --max-workers 3 --output-dir output/smoke
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
