import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.api.routes.keys import get_db
from app.db.models import DeviceKey, User

from tests.conftest import make_token

VALID_SPKI_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Y8LzKxK5P8e7o+1bC6g\n"
    "QY3m7j+k/V9y3d3x1w5a8n4v7c0m1k2l3j4h5g6f7e8d9c0b1a2z3y4x5w6v7u8t\n"
    "9s8r7q6p5o4n3m2l1k0j/i8h7g6f5e4d3c2b1a0z9y8x7w6v5u4t3s2r1q0p/o9n\n"
    "8m7l6k5j4i3h2g1f0e/d9c8b7a6z5y4x3w2v1u0t/s9r8q7p6o5n4m3l2k1j0i9h\n"
    "8g7f6e5d4c3b2a1z0y/x9w8v7u6t5s4r3q2p1o0n9m8l7k6j5i4h3g2f1e0d/c9b\n"
    "8a7z6y5x4w3v2u1t0s==\n"
    "-----END PUBLIC KEY-----"
)


class FakeDbSession:
    """In-memory fake DB session for isolated key unit tests."""

    def __init__(self):
        self.users = {}
        self.device_keys = []

    def add(self, obj):
        if isinstance(obj, User):
            if not getattr(obj, "id", None):
                obj.id = uuid.uuid4()
            if not getattr(obj, "created_at", None):
                obj.created_at = datetime.now(timezone.utc)
            self.users[obj.platform_user_id] = obj
        elif isinstance(obj, DeviceKey):
            if not getattr(obj, "id", None):
                obj.id = uuid.uuid4()
            if not getattr(obj, "created_at", None):
                obj.created_at = datetime.now(timezone.utc)
            self.device_keys.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = datetime.now(timezone.utc)

    async def execute(self, statement):
        mock_result = MagicMock()
        # Mocking User lookup
        if "FROM users" in str(statement):
            found = next(iter(self.users.values()), None)
            mock_result.scalar_one_or_none.return_value = found
            return mock_result

        # Mocking DeviceKey lookup
        if "FROM device_keys" in str(statement):
            active_keys = [k for k in self.device_keys if k.revoked_at is None]
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = active_keys
            mock_result.scalars.return_value = scalars_mock
            return mock_result

        # Mocking update (revocation)
        if "UPDATE device_keys" in str(statement):
            for k in self.device_keys:
                k.revoked_at = datetime.now(timezone.utc)
            return mock_result

        return mock_result


class TestKeyEndpoints:
    async def test_register_without_token_fails_403(self, client):
        response = await client.post(
            "/keys/register",
            json={"public_key": VALID_SPKI_PEM, "platform": "web"},
        )
        assert response.status_code == 403

    async def test_register_invalid_pem_fails_422(self, client, private_key_pem):
        from app.main import app

        fake_db = FakeDbSession()
        app.dependency_overrides[get_db] = lambda: fake_db

        try:
            token = make_token(private_key_pem)
            response = await client.post(
                "/keys/register",
                json={"public_key": "not-a-valid-pem", "platform": "web"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_register_and_retrieve_keys_flow(self, client, private_key_pem):
        from app.main import app

        fake_db = FakeDbSession()
        app.dependency_overrides[get_db] = lambda: fake_db

        try:
            token = make_token(private_key_pem, preferred_username="alice")
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Register Alice's public key
            res = await client.post(
                "/keys/register",
                json={
                    "public_key": VALID_SPKI_PEM,
                    "platform": "web",
                    "label": "Alice Laptop",
                },
                headers=headers,
            )
            assert res.status_code == 201
            data = res.json()
            assert data["platform"] == "web"
            assert data["public_key"] == VALID_SPKI_PEM.strip()
            assert data["label"] == "Alice Laptop"

            # 2. Retrieve Alice's public key
            get_res = await client.get("/keys/alice")
            assert get_res.status_code == 200
            get_data = get_res.json()
            assert get_data["user_id"] == "alice"
            assert len(get_data["keys"]) == 1
            assert get_data["keys"][0]["label"] == "Alice Laptop"
        finally:
            app.dependency_overrides.pop(get_db, None)
