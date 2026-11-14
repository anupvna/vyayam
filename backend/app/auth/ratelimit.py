"""Sliding-window limiter for failed logins.

Counts failures per key (e.g. "email:a@x.com" or "ip:1.2.3.4") within the last
`window_seconds`. Once a key reaches `max_failures`, logins for it are refused until
the oldest failure ages out.

In-memory on purpose: the app runs as a single instance, so this is simple and
enough. With several instances it would move to Postgres or Redis. The clock is
injectable so tests can move time forward without sleeping.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable


class FailureLimiter:
    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and q[0] <= now - self.window_seconds:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int | None:
        """Seconds until `key` may try again, or None if it isn't blocked."""
        now = self._clock()
        q = self._prune(key, now)
        if len(q) < self.max_failures:
            return None
        return max(1, math.ceil(q[0] + self.window_seconds - now))

    def record_failure(self, key: str) -> None:
        self._failures[key].append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
