# Security response headers applied to every response.
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Applied to all responses. HSTS is deliberately absent: it belongs to the TLS
# edge (Tailscale Serve in previews; R-12 in api/docs/security/risk-register.md),
# and sending it over plain HTTP in development would poison the browser's HSTS
# cache for localhost.
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

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds the security headers required by SR-28 (control API-5).

    Set on every response, not just the secret endpoints, so a new route cannot
    forget them. Existing values are not overwritten, letting a route opt out
    deliberately.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        is_docs = (
            request.url.path in ("/docs", "/redoc", "/openapi.json")
            or "/docs" in request.url.path
            or "/redoc" in request.url.path
        )

        for header, value in BASE_SECURITY_HEADERS.items():
            if header == "Content-Security-Policy" and is_docs:
                response.headers.setdefault(header, DOCS_CSP)
            else:
                response.headers.setdefault(header, value)
        return response
