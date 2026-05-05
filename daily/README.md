# NSE Daily 5-Star Setup Scanner

This folder is the organized daily timeframe scanner. It mirrors the structure of `weekly/` and `monthly/`.

## Path

```text
/workspaces/scans-test/daily
```

## What It Scans

The daily scanner searches all NSE `EQ` stocks for the same structure shown in the reference images:

```text
vertical move -> controlled pause -> tight base -> volume confirmation -> early/breakout/follow-through
```

The daily version is faster and more timing-focused than weekly/monthly, but it is also noisier. Use it best when weekly or monthly already supports the setup.

## Files

```text
daily/
├── config/settings.py          # Daily defaults
├── five_star_setup.pine        # TradingView 1D confirmation script
├── output/                     # Daily JSON results
├── requirements.txt
├── run.py                      # Daily scanner entry point
├── src/data.py                 # Yahoo data download and candle conversion
├── src/models.py               # Candle, signal, and summary objects
├── src/scanner.py              # Parallel scanner
├── src/strategy.py             # Daily 5-star setup rules
├── src/universe.py             # NSE symbol loading
└── tests/                      # Offline synthetic tests
```

## Defaults

```text
period   = 1y
interval = 1d
output   = output/results.json
workers  = min(64, max(10, CPU threads * 8))
```

Daily strategy tuning:

```text
minimum candles              = 90 daily bars
base window                  = 45 daily bars
recent tightness window      = 15 daily bars
near pivot                   = within 2 percent
strict early entry distance  = within 1 percent below pivot
strict early recent range    = 8 percent or tighter
strict early base drawdown   = 22 percent or less
damaged base cap             = deep/wide bases cannot pass
```

## Run Daily Scanner

```bash
cd /workspaces/scans-test/daily
python run.py
```

Output:

```text
daily/output/results.json
```

Run only selected symbols:

```bash
python run.py --universe symbols --symbols "RELIANCE,TCS,HEG"
```

Run a small sample:

```bash
python run.py --limit 50
```

Include broad watchlist names:

```bash
python run.py --include-watchlist
```

Dry-run all NSE symbol loading:

```bash
python run.py --dry-run
```

Override workers:

```bash
python run.py --max-workers 32
```

## Daily Pine Script

Use this file:

```text
/workspaces/scans-test/daily/five_star_setup.pine
```

Place it on a TradingView `1D` chart.

Look for:

```text
EARLY = strict early entry
BO    = breakout today
FT    = follow-through
NEAR  = watchlist only
BAD   = avoid
```

Best daily use:

```text
Weekly EARLY/BO + Daily EARLY/BO = best daily timing
Daily BO alone                   = entry, but lower confidence
Daily NEAR alone                 = watchlist only
```

## Validate Daily

```bash
cd /workspaces/scans-test/daily
python -m unittest discover -v
python -m py_compile run.py src/__init__.py src/models.py src/universe.py src/data.py src/strategy.py src/scanner.py config/__init__.py config/settings.py tests/__init__.py tests/fixtures.py tests/test_strategy.py tests/test_universe.py tests/test_scanner.py
```

## How To Read A Daily Result

Example fields:

```text
stage: early_entry
score: 9
rating: A
metrics.distance_to_pivot_pct: -0.6
metrics.breakout_volume_ratio: 1.8
metrics.recent_range_pct: 6.4
metrics.base_drawdown_pct: 18.2
```

Meaning:

```text
stage early_entry       = strict early setup near pivot
score/rating            = quality of pattern
distance_to_pivot_pct   = how far current close is from pivot
breakout_volume_ratio   = latest volume vs recent average
recent_range_pct        = tightness
base_drawdown_pct       = pause depth
```

For real trading, always confirm the same symbol in `overall/output/results.json` and on the matching TradingView daily chart.
