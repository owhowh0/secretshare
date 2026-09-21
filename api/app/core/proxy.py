# Resolves the real client address behind trusted reverse proxies.
import ipaddress
import logging
from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("secretshare.proxy")

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(values: Iterable[str]) -> list[IPNetwork]:
    """CIDRs or bare addresses → networks. Raises ValueError on a bad entry."""
    return [ipaddress.ip_network(value.strip(), strict=False) for value in values]


class TrustedProxyMiddleware:
    """
    Rewrites scope["client"] (and scope["scheme"]) from X-Forwarded-For /
    X-Forwarded-Proto, but only for requests whose immediate peer is a trusted
    proxy.

    Behind Traefik the TCP peer is always Traefik, so without this every caller
    shares one address: one rate-limit bucket (rl:<scope>:<ip>) and one audit
    IP for everybody. uvicorn's own --proxy-headers only trusts 127.0.0.1 by
    default, which never matches a proxy in another container.

    X-Forwarded-For is read right to left and the first hop that is not a
    trusted proxy is the client. Entries to the left of it were written by the
    client itself and are ignored, so sending a forged X-Forwarded-For cannot
    buy a fresh rate-limit bucket. Raw ASGI, like BodySizeLimitMiddleware, so
    the rewritten scope is what every downstream layer sees.
    """

    def __init__(self, app: ASGIApp, *, trusted_proxies: Iterable[str]) -> None:
        self._app = app
        self._trusted = parse_networks(trusted_proxies)

    def _is_trusted(self, host: str) -> bool:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(address in network for network in self._trusted)

    def _resolve_client(self, forwarded_for: str) -> str | None:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        for hop in reversed(hops):
            try:
                ipaddress.ip_address(hop)
            except ValueError:
                # A malformed chain can't be trusted at all; keep the peer.
                logger.debug("Ignoring malformed X-Forwarded-For entry")
                return None
            if not self._is_trusted(hop):
                return hop
        # Every hop is a trusted proxy: the leftmost is the origin.
        return hops[0] if hops else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        client = scope.get("client")
        if client and self._is_trusted(client[0]):
            headers = Headers(scope=scope)

            forwarded_for = headers.get("x-forwarded-for")
            if forwarded_for:
                resolved = self._resolve_client(forwarded_for)
                if resolved:
                    scope = {**scope, "client": (resolved, 0)}

            proto = headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
            if proto in ("http", "https", "ws", "wss"):
                if scope["type"] == "websocket":
                    proto = "wss" if proto in ("https", "wss") else "ws"
                scope = {**scope, "scheme": proto}

        await self._app(scope, receive, send)
