from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import DefaultDict, List


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: DefaultDict[str, List[float]] = defaultdict(list)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = [ts for ts in self._requests[key] if ts >= cutoff]
            if len(bucket) >= max_requests:
                self._requests[key] = bucket
                return False
            bucket.append(now)
            self._requests[key] = bucket
            return True


rate_limiter = RateLimiter()
