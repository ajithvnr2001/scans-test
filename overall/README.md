# Overall Multi-Timeframe Scanner

The overall scanner is the main command for serious scanning. It runs or combines:

```text
daily   -> /workspaces/scans-test/daily
weekly  -> /workspaces/scans-test/weekly
monthly -> /workspaces/scans-test/monthly
```

Then it ranks symbols by multi-timeframe confirmation quality.

## Main Command

```bash
cd /workspaces/scans-test/overall
python run.py --output-dir output
```

This writes:

```text
overall/output/daily.json
overall/output/weekly.json
overall/output/monthly.json
overall/output/results.json
```

Clean full rerun:

```bash
cd /workspaces/scans-test
find daily/output weekly/output monthly/output overall/output -type f -name '*.json' -delete
cd /workspaces/scans-test/overall
python run.py --output-dir output
```

## Fast Smoke Test

```bash
python run.py --symbols "RELIANCE,TCS,HEG" --max-workers 3 --output-dir output/smoke
```

## Combine Existing Results

After a full scan, do not download again if you only want to change ranking filters. Use:

```bash
python run.py --combine-only --input-dir output --output-dir output/reranked
```

## Pine Confirmation

Use the matching Pine script for the timeframe shown in each result:

```text
daily   -> ../daily/five_star_setup.pine on a 1D TradingView chart
weekly  -> ../weekly/five_star_setup.pine on a 1W TradingView chart
monthly -> ../monthly/five_star_setup.pine on a 1M TradingView chart
```

Each combined result includes `pine_confirmation`, for example:

```text
weekly/five_star_setup.pine on 1W chart: look for BO
daily/five_star_setup.pine on 1D chart: look for FT
```

Marker hierarchy:

```text
EARLY = clean aggressive early entry
BO    = confirmed breakout entry
FT    = follow-through, already moving
NEAR  = watchlist/prepare only
BAD   = avoid
```

The Pine scripts default to `Early image only`, so they show image-style `EARLY`, `NEAR`, or fresh `BO` setups. They also show a top-right status table on every chart. If you only see moving-average/base lines, check that these Pine inputs are enabled:

```text
Show Status Table = true
Show Current Status Label = true
Show Recent Signals = true
```

If you want every historical marker, change:

```text
Signal Mode = All actionable
Show Historical Signals = true
```

## Best Combo Logic

```text
Monthly EARLY/BO + Weekly EARLY/BO/FT = highest probability
Weekly EARLY + Daily EARLY/BO         = strong timing combo
Daily BO alone                        = entry, but lower confidence
NEAR only                             = watchlist, not entry
BAD                                   = avoid
```

By default, near-only candidates are excluded. Add `--include-near-only` for broader watchlists.

## Potential Upside Filters

`technical_upside_pct` is a measured-move estimate from the active base:

```text
estimated target = pivot + base depth
technical upside = target vs current close
```

This is not a price target guarantee. It is only a filter to avoid names that are already too extended.

## Command Hierarchy

Strict confirmed-entry list:

```bash
cd /workspaces/scans-test/overall
python run.py --output-dir output
```

Best balanced high-probability list, requiring weekly confirmation and at least 8% technical upside:

```bash
python run.py --combine-only --input-dir output --output-dir output/weekly-upside --min-timeframes 2 --require-weekly --min-technical-upside 8
```

Reference-image early entry list. This keeps only `EARLY`, `NEAR`, and first-day `BO` style setups and excludes late `FT` moves:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image --early-image-only --min-timeframes 1 --min-technical-upside 8
```

Cleaner weekly-supported early entry list:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image-weekly --early-image-only --require-weekly --min-timeframes 1 --min-technical-upside 8
```

Early watchlist, including `NEAR` only names:

```bash
python run.py --combine-only --input-dir output --output-dir output/early-image-watchlist --early-image-only --include-near-only --min-technical-upside 8
```

Highest timeframe watchlist, requiring monthly + weekly and at least 8% technical upside:

```bash
python run.py --combine-only --input-dir output --output-dir output/monthly-weekly-watchlist --require-monthly --require-weekly --min-timeframes 2 --min-technical-upside 8 --include-near-only
```

Very strict entry list, requiring weekly confirmation, two timeframes, and at least 15% technical upside:

```bash
python run.py --combine-only --input-dir output --output-dir output/high-upside-entry --min-timeframes 2 --require-weekly --min-technical-upside 15
```

## Analysis Workflow

Use this order after a full scan:

```text
1. output/early-image-weekly/results.json
   Cleanest image-style entries with weekly support. Best first file to inspect.

2. output/early-image/results.json
   Fresh image-style entries across daily, weekly, and monthly.

3. output/weekly-upside/results.json
   Multi-timeframe list with weekly support and 8%+ measured upside.

4. output/high-upside-entry/results.json
   Stricter multi-timeframe list with 15%+ measured upside.

5. output/early-image-watchlist/results.json
   Broader watchlist including NEAR. Use for alerts/preparation.

6. output/monthly-weekly-watchlist/results.json
   Slow but stronger higher-timeframe watchlist.
```

For each symbol, read these fields first:

```text
symbol
overall_score
confirmation
best_stage
best_timeframe
entry_plan
pine_confirmation
technical_upside_pct
early_image_timeframes
timeframe_count
```

Interpretation:

```text
BO or EARLY = entry-stage candidate
NEAR        = watchlist only; wait for EARLY or BO
FT          = already following through; manage risk because it may be late
BAD         = avoid
```

Then open the symbol in TradingView and use `pine_confirmation`:

```text
weekly/five_star_setup.pine on 1W chart: look for BO
daily/five_star_setup.pine on 1D chart: look for EARLY
monthly/five_star_setup.pine on 1M chart: look for NEAR
```

Do not treat `NEAR` alone as an entry. The better entry cases are:

```text
weekly BO/EARLY with daily BO/EARLY
monthly NEAR/EARLY/BO with weekly BO/EARLY
daily BO only when risk is controlled and upside remains acceptable
```

## Output Fields

Important result fields:

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
timeframes.daily
timeframes.weekly
timeframes.monthly
```

## Validate

```bash
cd /workspaces/scans-test/overall
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/ranker.py tests/__init__.py tests/test_ranker.py
```
