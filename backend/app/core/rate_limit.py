"""Shared slowapi Limiter instance, keyed by client IP.

Public-facing / cost-sensitive endpoints (login, chat) apply tighter per-route limits
via the @limiter.limit(...) decorator in their routers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
