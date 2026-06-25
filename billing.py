import datetime
import hmac
import hashlib
import json

import requests
from sqlalchemy.orm import Session

import config
from models import User

RAZORPAY_BASE = "https://api.razorpay.com/v1"
AUTH = (config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)


def create_checkout_session(user: User) -> str:
    """
    Creates a Razorpay Subscription via plain REST call and returns its
    hosted payment page (short_url) — the user pays there, same role as
    Stripe Checkout. We stash the user's id in `notes` so the webhook can
    find them later.
    """
    resp = requests.post(
        f"{RAZORPAY_BASE}/subscriptions",
        auth=AUTH,
        json={
            "plan_id": config.RAZORPAY_PLAN_ID,
            "customer_notify": 1,
            "total_count": 120,  # ~10 years of monthly cycles; Razorpay requires a count
            "notes": {"user_id": str(user.id)},
        },
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Razorpay error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    user.razorpay_subscription_id = data["id"]
    return data["short_url"]


def cancel_subscription(user: User) -> None:
    """Lets the user cancel — Razorpay has no hosted self-serve portal like Stripe's,
    so this just calls the API directly."""
    if not user.razorpay_subscription_id:
        raise ValueError("User has no active subscription to cancel.")
    resp = requests.post(
        f"{RAZORPAY_BASE}/subscriptions/{user.razorpay_subscription_id}/cancel",
        auth=AUTH,
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Razorpay error {resp.status_code}: {resp.text[:300]}")


def verify_webhook(payload: bytes, signature: str) -> dict:
    """Verifies the HMAC-SHA256 signature Razorpay sends on every webhook call."""
    expected = hmac.new(
        config.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise ValueError("Invalid webhook signature")
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
