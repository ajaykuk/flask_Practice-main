import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_health_success(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "healthy"
    assert response.json["database"] == "connected"


def test_health_failure(client, monkeypatch):

    class FakeMongoClient:
        class Admin:
            def command(self, command):
                raise Exception("MongoDB connection failed")

        admin = Admin()

    class FakeMongo:
        cx = FakeMongoClient()

    monkeypatch.setattr("app.mongo", FakeMongo())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json["status"] == "unhealthy"
    assert response.json["database"] == "disconnected"