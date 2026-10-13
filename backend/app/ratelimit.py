"""
A small token-bucket limiter, one bucket per caller. In memory, per process: it protects the hub from a runaway agent
loop or a leaked token, it is not a distributed quota. Zero disables a limit.
"""
import threading
import time
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, per_minute: int, burst: int | None = None):
        self.per_minute = per_minute
        self.burst = burst if burst is not None else max(1, per_minute // 6 or 1)
        self._b: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def configure(self, per_minute: int, burst: int | None = None) -> None:
        with self._lock:
            self.per_minute = per_minute
            self.burst = burst if burst is not None else max(1, per_minute // 6 or 1)
            self._b.clear()

    def allow(self, key: str) -> Tuple[bool, float]:
        """Returns (allowed, seconds_until_next_token)."""
        if self.per_minute <= 0:
            return True, 0.0
        rate = self.per_minute / 60.0
        cap = float(max(self.burst, 1))
        now = time.monotonic()
        with self._lock:
            tokens, last = self._b.get(key, (cap, now))
            tokens = min(cap, tokens + (now - last) * rate)
            if tokens >= 1.0:
                self._b[key] = (tokens - 1.0, now)
                if len(self._b) > 20000:  # forget idle callers
                    cutoff = now - 600
                    for k in [k for k, (_, t) in self._b.items() if t < cutoff]:
                        del self._b[k]
                return True, 0.0
            self._b[key] = (tokens, now)
            return False, (1.0 - tokens) / rate


def _mk(name: str, default: int) -> RateLimiter:
    from app.config import settings

    return RateLimiter(int(getattr(settings, name, default)))


# Tool calls (one bucket per token) and HTTP requests (one bucket per token or address).
tool_limiter = _mk("RATE_LIMIT_TOOLS_PER_MIN", 600)
http_limiter = _mk("RATE_LIMIT_HTTP_PER_MIN", 3000)


class FailureTracker:
    """Counts failed sign-ins per address. After `limit` failures inside a minute the address is locked out until the oldest ages out."""

    def __init__(self, limit: int):
        self.limit = limit
        self._hits: Dict[str, list] = {}
        self._lock = threading.Lock()

    def configure(self, limit: int) -> None:
        with self._lock:
            self.limit = limit
            self._hits.clear()

    def _recent(self, key: str, now: float) -> list:
        hits = [t for t in self._hits.get(key, []) if now - t < 60]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def locked(self, key: str) -> float:
        """Seconds the address must wait, or 0."""
        if self.limit <= 0:
            return 0.0
        now = time.monotonic()
        with self._lock:
            hits = self._recent(key, now)
            return max(0.0, 60 - (now - hits[0])) if len(hits) >= self.limit else 0.0

    def record(self, key: str) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            self._recent(key, now)
            self._hits.setdefault(key, []).append(now)
            if len(self._hits) > 20000:
                for k in [k for k in self._hits if not self._recent(k, now)]:
                    self._hits.pop(k, None)


from app.config import settings as _settings  # noqa: E402

auth_failures = FailureTracker(int(_settings.AUTH_FAILURES_PER_MIN))
