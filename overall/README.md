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

Highest timeframe watchlist, requiring monthly + weekly and at least 8% technical upside:

```bash
python run.py --combine-only --input-dir output --output-dir output/monthly-weekly-watchlist --require-monthly --require-weekly --min-timeframes 2 --min-technical-upside 8 --include-near-only
```

Very strict entry list, requiring weekly confirmation, two timeframes, and at least 15% technical upside:

```bash
python run.py --combine-only --input-dir output --output-dir output/high-upside-entry --min-timeframes 2 --require-weekly --min-technical-upside 15
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
