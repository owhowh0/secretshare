import pytest
from app.api.routes.secrets import get_secret_service
from app.main import app
from fastapi.testclient import TestClient


class FakeSecretService:
    def __init__(self) -> None:
        self.payloads = {}

    async def create_secret(self, ciphertext: str) -> str:
        payload_id = "test-id"
        self.payloads[payload_id] = ciphertext
        return payload_id

    async def retrieve_secret(self, payload_id: str) -> str | None:
        return self.payloads.pop(payload_id, None)


@pytest.fixture
def client():
    fake_service = FakeSecretService()
    app.dependency_overrides[get_secret_service] = lambda: fake_service

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_create_secret(client: TestClient) -> None:
    response = client.post(
        "/secrets",
        json={"ciphertext": "this-is-a-fake-ciphertext"},
    )

    assert response.status_code == 201
    assert response.json() == {"payload_id": "test-id"}


def test_retrieve_secret_burns_payload(client: TestClient) -> None:
    client.post(
        "/secrets",
        json={"ciphertext": "this-is-a-fake-ciphertext"},
    )

    first_response = client.post("/secrets/reveal", json={"payload_id": "test-id"})

    assert first_response.status_code == 200
    assert first_response.json() == {
        "ciphertext": "this-is-a-fake-ciphertext",
    }

    second_response = client.post("/secrets/reveal", json={"payload_id": "test-id"})

    assert second_response.status_code == 404
    assert second_response.json() == {
        "detail": "Secret not found or already retrieved",
    }
