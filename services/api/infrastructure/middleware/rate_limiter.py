from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 5, window_minutes: int = 60):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        # Key: identifier (email or IP), Value: list of datetime timestamps
        self._history: Dict[str, list] = {}

    def is_rate_limited(self, identifier: str) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.window_minutes)
        
        # Clean old entries
        if identifier in self._history:
            self._history[identifier] = [ts for ts in self._history[identifier] if ts > cutoff]
        else:
            self._history[identifier] = []

        if len(self._history[identifier]) >= self.max_requests:
            return True

        self._history[identifier].append(now)
        return False
