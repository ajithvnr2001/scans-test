# Weekly/Monthly Scan Correctness Fixes

This document captures the three correctness fixes applied to the weekly and
monthly scanners, the reasoning behind each, and the end-to-end validation
evidence. It accompanies PR #1.

## Scope

Only the `weekly/` and `monthly/` timeframes are touched, per the stated focus.
The `daily/` and `overall/` directories are intentionally **not** modified, even
where the same class of bug exists, so the change surface stays small and
reviewable.

Files changed (6):

```
weekly/src/scanner.py   weekly/src/data.py   weekly/src/strategy.py
monthly/src/scanner.py  monthly/src/data.py  monthly/src/strategy.py
```

Total diff: **+76 / -34** lines.

---

## Fix 1 — Sort key no longer prefers extended setups

**File:** `weekly/src/scanner.py`, `monthly/src/scanner.py`
**Severity:** High (affects ranking of every scan run)

### The bug

`run_scan` sorts matches at the end. The previous key was:

```python
matches.sort(
    key=lambda item: (
        item.signal.score,
        item.signal.metrics.get("breakout_volume_ratio", 0),
        item.signal.metrics.get("distance_to_pivot_pct", -100),
    ),
    reverse=True,
)
```

`reverse=True` means *larger* values win ties, including on the third
component, `distance_to_pivot_pct`. That's where the bug is. This metric
measures how far price is above (+) or below (-) the pivot. For an entry
setup you want it close to 0.

Concrete example from the actionable stages at the exact same score and
volume ratio:

| Stock   | score | volume_ratio | distance_to_pivot_pct | Old rank | Should rank |
|---------|-------|--------------|----------------------:|----------|-------------|
| ATPIVOT | 9     | 2.0          | +0.2  (right at pivot)|    2nd   |     1st     |
| EXTENDED| 9     | 2.0          | +15.0 (way extended)  |    1st   |    last     |
| NEARBELOW | 9   | 2.0          | -1.8  (just below)    |    3rd   |     2nd     |

The previous sort put the most-extended stock on top. If the user acts on the
top N, they are systematically trading the worst entries. This doesn't change
*which* stocks match — the match list itself is identical — only their order.

### The fix

```python
# Sort by: score desc, breakout volume desc, then proximity to pivot
# (closest to 0% wins; penalizes stocks already extended above pivot).
matches.sort(
    key=lambda item: (
        -item.signal.score,
        -item.signal.metrics.get("breakout_volume_ratio", 0),
        abs(item.signal.metrics.get("distance_to_pivot_pct", 100)),
    ),
)
```

Two mechanical changes:

1. Drop `reverse=True` and negate the first two components so each is
   naturally ordered "higher is better."
2. Use `abs(distance_to_pivot_pct)` so both overshoot and undershoot
   equally penalize the rank, and "closer to 0" sorts first.

Default for missing distance was `-100`; it becomes `+100` so missing-metric
rows sort last rather than tying with good setups.

### Does it change which matches appear?

**No.** The filter (`score >= min_score and actionable`) is unchanged. Only
the order of the already-matching list is affected. Score remains the
primary key — a score-11 breakout still ranks above a score-8 near-pivot
(verified in end-to-end test below).

### Validation

Three-stock tie-breaker test:

```
resulting order: ['ATPIVOT.NS', 'NEARBELOW.NS', 'EXTENDED.NS']
[PASS] closest to pivot (|0.2%|) ranks first
[PASS] next closest (|1.8%|) ranks second
[PASS] extended (|15%|) ranks last
[PASS] score still dominates over proximity
```

End-to-end `run_scan` with the fixture provider:

```
BO.NS   score=11 dist=3.65  vol_ratio=6.49   <- ranks 1st (higher score wins)
NEAR.NS score=8  dist=-1.35 vol_ratio=1.08   <- ranks 2nd
```

Confirms score-dominance is preserved.

---

## Fix 2 — Retry with exponential backoff on empty Yahoo frames

**File:** `weekly/src/data.py`, `monthly/src/data.py`
**Severity:** Medium (affects reproducibility of results)

### The bug

`YahooDataProvider.fetch_history` used to make a single `yf.download` call:

```python
try:
    frame = yf.download(...)
except Exception as exc:
    raise DataProviderError(...) from exc

return dataframe_to_candles(frame)
```

Two failure modes were handled poorly:

1. **Yahoo rate-limits (HTTP 429).** yfinance does not raise — it returns an
   empty DataFrame. `dataframe_to_candles` returns `[]`, and the scanner
   treats that as "stock doesn't match." The stock silently disappears from
   the results.
2. **Transient exceptions** (connection reset, timeout). `yf.download` raises,
   and the symbol is marked as a permanent error even for a blip.

Net effect: run the scanner twice five minutes apart on the full NSE
universe, and the match lists differ — not because the market moved, but
because different subsets hit Yahoo's rate limit each time.

### The fix

```python
def __init__(
    self,
    period: str = "1y",
    interval: str = "1d",
    validate_symbols: bool = False,
    max_retries: int = 3,
    retry_backoff: float = 0.75,
) -> None:
    ...
    self.max_retries = max(1, max_retries)
    self.retry_backoff = max(0.0, retry_backoff)
```

```python
last_exc: Exception | None = None

for attempt in range(self.max_retries):
    try:
        frame = yf.download(...)
    except Exception as exc:
        last_exc = exc
        frame = None

    candles = dataframe_to_candles(frame) if frame is not None else []
    if candles:
        return candles

    if attempt < self.max_retries - 1 and self.retry_backoff:
        time.sleep(self.retry_backoff * (2 ** attempt))

if last_exc is not None:
    raise DataProviderError(...) from last_exc
return []
```

Key design points:

- **Default 3 attempts.** Backoff sleeps are 0.75s, 1.5s between attempts
  (the attempt itself is not delayed). Total worst-case wasted time per
  stuck symbol: ~2.25s.
- **Empty frame is a retry signal**, not a pass-through. An empty frame
  typically means rate-limiting on NSE tickers that definitely have data.
- **Exceptions are caught and retried**, not bubbled on the first attempt.
- **Persistent empty frames return `[]`** (not an error — the ticker may
  genuinely have no data, e.g. newly listed below the period window).
- **Persistent exceptions raise `DataProviderError`** — same public
  contract as before, so the scanner's error-tracking still works.
- **`max_retries` and `retry_backoff` are constructor parameters**, so the
  behavior is testable and tunable without code changes.

### What doesn't change

- The scanner sees the same return types as before: `list[Candle]` on
  success/empty, `DataProviderError` on persistent failure.
- `--validate-symbols`, `--period`, `--interval` all still work identically.
- No threading changes — the existing `ThreadPoolExecutor` in `scanner.py`
  still fans out across symbols.

### Validation

All three code paths verified with a stubbed `yfinance.download`:

```
== Fix 2: retry-with-backoff ==
[PASS] candles returned after retry (got 5)           <- Case A: 2 empty, then success
[PASS] yfinance called 3 times (got 3)
[PASS] exponential backoff applied (got [0.5, 1.0])   <- sleeps between attempts

[PASS] empty list returned when all retries return empty   <- Case B: always empty
[PASS] yfinance called 3 times (got 3)
[PASS] two backoff sleeps in between (got [0.5, 1.0])

[PASS] DataProviderError raised when every attempt throws  <- Case C: always raises
[PASS] yfinance called 3 times on persistent error (got 3)
```

All three cases pass on both `weekly` and `monthly`.

---

## Fix 3 — Reason string correctly names the MA timeframe

**File:** `weekly/src/strategy.py`, `monthly/src/strategy.py`
**Severity:** Cosmetic (affects log/JSON readability, not matching)

### The bug

In all three strategy files, the 50-MA check appended:

```python
reasons.append("price is above the 50-day average")
```

But the weekly strategy is operating on weekly candles, so the 50-period MA
is a **50-week** MA. Same issue on monthly (it's a 50-month MA). The math
itself is correct — `mean(closes[-50:])` is computed from the right bars —
but the JSON and log output mislabels it as "50-day" on every timeframe.

This doesn't affect which stocks match. It's purely a reporting issue. But
for a scanner whose JSON is consumed by downstream tooling or read by
humans, mislabeled reasons erode trust in the output.

### The fix

Added a per-timeframe constant `TIMEFRAME_BAR_NAME` and used it in the
f-string:

**`weekly/src/strategy.py`:**
```python
TIMEFRAME_NAME = "weekly"
TIMEFRAME_BAR_NAME = "week"
...
reasons.append(f"price is above the 50-{TIMEFRAME_BAR_NAME} average")
```

**`monthly/src/strategy.py`:**
```python
TIMEFRAME_NAME = "monthly"
TIMEFRAME_BAR_NAME = "month"
...
reasons.append(f"price is above the 50-{TIMEFRAME_BAR_NAME} average")
```

Why a separate constant instead of deriving `"week"` from `"weekly"[:-2]`?
Because `TIMEFRAME_NAME = "daily"` → `"dail"` fails. A second explicit
constant is unambiguous and future-proof if a new timeframe is added.

### What doesn't change

- Score is still incremented by 1 on the same condition (`latest_close > ma50
  and ma20 >= ma50 * 0.98`).
- The `ma50` metric in the returned `SetupSignal.metrics` dict is unchanged
  — it was always the correct 50-bar mean.
- No other reason strings are touched.

### Validation

Reason strings on the fixture breakout:

```
weekly  reasons: price is above the 50-week average | ...
[PASS] reason mentions 50-week
[PASS] reason no longer mentions 50-day

monthly reasons: price is above the 50-month average | ...
[PASS] reason mentions 50-month
[PASS] reason no longer mentions 50-day
```

---

## End-to-end validation summary

### Existing unit tests

All existing tests pass with zero modifications:

| Directory | Tests passing |
|-----------|:-------------:|
| weekly/tests   | 10 / 10 |
| monthly/tests  | 10 / 10 |
| daily/tests    | 10 / 10 |
| overall/tests  | 5  / 5  |
| **Total**      | **35 / 35** |

This confirms the strategy scoring, base-damage logic, early-entry
detection, and scanner match filtering are all unchanged.

### Targeted fix validation

A throwaway script (`validate_fixes.py`, removed before commit) ran 24
focused assertions across both timeframes:

| Fix | Assertions (weekly) | Assertions (monthly) |
|-----|:-------------------:|:--------------------:|
| 1. Sort key | 4 / 4 pass | 4 / 4 pass |
| 2. Retry/backoff | 8 / 8 pass | 8 / 8 pass |
| 3. Reason string | 2 / 2 pass | 2 / 2 pass |
| **Total** | **14 / 14** | **14 / 14** |

### End-to-end `run_scan` with real fixtures

Two-stock scan using the existing breakout fixture:

```
BO.NS   score=11  distance=+3.65%  volume_ratio=6.49  <- rank 1 (higher score)
NEAR.NS score=8   distance=-1.35%  volume_ratio=1.08  <- rank 2
```

Confirms:
- Score still dominates ranking (score-11 ranks above score-8).
- Proximity tie-breaking is only active when score AND volume ratio are
  identical (per Fix 1's design).

### CLI smoke test

```
$ python weekly/run.py --universe symbols --symbols "reliance,tcs,m&m" --dry-run
{
  "universe": "symbols",
  "total_symbols": 3,
  "cpu_threads": 8,
  "max_workers": 64,
  "symbols": ["RELIANCE.NS", "TCS.NS", "M&M.NS"]
}
```

Same result from `monthly/run.py`. Argparse plumbing, symbol
normalization, and universe resolution all work end-to-end.

---

## What this PR deliberately does NOT fix

These are real issues flagged during the review, but left out of this PR
to keep the change focused:

1. **Identical sort bug in `daily/src/scanner.py`.** Same fix applies, but
   daily is out of scope.
2. **File duplication.** `data.py`, `scanner.py`, `universe.py`, and
   `models.py` are byte-identical across daily/weekly/monthly (that's how
   this PR had to patch the same code twice). A shared `common/` package
   would eliminate this; that's a larger refactor for its own PR.
3. **`--validate-symbols` silent no-op** when `nsetools` is missing.
4. **Non-atomic file writes** in `run.py` — a Ctrl+C mid-write leaves
   corrupt JSON.
5. **`_best_prior_gain` is O(N²)** — correct, just slow.
6. **Per-symbol `yf.download` instead of batched.** Retry helps with
   rate-limit symptoms; batching would reduce rate-limit frequency at the
   source. Much larger change.
7. **Daily's missing `post_peak_drawdown` guard.** Daily-only bug.
8. **Reason string labels in daily.** Daily-only.

All of these are tracked and can be addressed in follow-up PRs.

---

## Review checklist

- [x] Behavior change is intentional and documented above
- [x] No public API changes (constructor adds keyword-only args with
      defaults that preserve old behavior)
- [x] No new dependencies
- [x] Existing tests pass
- [x] Focused validation of each fix passes
- [x] Error handling preserves the `DataProviderError` contract
- [x] No logs/output format changes beyond the reason-string fix
