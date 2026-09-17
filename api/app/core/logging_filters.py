"""Log filters that keep capability-bearing identifiers out of log files.

`POST /secrets/reveal` keeps the payload id in the request body, so the access
log no longer sees it. This filter is defence in depth for everything that route
change cannot reach: an old bookmarked `GET /secrets/<id>` link that still hits
the API, a future route that puts an id in a path, and the exception handler
that logs `request.url.path`.
"""

import logging
import re

# Any /secrets/ path segment that is not one of the known, id-free routes.
# `token_urlsafe(32)` yields 43 base64url characters, but the pattern is kept
# broad on purpose: anything id-shaped in that position is redacted.
_SECRET_PATH = re.compile(r"(/secrets/)(?!reveal\b)[A-Za-z0-9_\-]+")

REDACTED = r"\1<redacted>"


class RedactSecretPaths(logging.Filter):
    """Rewrites secret ids out of a record before any handler formats it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_PATH.sub(REDACTED, record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: self._scrub(value) for key, value in record.args.items()
                }
            else:
                record.args = tuple(self._scrub(value) for value in record.args)

        return True

    @staticmethod
    def _scrub(value: object) -> object:
        if isinstance(value, str):
            return _SECRET_PATH.sub(REDACTED, value)
        return value


def install_secret_path_redaction() -> None:
    """Attaches the filter to the loggers that can print a request path."""
    for name in ("uvicorn.access", "uvicorn.error", "secretshare.api"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretPaths) for f in logger.filters):
            logger.addFilter(RedactSecretPaths())
