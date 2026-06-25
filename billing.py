"""
Razorpay Subscriptions integration.

Unlike Stripe, Razorpay has no hosted "Checkout page" you can just redirect
to for a recurring plan. The flow here is:

  1. Backend creates a Subscription via the Razorpay API -> gets a
     subscription_id (status starts as "created").
  2. The desktop app opens a small backend-served HTML page in the user's
     browser, passing that subscription_id. That page loads Razorpay's
     checkout.js widget, which collects payment and "authenticates" the
     subscription (this first charge is what activates recurring billing).
  3. Razorpay confirms this two ways: a JS callback on that page (used only
     for an instant "you're done!" message -- never trusted for granting
     access) and a webhook (subscription.activated / subscription.charged)
     which is the only thing that actually updates the user's access.

So unlike the old Stripe version, there's no separate "billing portal" --
Razorpay Subscriptions are managed by cancelling and re-subscribing, which
is exposed here as cancel_subscription().
"""
import hashlib
import hmac

import razorpay
from sqlalchemy.orm import Session

import config
from models import User

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.RAZORPAY_KEY_ID or not config.RAZORPAY_KEY_SECRET:
            raise RuntimeError(
                "Razorpay isn't configured on the server yet "
                "(missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET)."
            )
        _client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
    return _client


# Statuses where the user should be able to generate images. "authenticated"
# covers the brief window right after the first payment but before the
# subscription.activated webhook has been processed.
ACTIVE_STATUSES = ("active", "authenticated")


def create_subscription(user: User, db: Session) -> dict:
    """Creates (or reuses) a Razorpay Subscription for this user and returns
    {"subscription_id": ..., "key_id": ...} -- everything the checkout page
    needs to open the payment widget."""
    if not config.RAZORPAY_PLAN_ID:
        raise RuntimeError("RAZORPAY_PLAN_ID isn't set on the server yet.")

    client = _get_client()

    # Reuse an existing not-yet-paid subscription instead of creating a new
    # one every time the user clicks Subscribe (e.g. if they closed the
    # checkout page without paying and tried again).
    if user.razorpay_subscription_id and user.subscription_status in ("none", "created"):
        try:
            existing = client.subscription.fetch(user.razorpay_subscription_id)
            if existing.get("status") in ("created", "authenticated"):
                return {"subscription_id": existing["id"], "key_id": config.RAZORPAY_KEY_ID}
        except Exception:
            pass  # fall through and create a fresh one

    subscription = client.subscription.create({
        "plan_id": config.RAZORPAY_PLAN_ID,
        "total_count": config.RAZORPAY_SUBSCRIPTION_TOTAL_COUNT,
        "quantity": 1,
        "customer_notify": 1,
        "notes": {"user_id": str(user.id), "email": user.email},
    })

    user.razorpay_subscription_id = subscription["id"]
    user.subscription_status = subscription.get("status", "created")
    db.commit()

    return {"subscription_id": subscription["id"], "key_id": config.RAZORPAY_KEY_ID}


def cancel_subscription(user: User, db: Session):
    """Razorpay has no customer billing portal -- cancellation is a direct
    API call. cancel_at_cycle_end=True lets them keep access until the
    period they already paid for runs out, instead of cutting off instantly."""
    if not user.razorpay_subscription_id:
        raise RuntimeError("No active subscription to cancel.")
    client = _get_client()
    client.subscription.cancel(user.razorpay_subscription_id, {"cancel_at_cycle_end": 1})
    # Don't flip subscription_status here -- wait for the
    # subscription.cancelled webhook so the DB reflects Razorpay's actual
    # state, not an assumption about when the cancellation takes effect.


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not config.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        config.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _find_user(db: Session, entity: dict) -> "User | None":
    """Looks up the user a webhook event refers to, first by the
    subscription/customer ID we already stored, then by the notes we
    attached when creating the subscription."""
    sub_id = entity.get("id")
    if sub_id:
        user = db.query(User).filter(User.razorpay_subscription_id == sub_id).first()
        if user:
            return user

    notes = entity.get("notes") or {}
    user_id = notes.get("user_id")
    if user_id:
        return db.query(User).filter(User.id == int(user_id)).first()
    return None


def handle_webhook_event(payload: bytes, signature: str, db: Session) -> dict:
    if not verify_webhook_signature(payload, signature):
        raise ValueError("Invalid webhook signature")

    import json
    event = json.loads(payload)
    event_type = event.get("event", "")
    payload_data = event.get("payload", {})

    subscription_entity = payload_data.get("subscription", {}).get("entity", {})

    if event_type == "subscription.authenticated":
        user = _find_user(db, subscription_entity)
        if user:
            user.subscription_status = "authenticated"
            db.commit()

    elif event_type == "subscription.activated":
        user = _find_user(db, subscription_entity)
        if user:
            user.subscription_status = "active"
            user.generations_used = 0
            import datetime
            user.billing_period_start = datetime.datetime.utcnow()
            db.commit()

    elif event_type == "subscription.charged":
        # A renewal (or the very first) charge succeeded -- reset quota.
        user = _find_user(db, subscription_entity)
        if user:
            user.subscription_status = "active"
            user.generations_used = 0
            import datetime
            user.billing_period_start = datetime.datetime.utcnow()
            db.commit()

    elif event_type in ("subscription.pending", "subscription.halted"):
        # A renewal charge failed/is retrying -- payment method needs attention.
        user = _find_user(db, subscription_entity)
        if user:
            user.subscription_status = "pending" if event_type == "subscription.pending" else "halted"
            db.commit()

    elif event_type in ("subscription.cancelled", "subscription.completed", "subscription.expired"):
        user = _find_user(db, subscription_entity)
        if user:
            user.subscription_status = event_type.split(".")[1]  # cancelled / completed / expired
            db.commit()

    return {"received": True, "type": event_type}
