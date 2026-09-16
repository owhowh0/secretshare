"""
A rejected token must not tell the client *why* it was rejected.

Naming the reason — unknown signing key, wrong audience, expired — hands an
attacker probing for a forgery a checklist of what to fix next. These tests pin
the response to one constant body and assert the diagnostic detail reaches the
server log instead (brief §2, CLAUDE.md §8 generic errors).
"""

import logging

import pytest

from tests.conftest import make_token

EXPECTED_DETAIL = "Invalid or expired token"

# Substrings PyJWT puts in its exception messages. If any of these reach the
# client, the failure mode has been disclosed.
#
# "expired" is deliberately absent: it is part of the constant detail string and
# so appears identically in every rejection, disclosing nothing. What matters is
# that the bodies are indistinguishable, which
# test_all_failure_modes_return_identical_body asserts directly.
LEAKY_FRAGMENTS = [
    "signing key",
    "kid",
    "audience",
    "signature",
    "algorithm",
    "PyJWK",
    "Unable to find",
]


def _token_variants(private_key_pem: bytes) -> dict[str, str]:
    """One token per distinct validation failure mode."""
    return {
        "expired": make_token(private_key_pem, exp_delta=-60),
        "wrong_audience": make_token(private_key_pem, audience="some-other-service"),
        "unknown_kid": make_token(private_key_pem, kid="unknown-kid-xyz"),
        "malformed": "not.a.jwt",
        "empty_segments": "..",
        "tampered_signature": make_token(private_key_pem) + "tampered",
    }


class TestAuthErrorDisclosure:
    async def test_all_failure_modes_return_identical_body(
        self, client, private_key_pem
    ):
        """The response body must be byte-identical across every failure mode."""
        bodies = {}
        for name, token in _token_variants(private_key_pem).items():
            r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 401, f"{name} returned {r.status_code}"
            bodies[name] = r.content

        distinct = set(bodies.values())
        assert len(distinct) == 1, (
            f"Failure modes are distinguishable by body: "
            f"{ {k: v.decode() for k, v in bodies.items()} }"
        )
        assert bodies["expired"] == b'{"detail":"Invalid or expired token"}'

    async def test_detail_is_the_static_string(self, client, private_key_pem):
        for name, token in _token_variants(private_key_pem).items():
            r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
            assert r.json()["detail"] == EXPECTED_DETAIL, f"leaked on {name}"

    @pytest.mark.parametrize("fragment", LEAKY_FRAGMENTS)
    async def test_no_internal_detail_in_response(
        self, client, private_key_pem, fragment
    ):
        """No PyJWT exception text may appear anywhere in the response."""
        for name, token in _token_variants(private_key_pem).items():
            r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
            body = r.content.decode().lower()
            assert fragment.lower() not in body, (
                f"'{fragment}' leaked in the {name} response: {body}"
            )

    async def test_www_authenticate_header_is_unchanged(
        self, client, private_key_pem
    ):
        """The challenge header must stay generic too."""
        for token in _token_variants(private_key_pem).values():
            r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
            assert r.headers.get("WWW-Authenticate") == "Bearer"

    async def test_reason_is_recorded_server_side(
        self, client, private_key_pem, caplog
    ):
        """
        The detail must not be lost: it belongs in the log so an operator can
        still debug a rejected token.
        """
        with caplog.at_level(logging.WARNING, logger="secretshare.auth"):
            token = make_token(private_key_pem, kid="unknown-kid-xyz")
            r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 401
        records = [
            rec for rec in caplog.records if rec.name == "secretshare.auth"
        ]
        assert records, "the rejection reason was not logged"
        logged = " ".join(rec.getMessage() for rec in records).lower()
        assert "signing key" in logged

    async def test_expired_token_reason_is_logged(
        self, client, private_key_pem, caplog
    ):
        with caplog.at_level(logging.WARNING, logger="secretshare.auth"):
            token = make_token(private_key_pem, exp_delta=-60)
            await client.get("/me", headers={"Authorization": f"Bearer {token}"})

        logged = " ".join(
            rec.getMessage() for rec in caplog.records if rec.name == "secretshare.auth"
        ).lower()
        assert "expired" in logged, f"expiry reason not logged, got: {logged}"

    async def test_bearer_token_is_never_logged(
        self, client, private_key_pem, caplog
    ):
        """
        Invariant 6: the token is a live credential and must stay out of the logs
        even while its rejection reason is recorded.
        """
        with caplog.at_level(logging.DEBUG):
            token = make_token(private_key_pem, kid="unknown-kid-xyz")
            await client.get("/me", headers={"Authorization": f"Bearer {token}"})

        all_logs = " ".join(rec.getMessage() for rec in caplog.records)
        assert token not in all_logs, "the bearer token was written to the log"
        # The signature segment alone is enough to replay; check it separately.
        assert token.rsplit(".", 1)[-1] not in all_logs
