# Ephemeral ciphertext storage in Redis. Every key carries a TTL, so a secret
# that is never read still disappears on its own.
from dataclasses import dataclass
from enum import Enum

from redis.asyncio import Redis

# Reads the envelope and deletes it only when it belongs to the caller, as one
# atomic step. Checking the recipient in Python after a GETDEL would destroy the
# secret on a denied request; a GET followed by a separate DEL would let two
# concurrent reveals by the recipient both receive it (invariant 3). A payload
# that is not a JSON object with a matching recipient_id is never deleted here.
_BURN_FOR_RECIPIENT = """
local payload = redis.call('GET', KEYS[1])
if not payload then
  return {'missing'}
end
local ok, envelope = pcall(cjson.decode, payload)
if not ok or type(envelope) ~= 'table' or envelope['recipient_id'] ~= ARGV[1] then
  return {'denied'}
end
redis.call('DEL', KEYS[1])
return {'burned', payload}
"""


class BurnStatus(str, Enum):
    MISSING = "missing"  # unknown, already revealed, or expired
    DENIED = "denied"  # exists, but not for this caller; left untouched
    BURNED = "burned"  # returned to the recipient and deleted


@dataclass(frozen=True)
class BurnResult:
    status: BurnStatus
    payload: str | None = None


class SecretStore:
    def __init__(self, redis: Redis):
        self._redis = redis

    # store envelope payload in redis with automated expiration TTL
    async def put(self, payload_id: str, payload: str, *, ttl_seconds: int) -> None:
        await self._redis.set(f"s:{payload_id}", payload, ex=ttl_seconds)

    # Non-destructive check for bot previews and existence verification
    async def exists(self, payload_id: str) -> bool:
        return bool(await self._redis.exists(f"s:{payload_id}"))

    # retrieves the envelope and destroys it, but only for its recipient
    async def burn_for_recipient(self, payload_id: str, recipient_id: str) -> BurnResult:
        result = await self._redis.eval(
            _BURN_FOR_RECIPIENT, 1, f"s:{payload_id}", recipient_id
        )
        status = BurnStatus(result[0])
        return BurnResult(status, result[1] if status is BurnStatus.BURNED else None)
