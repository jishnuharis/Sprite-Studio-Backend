import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean

from database import Base


def _now():
    return datetime.datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    created_at = Column(DateTime, default=_now)

    # Razorpay
    razorpay_customer_id = Column(String, nullable=True)
    razorpay_subscription_id = Column(String, nullable=True)
    # One of: "none", "created", "authenticated", "active", "pending",
    # "halted", "cancelled", "completed", "expired"
    # ("active" and "authenticated" are treated as having access -- see main.py)
    subscription_status = Column(String, default="none")

    # Usage / quota, reset on each successful billing-period renewal
    generations_used = Column(Integer, default=0)
    billing_period_start = Column(DateTime, default=_now)
