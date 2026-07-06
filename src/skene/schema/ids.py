"""Prefixed, time-sortable identifiers (``ses_``, ``msg_``, ``prt_``, ``evt_``).

The prefix makes IDs self-describing in logs and DB rows; the millisecond
timestamp prefix makes lexicographic order match creation order, so SQLite
range scans over IDs are chronological without an extra column.
"""

from __future__ import annotations

import secrets
import threading
import time

# Fixed-width hex millisecond timestamp: 12 hex chars covers year ~10889.
_TS_WIDTH = 12

# IDs minted in the same millisecond would otherwise sort by their random
# suffix; bump a monotonic floor so per-process creation order always holds.
_last_ts = 0
_lock = threading.Lock()


def new_id(prefix: str) -> str:
    global _last_ts
    with _lock:
        ts = max(int(time.time() * 1000), _last_ts + 1)
        _last_ts = ts
    return f"{prefix}_{ts:0{_TS_WIDTH}x}{secrets.token_hex(6)}"
