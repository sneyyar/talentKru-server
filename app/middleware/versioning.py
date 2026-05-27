from functools import wraps
from fastapi import Response


def deprecated(sunset_date: str, replacement_link: str):
    """Decorator that adds deprecation headers to a route response."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, response: Response, **kwargs):
            response.headers["Sunset"] = sunset_date          # ISO 8601
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = f'<{replacement_link}>; rel="successor-version"'
            return await func(*args, response=response, **kwargs)
        return wrapper
    return decorator
