from typing import Annotated, List, Optional
from pydantic import ValidationError
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, Relationship


class UserToLoan(SQLModel, table=True):
    user_id: int | None = Field(
        default=None, foreign_key="user.id", primary_key=True)
    loan_id: int | None = Field(
        default=None, foreign_key="loan.id", primary_key=True)
    user_type: str


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str
    loans: list["Loan"] = Relationship(
        back_populates="users", link_model=UserToLoan)


class UserCreate(SQLModel):
    name: str
    email: str


class UserPublic(SQLModel):
    id: int
    name: str
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
    annual_interest_rate: float
    loan_term_in_months: int


class LoanPublic(SQLModel):
    id: int
    amount: float
    annual_interest_rate: float
    loan_term_in_months: int


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)  # pragma: no cover


def get_session():
    with Session(engine) as session:  # pragma: no cover
        yield session  # pragma: no cover


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # pragma: no cover
    yield  # pragma: no cover

app = FastAPI(lifespan=lifespan)


@app.post("/user/", response_model=UserPublic)
def create_user(user: UserCreate, session: SessionDep):
    user = User.model_validate(user)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/loan/", response_model=LoanPublic)
def create_loan(loan: LoanCreate, session: SessionDep):
    loan = Loan.model_validate(loan)
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan
