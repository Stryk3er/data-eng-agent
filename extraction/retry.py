"""Exponential backoff with jitter, dependency-free."""
import functools
import random
import time


def with_retries(max_attempts: int = 5, base_delay: float = 1.0, retry_exceptions=(Exception,)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except retry_exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    print(f"[retry] attempt {attempt}/{max_attempts} failed ({e!r}); retrying in {delay:.1f}s")
                    time.sleep(delay)
        return wrapper
    return decorator
