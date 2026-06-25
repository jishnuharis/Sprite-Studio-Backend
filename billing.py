import datetime
import razorpay
from sqlalchemy.orm import Session

import config
from models import User

client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))


def create_checkout_session(user: User) -> str:
    """
    Creates a Razorpay Subscription and returns its hosted payment page
    (short_url) — the user pays there, same role as Stripe Checkout.
    We stash the user's id in `notes` so the webhook can find them later.
    """
    subscription = client.subscription.create({
        "plan_id": config.RAZORPAY_PLAN_ID,
        "customer_notify": 1,
        "total_count": 120,  # ~10 years of monthly cycles; Razorpay requires a count
        "notes": {"user_id": str(user.id)},
    })

    user.razorpay_subscription_id = subscription["id"]
    return subscription["short_url"]


def cancel_subscription(user: User) -> None:
    """Lets the user cancel — Razorpay has no hosted self-serve portal like Stripe's,
    so this just calls the API directly. Wire this up to a `/billing/cancel-subscription`
    endpoint if you want users to self-cancel from inside the app."""
    if not user.razorpay_subscription_id:
        raise ValueError("User has no active subscription to cancel.")
    client.subscription.cancel(user.razorpay_subscription_id)


def verify_webhook(payload: bytes, signature: str) -> dict:
    """Raises razorpay.errors.SignatureVerificationError if invalid."""
    client.utility.verify_webhook_signature(
        payload.decode("utf-8"), signature, config.RAZORPAY_WEBHOOK_SECRET
    )
    import json
    return json.loads(payload)


def handle_webhook_event(event: dict, db: Session):
    event_type = event.get("event")
    payload = event.get("payload", {})

    if event_type in ("subscription.activated", "subscription.charged"):
        sub_entity = payload.get("subscription", {}).get("entity", {})
        sub_id = sub_entity.get("id")
        notes = sub_entity.get("notes", {}) or {}
        user_id = notes.get("user_id")

        user = None
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
        if not user and sub_id:
            user = db.query(User).filter(User.razorpay_subscription_id == sub_id).first()

        if user:
            user.razorpay_subscription_id = sub_id
            user.subscription_status = "active"
            user.generations_used = 0
            user.period_start = datetime.datetime.utcnow()
            user.period_end = datetime.datetime.utcnow() + datetime.timedelta(days=30)
            db.commit()

    elif event_type in ("subscription.cancelled", "subscription.completed", "subscription.halted"):
        sub_entity = payload.get("subscription", {}).get("entity", {})
        sub_id = sub_entity.get("id")
        user = db.query(User).filter(User.razorpay_subscription_id == sub_id).first()
        if user:
            user.subscription_status = "canceled"
            db.commit()
