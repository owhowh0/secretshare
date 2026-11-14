# Request body size limit, enforced before the body reaches Pydantic.
import logging

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("secretshare.limits")

# Room for the JSON envelope around the ciphertext field, so a payload that is
# exactly max_payload_bytes is rejected by the schema (a clean 422) rather than
# by this middleware.
BODY_OVERHEAD_BYTES = 1024


class BodySizeLimitMiddleware:
    """
    Rejects oversized request bodies before they are buffered or parsed.

    Upholds the 64 KB payload cap (NFR-07, SR-07). The schema's max_length
    also enforces the cap, but only after the full body has been read into
    memory — an unauthenticated caller could otherwise make the relay buffer an
    arbitrarily large request. Content-Length is checked first, and streamed
    bodies are counted chunk by chunk so a chunked request cannot bypass it.

    Written as raw ASGI rather than BaseHTTPMiddleware because it has to wrap
    the receive channel itself: BaseHTTPMiddleware rebuilds the downstream
    Request, which discards any replayed body.
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self._app = app
        self._max = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                await self._reject(scope, send, 400, "Invalid request")
                return
            if declared > self._max:
                await self._reject(scope, send, 413, "Payload too large")
                return

        # A missing or understated Content-Length still has to be bounded, so
        # the body is counted as it streams through.
        received = 0
        exceeded = False

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max:
                    exceeded = True
                    # Ending the stream keeps the route from blocking; the
                    # oversized request fails as an incomplete body.
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        sent_response = False

        async def guarded_send(message: Message) -> None:
            nonlocal sent_response
            if exceeded and not sent_response:
                sent_response = True
                await self._send_response(
                    send, 413, "Payload too large", scope=scope
                )
                return
            if exceeded:
                return
            sent_response = True
            await send(message)

        await self._app(scope, counting_receive, guarded_send)

    async def _reject(self, scope: Scope, send: Send, status: int, detail: str) -> None:
        await self._send_response(send, status, detail, scope=scope)

    async def _send_response(
        self, send: Send, status: int, detail: str, *, scope: Scope
    ) -> None:
        response = JSONResponse(status_code=status, content={"detail": detail})
        await response(scope, _empty_receive, send)


async def _empty_receive() -> Message:
    return {"type": "http.disconnect"}
