"""Lightweight per-client rate limiting + trustworthy client-IP resolution.

Backed by the configured cache (see CACHES in settings — use Redis in
production so counters are shared across workers; the default LocMemCache is
per-process and therefore only approximate). Fixed-window counters: the first
hit sets a key with a TTL of `window` seconds, subsequent hits increment it,
and the window resets once the key expires.
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def get_client_ip(request):
    """Resolve the real client IP from a SINGLE trusted proxy header.

    CLIENT_IP_HEADER names the one header set by our own edge proxy (default
    HTTP_CF_CONNECTING_IP for Cloudflare Tunnel). We deliberately do NOT fall
    back to X-Forwarded-For, which a client can spoof — otherwise IP-keyed
    throttles could be trivially evaded. Set CLIENT_IP_HEADER=REMOTE_ADDR when
    running without a trusted proxy in front.
    """
    header = getattr(settings, "CLIENT_IP_HEADER", "HTTP_CF_CONNECTING_IP")
    if header and header != "REMOTE_ADDR":
        val = request.META.get(header)
        if val:
            return val.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def _client_key(request):
    """Prefer the authenticated user id (survives IP changes) and fall back to
    the trusted client IP for anonymous requests."""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return "u{}".format(user.pk)
    return "ip{}".format(get_client_ip(request))


def check_rate(request, bucket, limit, window):
    """Return True if this request is within `limit` per `window` seconds for
    the client, incrementing the counter. Fails OPEN on any cache error so a
    cache outage can never take the whole site down."""
    key = "rl:{}:{}".format(bucket, _client_key(request))
    try:
        if cache.add(key, 1, window):     # first hit in this window
            return True
        try:
            current = cache.incr(key)
        except ValueError:                # key expired between add and incr
            cache.set(key, 1, window)
            return True
        return current <= limit
    except Exception:
        return True


def ratelimit(bucket, limit, window, json=False):
    """Decorator: throttle a view to `limit` requests per `window` seconds per
    client. Returns 429 when exceeded (JSON body if json=True). Place it BELOW
    @login_required so authenticated users are keyed by user id."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not check_rate(request, bucket, limit, window):
                if json:
                    return JsonResponse(
                        {"error": "Rate limit exceeded — please slow down."}, status=429
                    )
                return HttpResponse(
                    "Too many requests — please slow down and try again shortly.",
                    status=429, content_type="text/plain",
                )
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
