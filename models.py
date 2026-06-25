from sqlalchemy import Column, Integer, String, DateTime, func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    razorpay_customer_id = Column(String, nullable=True)
    razorpay_subscription_id = Column(String, nullable=True)

    # inactive | trialing | active | past_due | canceled
    subscription_status = Column(String, default="inactive", nullable=False)

    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    generations_used = Column(Integer, default=0, nullable=False)

    def has_active_subscription(self) -> bool:
        return self.subscription_status in ("active", "trialing")
