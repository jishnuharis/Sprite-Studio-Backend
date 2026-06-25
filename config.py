"""
All configuration comes from environment variables so nothing secret
ever lives in source control or in the desktop app.
"""
import os

# --- Core secrets -----------------------------------------------------------
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_PLAN_ID = os.environ.get("RAZORPAY_PLAN_ID", "")

# --- Database ----------------------------------------------------------------
# Defaults to a local SQLite file for development. On Railway/Render, set
# DATABASE_URL to the Postgres connection string they give you.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./app.db")

# --- App behavior --------------------------------------------------------------
JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30"))
GENERATIONS_PER_MONTH = int(os.environ.get("GENERATIONS_PER_MONTH", "300"))

# Used to build Stripe Checkout redirect URLs. Since this is a desktop app
# (no web frontend), these can just be simple static pages — see README.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
CHECKOUT_SUCCESS_URL = os.environ.get("CHECKOUT_SUCCESS_URL", f"{APP_BASE_URL}/billing/success")
CHECKOUT_CANCEL_URL = os.environ.get("CHECKOUT_CANCEL_URL", f"{APP_BASE_URL}/billing/cancel")

# The Replicate model your server pays for. Keep this server-side and
# never let the client choose an arbitrary (potentially expensive) model.
REPLICATE_MODEL = os.environ.get("REPLICATE_MODEL", "black-forest-labs/flux-schnell")

# Hard caps so a tampered client request can't blow up your Replicate bill.
MAX_WIDTH = 768
MAX_HEIGHT = 768

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
