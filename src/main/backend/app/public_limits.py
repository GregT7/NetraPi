"""In-process limits for the public clip mint (not Pi ingest).

Per-IP rate limit and the global live-URL cap are orthogonal. Slots are
time-based: S3 does not report that a signature was used.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

PUBLIC_MAX_LIVE_URLS = 20
PUBLIC_MINT_RATE_MAX = 10
PUBLIC_MINT_RATE_WINDOW_SECONDS = 60.0


class PublicMintLimitError(Exception):
    def __init__(self, detail: str, retry_after: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.retry_after = retry_after


class PublicMintRateLimited(PublicMintLimitError):
    pass


class PublicMintSlotsFull(PublicMintLimitError):
    pass


_lock = threading.Lock()
_live_until: deque[float] = deque()
_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_for_tests() -> None:
    with _lock:
        _live_until.clear()
        _hits.clear()


def _retry_after(ready_at: float, now: float) -> int:
    return max(1, int(ready_at - now) + 1)


def record_mint_request(ip: str) -> None:
    """Count one mint *ask*. Raises if this IP is over the window."""
    now = time.monotonic()
    window_start = now - PUBLIC_MINT_RATE_WINDOW_SECONDS
    with _lock:
        hits = _hits[ip]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= PUBLIC_MINT_RATE_MAX:
            raise PublicMintRateLimited(
                "Too many playback URL requests from this client",
                _retry_after(hits[0] + PUBLIC_MINT_RATE_WINDOW_SECONDS, now),
            )
        hits.append(now)


def acquire_live_slot(ttl_seconds: int) -> float:
    """Reserve one unexpired public GET signature. Raises if 20 are live."""
    now = time.monotonic()
    expiry = now + ttl_seconds
    with _lock:
        while _live_until and _live_until[0] <= now:
            _live_until.popleft()
        if len(_live_until) >= PUBLIC_MAX_LIVE_URLS:
            raise PublicMintSlotsFull(
                "Too many live playback URLs",
                _retry_after(_live_until[0], now),
            )
        _live_until.append(expiry)
        return expiry


def release_live_slot(expiry: float) -> None:
    with _lock:
        try:
            _live_until.remove(expiry)
        except ValueError:
            pass


def live_slot_count() -> int:
    now = time.monotonic()
    with _lock:
        while _live_until and _live_until[0] <= now:
            _live_until.popleft()
        return len(_live_until)
