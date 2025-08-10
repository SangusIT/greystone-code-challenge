import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app import app, get_session, get_password_hash, Loan, User, authenticate_user, UserToLoan

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


def test_create_user(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    response = client.post(
        "/user/", data={"username": "carol1234", "email": "carol@email.com", "password": "secretpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    data = response.json()
    assert response.status_code == 200
    assert data["username"] == "carol1234"
    assert data["email"] == "carol@email.com"
    assert "id" in data


# def test_create_user_error(session: Session):
#     def get_session_override():
#         return session

#     app.dependency_overrides[get_session] = get_session_override

#     response = client.post(
#         "/user/", data={"username": 0, "email": 12, "password": 0}, headers={"Content-Type": "application/x-www-form-urlencoded"})
#     data = response.json()
#     assert response.status_code == 422
#     assert data["detail"][0]["msg"] == "Input should be a valid string"


def test_create_loan(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    token_response = setup_test_token(session)
    token_data = token_response.json()
    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.post(
        "/loan/", json={
            "amount": 1000,
            "annual_interest_rate": 0.03,
            "loan_term_in_months": 24
        }, headers=headers)
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

    token_response = setup_test_token(session)
    token_data = token_response.json()
    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.post(
        "/loan/", json={
            "amount": "one hundred",
            "annual_interest_rate": "3%",
            "loan_term_in_months": "twenty-four"
        }, headers=headers)
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


def test_get_access_token(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    response = client.post(
        "/token/", data={"username": "carol1234", "password": "secretpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    data = response.json()
    assert response.status_code == 200
    assert data["token_type"] == "bearer"
    assert "access_token" in data


def test_get_access_token_username_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    response = client.post(
        "/token/", data={"username": "carol456", "password": "secretpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "No users with that username found."


def test_get_access_token_password_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    response = client.post(
        "/token/", data={"username": "carol1234", "password": "testpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    data = response.json()
    assert response.status_code == 401
    assert data["detail"] == "Incorrect username or password"


def test_get_user(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    token_response = setup_test_token(session)
    token_data = token_response.json()
    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.get("/users/me/", headers=headers)
    assert response.status_code == 200


def test_get_token_missing_username_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    response = client.post(
        "/token/", data={"password": "secretpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code != 200


def test_get_user_invalid_token_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    headers = {"Authorization": "Bearer 2345"}

    response = client.get("/users/me/", headers=headers)
    assert response.status_code != 200


def test_get_user_loans(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    token_response = setup_test_token(session)
    token_data = token_response.json()

    usertoloan = UserToLoan(
        user_id=1, loan_id=1, user_type="owner")
    session.add(usertoloan)
    session.commit()
    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.get("/loans/user", headers=headers)
    data = response.json()
    assert response.status_code == 200
    assert len(data) > 0


def setup_test_token(session: Session):
    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    response = client.post(
        "/token/", data={"username": "carol1234", "password": "secretpassword"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return response


def test_authenticate_user_password_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    hashed_password = get_password_hash("secretpassword")
    test_user = User(hashed_password=hashed_password,
                     email="carol@email.com", username="carol1234")
    session.add(test_user)
    session.commit()

    result = authenticate_user("carol1234", "password", session)
    assert result == False


def test_share_loan(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    token_response = setup_test_token(session)
    token_data = token_response.json()

    usertoloan = UserToLoan(
        user_id=1, loan_id=1, user_type="owner")
    session.add(usertoloan)
    session.commit()

    hashed_password = get_password_hash("password123")
    test_user = User(hashed_password=hashed_password,
                     email="robert@email.com", username="robertm")
    session.add(test_user)
    session.commit()

    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.put("/loan/", headers=headers,
                          params={"loan_id": 1, "user_id": 2})
    data = response.json()
    assert response.status_code == 200
    assert len(data) > 0


def test_share_loan_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    token_response = setup_test_token(session)
    token_data = token_response.json()

    hashed_password = get_password_hash("password123")
    test_user = User(hashed_password=hashed_password,
                     email="robert@email.com", username="robertm")
    session.add(test_user)
    session.commit()

    usertoloan = UserToLoan(
        user_id=2, loan_id=1, user_type="owner")
    session.add(usertoloan)
    session.commit()

    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.put("/loan/", headers=headers,
                          params={"loan_id": 1, "user_id": 1})
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "You can only share loans you've created or that have been shared with you."


def test_share_loan_prev_share_error(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    test_loan = Loan(amount=30000, annual_interest_rate=3,
                     loan_term_in_months=48)
    session.add(test_loan)
    session.commit()

    token_response = setup_test_token(session)
    token_data = token_response.json()

    usertoloan = UserToLoan(
        user_id=1, loan_id=1, user_type="owner")
    session.add(usertoloan)
    session.commit()

    hashed_password = get_password_hash("password123")
    test_user = User(hashed_password=hashed_password,
                     email="robert@email.com", username="robertm")
    session.add(test_user)
    session.commit()

    headers = {"Authorization": "Bearer %s" % token_data["access_token"]}

    response = client.put("/loan/", headers=headers,
                          params={"loan_id": 1, "user_id": 1})
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "Loan previously shared."
