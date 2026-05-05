from __future__ import annotations

import os


DEFAULT_UNIVERSE = "all"
DEFAULT_MIN_SCORE = 7
DEFAULT_PERIOD = "10y"
DEFAULT_INTERVAL = "1mo"
DEFAULT_OUTPUT_PATH = "output/results.json"


def cpu_thread_count() -> int:
    return os.cpu_count() or 1


def default_max_workers() -> int:
    # Fetching Yahoo history is network I/O bound, so a small multiple of CPU
    # threads is faster than using CPU count alone.
    return min(64, max(10, cpu_thread_count() * 8))
