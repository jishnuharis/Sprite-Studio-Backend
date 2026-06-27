"""
Brute-force protection for /auth/login and /auth/signup:

  - Per-IP rate limiting: a sliding window cap on how many auth requests one
    IP can make in a given period.
  - Per-account lockout: after enough failed logins against one account, that
    account stops accepting login attempts for a cooldown period, regardless
    of which IP they come from.

Both are in-memory and per-process, which is fine for Render's default
single-instance setup. If you scale to multiple instances behind a load
balancer, move RateLimiter's storage to something shared (e.g. Redis) so
limits apply across all of them instead of being reset by which instance
happens to handle a given request.
"""
import time
from collections import defaultdict
from threading import Lock

import config


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        """Returns True if the request is allowed, False if rate-limited."""
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self.window_seconds]
            if len(hits) >= self.max_requests:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


auth_rate_limiter = RateLimiter(
    max_requests=config.AUTH_RATE_LIMIT_MAX,
    window_seconds=config.AUTH_RATE_LIMIT_WINDOW_SECONDS,
)


def client_ip(request) -> str:
    # Render (like most PaaS hosts) sits the app behind a reverse proxy, so
    # the real client IP arrives via this header rather than the raw socket.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_locked(user) -> bool:
    return bool(user.locked_until and user.locked_until > time.time())


def record_failed_login(user, db):
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= config.MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = time.time() + config.ACCOUNT_LOCKOUT_SECONDS
    db.commit()


def record_successful_login(user, db):
    user.failed_login_attempts = 0
    user.locked_until = 0.0
    db.commit()
