from typing import Annotated, List, Optional
from pydantic import ValidationError
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, Relationship, select


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


def get_summary(amount, n, rate, month):
    schedule = get_amortization_schedule(amount, n, rate)
    """
    Current principal balance at given month
    The aggregate amount of principal already paid
    The aggregate amount of interest already paid
    """
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # pragma: no cover
    yield  # pragma: no cover

app = FastAPI(lifespan=lifespan)


@app.get("/users/", response_model=List[UserPublic])
def get_users(session: SessionDep):
    statement = select(User)
    result = session.exec(statement)
    return [user for user in result]


@app.post("/user/", response_model=UserPublic)
def create_user(user: UserCreate, session: SessionDep):
    user = User.model_validate(user)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.get("/loans/", response_model=List[LoanPublic])
def get_loans(session: SessionDep):
    statement = select(Loan)
    result = session.exec(statement)
    return [loan for loan in result]


@app.get("/loan/schedule/{load_id}")
def get_loan_schedule(load_id, session: SessionDep):
    statement = select(Loan).where(Loan.id == load_id)
    schedule = session.exec(statement)
    result = []
    for s in schedule:
        result = get_amortization_schedule(
            s.amount, s.loan_term_in_months, s.annual_interest_rate)
    if len(result) == 0:
        raise HTTPException(
            status_code=400, detail="No loan with that ID found.")
    return result


@app.get("/loan/summary/{load_id}/{month}")
def get_loan_summary(load_id, month, session: SessionDep):
    statement = select(Loan).where(Loan.id == load_id)
    schedule = session.exec(statement)
    result = []
    for s in schedule:
        result = get_summary(
            s.amount, s.loan_term_in_months, s.annual_interest_rate, int(month))
    if len(result) == 0:
        raise HTTPException(
            status_code=400, detail="No loan with that ID found.")
    return result


@app.post("/loan/", response_model=LoanPublic)
def create_loan(loan: LoanCreate, session: SessionDep):
    loan = Loan.model_validate(loan)
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan
