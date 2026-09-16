# Security response headers applied to every response.
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Applied to all responses. HSTS is deliberately absent: it is set by Caddy at
# the TLS edge (CLAUDE.md §5), and sending it over plain HTTP in development
# would poison the browser's HSTS cache for localhost.
BASE_SECURITY_HEADERS = {
    # A secret is revealed exactly once; a cached copy would outlive the burn.
    "Cache-Control": "no-store, no-cache, must-revalidate, private",
    "Pragma": "no-cache",
    # The payload id lives in the URL, so it must never leak to a third party
    # through the Referer header (invariant 6).
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # The API serves JSON only; nothing here should ever be rendered or framed.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds the security headers required by CLAUDE.md §11.6.

    Set on every response, not just the secret endpoints, so a new route cannot
    forget them. Existing values are not overwritten, letting a route opt out
    deliberately.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in BASE_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
