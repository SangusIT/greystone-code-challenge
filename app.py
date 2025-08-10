from typing import Annotated, List, Optional
from pydantic import ValidationError, BaseModel, computed_field, SecretStr
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status, Form
from sqlmodel import Field, Session, SQLModel, create_engine, Relationship, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from datetime import datetime, timedelta, timezone, date
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from dotenv import load_dotenv
import os
import jwt


load_dotenv()


SECRET_KEY: str = os.environ.get("SECRET_KEY")
ALGORITHM: str = os.environ.get("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES"))


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserToLoan(SQLModel, table=True):
    user_id: int | None = Field(
        default=None, foreign_key="user.id", primary_key=True)
    loan_id: int | None = Field(
        default=None, foreign_key="loan.id", primary_key=True)
    user_type: str


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    email: str = Field(unique=True)
    loans: list["Loan"] = Relationship(
        back_populates="users", link_model=UserToLoan)
    hashed_password: str = Field(unique=True)


class UserCreate(BaseModel):
    username: str
    email: str
    password: SecretStr


class UserPublic(SQLModel):
    id: int
    username: str
    email: str


class Loan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    annual_interest_rate: float
    loan_term_in_months: int
    users: list["User"] = Relationship(
        back_populates="loans", link_model=UserToLoan)


class LoanCreate(SQLModel):
    amount: float = Field(gt=0)
    annual_interest_rate: float = Field(gt=0)
    loan_term_in_months: int = Field(gt=0)


class LoanPublic(SQLModel):
    id: int
    amount: float
    annual_interest_rate: float
    loan_term_in_months: int
    users: list["UserPublic"]
    owner: str | None = None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)  # pragma: no cover


def get_session():
    with Session(engine) as session:  # pragma: no cover
        yield session  # pragma: no cover


def get_summary(amount, n, rate, month):
    schedule = get_amortization_schedule(amount, n, rate)
    principal_balance = schedule[month - 1]["remaining_balance"]
    principal_paid = 0
    interest_paid = 0
    for i in range(month):
        principal_paid = principal_paid + \
            schedule[i]["monthly_payment"] - schedule[i]["monthly_interest"]
        interest_paid += schedule[i]["monthly_interest"]
    return {"principal_balance": round(principal_balance, 2), "principal_paid": round(principal_paid, 2), "interest_paid": round(interest_paid, 2)}


def get_amortization_schedule(amount, n, rate):
    """
    https://www.investopedia.com/terms/a/amortization.asp
    https://www.calculator.net/amortization-calculator.html
    """
    result = []
    i = rate/100/12
    current_amount = amount
    monthly_pmt = (amount *
                   ((i * ((1 + i)**n)) / (((1 + i)**n) - 1)))
    for month in range(1, n + 1):
        monthly_interest = current_amount * i
        current_amount = current_amount - monthly_pmt + monthly_interest
        result.append({
            "month": month,
            "remaining_balance": round(current_amount, 2),
            "monthly_payment": round(monthly_pmt, 2),
            "monthly_interest": round(monthly_interest, 2),
            "principal_due": round(monthly_pmt - monthly_interest, 2)
        })
    return result


SessionDep = Annotated[Session, Depends(get_session)]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # pragma: no cover
    yield  # pragma: no cover

app = FastAPI(lifespan=lifespan)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str, session: SessionDep):
    try:
        statement = select(User).where(User.username == username)
        result = session.exec(statement)
        user = result.one()
    except NoResultFound as e:
        raise HTTPException(
            status_code=400, detail="No users with that username found.")
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + \
            timedelta(minutes=15)  # pragma: no cover
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception  # pragma: no cover
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    statement = select(User).where(User.username == token_data.username)
    user = session.exec(statement)
    if user is None:
        raise credentials_exception  # pragma: no cover
    return user


@app.post("/token/", response_model=Token)
async def get_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep,
):
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me/", response_model=UserPublic)
async def get_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    u = current_user.one()
    user = UserPublic(id=u.id, username=u.username, email=u.email)
    return user


@app.get("/users/", response_model=List[UserPublic])
def get_users(session: SessionDep):
    statement = select(User)
    result = session.exec(statement)
    return [user for user in result]


@app.post("/user/", response_model=UserPublic)
def create_user(user: Annotated[UserCreate, Form()], session: SessionDep):
    hashed_password = get_password_hash(user.password.get_secret_value())
    user = User(hashed_password=hashed_password,
                email=user.email, username=user.username)
    user = User.model_validate(user)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.get("/loan/schedule/{loan_id}")
def get_loan_schedule(loan_id, session: SessionDep):
    try:
        statement = select(Loan).where(Loan.id == loan_id)
        schedule = session.exec(statement)
        s = schedule.one()
        result = get_amortization_schedule(
            s.amount, s.loan_term_in_months, s.annual_interest_rate)
    except NoResultFound as e:
        raise HTTPException(
            status_code=400, detail="No loan with that ID found.")
    return result


@app.get("/loan/summary/{loan_id}/{month}")
def get_loan_summary(loan_id, month, session: SessionDep):
    try:
        statement = select(Loan).where(Loan.id == loan_id)
        schedule = session.exec(statement)
        s = schedule.one()
        result = get_summary(
            s.amount, s.loan_term_in_months, s.annual_interest_rate, int(month))
    except NoResultFound as e:
        raise HTTPException(
            status_code=400, detail="No loan with that ID found.")
    return result


@app.post("/loan/", response_model=LoanPublic, dependencies=[Depends(get_current_user)])
def create_loan(loan: LoanCreate, session: SessionDep, current_user: User = Depends(get_current_user)):
    user = current_user.one()
    loan = Loan.model_validate(loan)
    session.add(loan)
    session.commit()
    session.refresh(loan)
    usertoloan = UserToLoan(
        user_id=user.id, loan_id=loan.id, user_type="owner")
    session.add(usertoloan)
    session.commit()
    session.refresh(loan)
    loan = LoanPublic.model_validate(loan)
    loan.owner = user.username
    return loan


@app.get("/loans/user", response_model=list[LoanPublic], dependencies=[Depends(get_current_user)])
def get_user_loans(session: SessionDep, current_user: User = Depends(get_current_user)):
    loans = []
    user = current_user.one()
    statement = select(Loan, UserToLoan, User).where(
        Loan.users.any(id=user.id)).where(Loan.id == UserToLoan.loan_id).where(UserToLoan.user_type == "owner").where(User.id == UserToLoan.user_id)
    results = session.exec(statement)

    for loan, usertoloan, user in results:
        loan = LoanPublic.model_validate(loan)
        loan.owner = user.username
        loans.append(loan)
    return loans


@app.put("/loan/", response_model=LoanPublic, dependencies=[Depends(get_current_user)])
def share_loan(loan_id, user_id, session: SessionDep, current_user: User = Depends(get_current_user)):
    user = current_user.one()
    try:
        statement = select(Loan).where(
            Loan.id == loan_id).where(Loan.users.any(id=user.id))
        results = session.exec(statement)
        loan = results.one()
        usertoloan = UserToLoan(
            user_id=user_id, loan_id=loan.id, user_type="viewer")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="You can only share loans you've created or that have been shared with you.")
    try:
        session.add(usertoloan)
        session.commit()
        session.refresh(loan)
    except IntegrityError as e:
        raise HTTPException(
            status_code=400, detail="Loan previously shared.")
    return loan
