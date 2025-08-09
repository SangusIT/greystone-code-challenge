import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app import app, get_session

client = TestClient(app)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_user(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/users/", json={"name": "carol", "email": "carol@email.com"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == data["name"]
    assert data["email"] == data["email"]
    assert "id" in data
