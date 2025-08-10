import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app import app, get_session, Loan

client = TestClient(app)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_get_users(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.get("/users/")
    assert response.status_code == 200


def test_get_loans(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.get("/loans/")
    assert response.status_code == 200


def test_create_user(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/user/", json={"name": "carol", "email": "carol@email.com"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "carol"
    assert data["email"] == "carol@email.com"
    assert "id" in data


def test_create_user_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/user/", json={"name": 0, "email": 12})
    data = response.json()
    assert response.status_code == 422
    assert data["detail"][0]["msg"] == "Input should be a valid string"


def test_create_loan(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/loan/", json={
            "amount": 1000,
            "annual_interest_rate": 0.03,
            "loan_term_in_months": 24
        })
    data = response.json()
    assert response.status_code == 200
    assert data["amount"] == 1000
    assert data["annual_interest_rate"] == 0.03
    assert data["loan_term_in_months"] == 24
    assert "id" in data


def test_create_loan_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/loan/", json={
            "amount": "one hundred",
            "annual_interest_rate": "3%",
            "loan_term_in_months": "twenty-four"
        })
    data = response.json()
    assert response.status_code == 422
    assert data["detail"][0]["msg"] == "Input should be a valid number, unable to parse string as a number"


def test_get_loan_schedule(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    response = client.get("/loan/schedule/1")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == test_loan.loan_term_in_months


def test_get_loan_schedule_error(session: Session):
    def get_session_override():
        return session

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    app.dependency_overrides[get_session] = get_session_override

    response = client.get("/loan/schedule/9898989")
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "No loan with that ID found."


def test_get_loan_summary(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    response = client.get("/loan/summary/1/12")
    data = response.json()
    assert response.status_code == 200
    assert data["interest_paid"] == 802


def test_get_loan_summary_error(session: Session):
    def get_session_override():
        return session

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    app.dependency_overrides[get_session] = get_session_override

    response = client.get("/loan/summary/9898989/12")
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "No loan with that ID found."
