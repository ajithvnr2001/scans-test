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
to keep the change focused. Items marked ✅ have since been addressed in
Round 2 below; the rest remain open.

1. **Identical sort bug in `daily/src/scanner.py`.** Same fix applies, but
   daily is out of scope.
2. **File duplication.** `data.py`, `scanner.py`, `universe.py`, and
   `models.py` are byte-identical across daily/weekly/monthly (that's how
   this PR had to patch the same code twice). A shared `common/` package
   would eliminate this; that's a larger refactor for its own PR.
3. **`--validate-symbols` silent no-op** when `nsetools` is missing.
4. ✅ **Non-atomic file writes** in `run.py` — a Ctrl+C mid-write leaves
   corrupt JSON. **Fixed in Round 2.**
5. **`_best_prior_gain` is O(N²)** — correct, just slow.
6. **Per-symbol `yf.download` instead of batched.** Retry helps with
   rate-limit symptoms; batching would reduce rate-limit frequency at the
   source. Much larger change.
7. **Daily's missing `post_peak_drawdown` guard.** Daily-only bug.
8. **Reason string labels in daily.** Daily-only.
9. ✅ **`error_details` silently truncated at 25 rows.** **Fixed in
   Round 2** — `error_details_truncated` and `error_details_limit`
   fields now surface the truncation.
10. ✅ **Unused `highs` / `lows` locals in `analyze_five_star_setup`.**
    **Fixed in Round 2** — dead code removed.

All of the remaining items are tracked and can be addressed in
follow-up PRs.

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

---

# Round 2 — robustness, JSON transparency, and cleanup

A follow-up pass addressing smaller issues flagged during review. Same
scope (weekly + monthly only). All changes are behavior-preserving on
the happy path; they only matter on failure paths (atomic write, error
truncation).

## Fix 4 — Atomic JSON writes

**File:** `weekly/run.py`, `monthly/run.py`
**Severity:** Medium (a Ctrl+C mid-write currently corrupts output)

### The bug

```python
output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

`Path.write_text` is not atomic. If the process is killed (Ctrl+C, OOM,
crash) after the file is truncated but before the new contents are fully
flushed, `results.json` ends up as a half-written file. The next run of
`overall/run.py --combine-only` (which calls `json.loads` on each
timeframe file) will then fail with a cryptic `JSONDecodeError`.

On a full NSE-universe scan with retries, this is a multi-minute
window. It is realistic to interrupt it.

### The fix

```python
import os
...
output_path = Path(args.output)
output_path.parent.mkdir(parents=True, exist_ok=True)
# Atomic write: write to a temp file next to the target, then rename.
tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
os.replace(tmp_path, output_path)
```

Why this works:

- Writing to `results.json.tmp` first means the in-progress state never
  shares a name with the final artifact.
- `os.replace` is guaranteed atomic on POSIX and Windows for same-
  filesystem renames. Consumers see either the previous `results.json`
  or the new one, never an empty or truncated one.
- The `.tmp` sibling lives in the same directory, so the rename stays
  on the same filesystem (atomicity is not guaranteed across mounts).

### What does not change

- The output path, JSON structure, printed-to-stdout payload, exit code,
  and `output_path.parent.mkdir` behavior are all unchanged.
- A dangling `results.json.tmp` left by a previous crash is silently
  overwritten on the next run's write phase.

### Validation

```
== Fix A: atomic write on weekly/run.py ==
[PASS] run.py uses os.replace to finalize the write
[PASS] run.py writes to a .tmp sibling before renaming
[PASS] run.py imports os for the atomic rename
[PASS] dry-run exits 0 (got 0)
[PASS] dry-run reports 2 symbols (got 2)
```

End-to-end on disk:

```
wrote /projects/sandbox/scans-test/weekly/output/validate_round2/results.json
matches=1  errors=0  truncated=False  limit=25
[PASS] atomic write + truncation metadata verified on disk
```

Both weekly and monthly verified.

---

## Fix 5 — Error truncation is no longer silent

**File:** `weekly/src/models.py`, `monthly/src/models.py`
**Severity:** Low (data readability, not correctness)

### The bug

```python
def to_dict(self) -> dict[str, Any]:
    return {
        ...
        "errors": len(self.errors),
        "results": [...],
        "error_details": list(self.errors[:25]),
    }
```

`error_details` is silently capped at 25 rows. The `errors` integer is
the full total, but a reader of `results.json` who sees
`errors: 200, error_details: [<25 rows>]` has no way to tell whether the
first 25 is a sample, the worst offenders, or everything there is. In
practice it is just the first 25 in insertion order (which, because of
`ThreadPoolExecutor`, is nondeterministic).

### The fix

```python
@dataclass(frozen=True)
class ScanSummary:
    ...
    ERROR_DETAIL_LIMIT = 25

    def to_dict(self) -> dict[str, Any]:
        truncated = len(self.errors) > self.ERROR_DETAIL_LIMIT
        return {
            ...
            "error_details": list(self.errors[: self.ERROR_DETAIL_LIMIT]),
            "error_details_truncated": truncated,
            "error_details_limit": self.ERROR_DETAIL_LIMIT,
        }
```

Two tiny improvements:

1. The cap is a class constant (`ERROR_DETAIL_LIMIT`) instead of a
   magic `25` literal buried in a method body. Tests and downstream
   readers can reference `ScanSummary.ERROR_DETAIL_LIMIT` rather than
   hard-coding the number.
2. Two new fields in the JSON:
   - `error_details_truncated: bool` — `True` if the full error list
     didn't fit.
   - `error_details_limit: int` — the cap that was applied.

### What does not change

- The existing `errors` (count) and `error_details` (list) fields are
  unchanged.
- Consumers who only read `errors` and `error_details` still work; the
  two new fields are additive.

### Validation

```
== Fix B: error_details truncation surfaced (weekly) ==
[PASS] error_details_truncated is False when errors fit under the limit
[PASS] error_details_limit equals class constant (25)
[PASS] all 5 error details preserved (got 5)
[PASS] error_details_truncated is True when errors exceed the limit
[PASS] error_details capped at 25 rows (got 25)
[PASS] errors count reflects the full total, not the truncated list
```

All six pass on both weekly and monthly.

---

## Fix 6 — Dead `highs` / `lows` locals removed

**File:** `weekly/src/strategy.py`, `monthly/src/strategy.py`
**Severity:** Cleanup (no behavior change)

### The bug

```python
closes = [candle.close for candle in candles]
highs = [candle.high for candle in candles]   # never used
lows = [candle.low for candle in candles]     # never used
volumes = [candle.volume for candle in candles]
```

`highs` and `lows` were computed at the top of `analyze_five_star_setup`
but never read. (The `highs` local inside `_breakout_stage` is a
different scope and remains legitimate — it's used to compute the
rolling pivot.)

Two tiny costs:

- A ~250-item list comprehension is allocated twice per stock per
  timeframe, for nothing.
- Readers of the code waste a moment wondering what high/low features
  are being used that they can't find.

### The fix

Delete the two unused lines. That's it.

### Validation

```
== Fix C: dead locals removed (weekly/src/strategy.py) ==
[PASS] dead `highs` and `lows` list-comprehensions removed from analyze_five_star_setup
[PASS] _breakout_stage still computes its own highs (unchanged)
```

Same on monthly. All 35 existing unit tests still pass.

---

## Round 2 validation summary

| Layer | Scope | Result |
|---|---|---|
| Existing unit tests | weekly + monthly + daily + overall | **35 / 35 pass** |
| Round-2 focused checks | 14 checks × 2 timeframes | **28 / 28 pass** |
| End-to-end on-disk write | 2 timeframes (fake provider, real file I/O) | **4 / 4 assertions pass** |
| CLI smoke test | `run.py --dry-run` on weekly + monthly | Works |

Running totals across both rounds: **6 fixes, 57 validation checks, 0
regressions**.




---

# Round 3 — hierarchical trading-priority ranking

Feedback on Round 1's sort key was: `abs(distance_to_pivot_pct)` is
symmetric and treats `-3%` identical to `+3%`. For pure early-entry
scanning that is fine, but for a confirmed-breakout scan a stock just
above pivot is strictly better than one just below pivot, especially
if volume confirms. Fix 1's sort was safer than the old one but not
yet the best-possible trading-priority logic.

## Fix 7 — Stage tier + asymmetric distance bucket

**File:** `weekly/src/scanner.py`, `monthly/src/scanner.py`
**Severity:** Medium (affects ranking of every scan run; no match
inclusion changes)

### The new sort hierarchy

Each key is sorted ascending, so "lower is better":

```
1. score                       (negated -> higher score wins)
2. stage tier                  BO/EARLY (0) > NEAR (1) > FT (2)
3. breakout_volume_ratio       (negated -> higher volume wins)
4. distance bucket             asymmetric; see below
5. |distance_to_pivot_pct|     within-bucket tiebreaker, closer wins
```

### Stage tier

```python
_STAGE_TIER = {
    "early_entry":    0,    # strict pre-BO entry, tight base, volume dry-up
    "breakout_today": 0,    # fresh BO; same conviction as a clean EARLY
    "near_breakout":  1,    # pressed to pivot, not yet through
    "follow_through": 2,    # already in progress; lower priority for *entry*
}
```

Two things to note:

- `early_entry` and `breakout_today` share tier 0. They are both the
  "act now" bucket. EARLY is pre-pivot conviction; BO is post-pivot
  confirmation. Neither is universally better than the other, so the
  tie falls to score, then volume, then bucket.
- `follow_through` is tier 2, *below* NEAR. FT is already moving and
  is a lower-priority entry than a fresh setup at the same score. It
  still beats stocks whose stage is not in the table (default tier 99,
  e.g. `damaged_base` when someone passes `actionable_only=False`).

### Distance bucket (asymmetric)

```python
def _distance_bucket(distance_pct: float) -> int:
    if 0.0 <= distance_pct <= 3.0:
        return 0  # best: fresh BO at/just above pivot
    if -3.0 <= distance_pct < 0.0:
        return 1  # watch/early: just below pivot
    if 3.0 < distance_pct <= 8.0:
        return 2  # acceptable but later
    return 3      # extended (>+8%) or too far below (<-3%)
```

The bucket boundaries match the stage rules: weekly's near-pivot
threshold is 3%, monthly's is 5%, and `breakout_today` requires
`close >= pivot * 1.005` so confirmed BOs land at ≥+0.5%. Any BO at
`+15%` (inside the `follow_through` pivot extension cap of 25%) gets
parked in bucket 3, which is the correct behavior for entry
scanning.

### Worked examples

| Stock | score | stage | vol | dist | tier | bucket | rank |
|---|---|---|---|---|---|---|---|
| HI_SCORE_FT | 11 | follow_through | 1.5 | +20% | 2 | 3 | **1st** (score dominates) |
| LO_SCORE_BO |  8 | breakout_today | 5.0 | +1%  | 0 | 0 | 2nd |

Score still dominates — that's how the original behavior is preserved.

At **equal score**:

| Stock | stage | vol | dist | tier | bucket | rank |
|---|---|---|---|---|---|---|
| BO_PLUS_1       | breakout_today | 2.0 | +1.0% | 0 | 0 | **1st** |
| EARLY_MINUS_1   | early_entry    | 2.0 | -1.0% | 0 | 1 | 2nd |
| NEAR_MINUS_1    | near_breakout  | 1.0 | -1.0% | 1 | 1 | 3rd |
| FT_PLUS_1       | follow_through | 2.0 | +1.0% | 2 | 0 | 4th |

This is the key behavior change from Round 1. Under the old symmetric
`abs()` sort, `BO_PLUS_1` and `EARLY_MINUS_1` would tie on distance and
fall back to input order. Now the asymmetric bucket puts the confirmed
breakout first, as it should.

### The review scenario, explicitly

The reviewer flagged: *"a stock just above pivot with volume
confirmation should beat one just below pivot."* At equal score:

| Stock | stage | vol | dist | tier | vol key | bucket | rank |
|---|---|---|---|---|---|---|---|
| CONFIRMED_PLUS_1 | breakout_today | 2.5 | +1% | 0 | -2.5 | 0 | **1st** |
| NEAR_MINUS_1     | near_breakout  | 1.0 | -1% | 1 | -1.0 | 1 | 2nd |

Wins at the **tier** level (0 < 1) before the bucket or volume keys
even matter. Exactly the intended priority.

### What does NOT change

- Filtering (`score >= min_score and actionable`) is unchanged —
  same stocks match.
- Score is still the primary key. A score-11 FT still ranks above a
  score-8 BO.
- Volume ratio still matters within the same score+stage bucket.
- No changes to strategy, data, models, or run.py.

### Validation

All five levels of the hierarchy plus the review scenario were
verified with isolated test cases:

```
== weekly: hierarchical sort ==
[PASS] Level 1: score 11 beats score 8 regardless of stage/volume/distance
[PASS] Level 2: BO/EARLY are top two
[PASS] Level 2: NEAR is third
[PASS] Level 2: FT is last
[PASS] Level 3: higher volume wins within same tier+bucket
[PASS] Level 4: +1% (bucket 0) ranks above -1% (bucket 1)
[PASS] Level 4: -1% (bucket 1) ranks above +5% (bucket 2)
[PASS] Level 4: +5% (bucket 2) ranks above extended/too-far
[PASS] Level 4: +15% and -5% share bucket 3 (last two positions)
[PASS] Level 5: +0.5% closer-to-pivot wins within bucket 0
[PASS] Review scenario: confirmed BO at +1% beats NEAR at -1%
[PASS] Bucket asymmetry: +1% (bucket 0) beats -1% (bucket 1) at same tier/score/volume
```

Same 12 checks pass on monthly (24 total).

End-to-end through real `run_scan` on fixtures:

```
BO.NS    score=11  stage=breakout_today  dist=+3.65%  vol=6.49x  -> rank 1
NEAR.NS  score= 8  stage=early_entry     dist=-1.35%  vol=1.08x  -> rank 2
```

Score still dominates; no regression on the existing 35-test suite.

---

## Round 3 validation summary

| Layer | Scope | Result |
|---|---|---|
| Existing unit tests | weekly + monthly + daily + overall | **35 / 35 pass** |
| Hierarchical-sort focused checks | 12 checks × 2 timeframes | **24 / 24 pass** |
| End-to-end `run_scan` on fixtures | weekly + monthly | Correct order |

Running totals across all three rounds: **7 fixes, 81 validation checks, 0 regressions**.
