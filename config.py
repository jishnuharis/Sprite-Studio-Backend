"""
All configuration comes from environment variables so nothing secret ever
lives in source control. On Render, set these under your service's
Environment tab. Locally, copy .env.example to .env and fill it in.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str, default=None):
    val = os.environ.get(name, default)
    return val


# --- Database -----------------------------------------------------------
# Render's managed Postgres gives you a connection string ("Internal
# Database URL") that you paste into this service's DATABASE_URL variable
# yourself (or wire automatically via render.yaml's `fromDatabase`). Locally,
# falls back to a SQLite file so you can run/test without any setup.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sprite_studio.db")
# Some providers (Render included, depending on which URL you copy) hand out
# postgres:// URLs -- SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Auth -----------------------------------------------------------------
JWT_SECRET = _require("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_DAYS = int(os.environ.get("JWT_EXPIRES_DAYS", "30"))

# --- Replicate (server-side only -- never sent to the client) -------------
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
REPLICATE_MODEL = os.environ.get(
    "REPLICATE_MODEL", "black-forest-labs/flux-schnell"
)

# --- Public URL of this server itself --------------------------------------
# Needed to build the checkout page URL we hand back to the desktop app.
# Render gives every web service a free domain automatically -- set this to
# that, e.g. https://yourapp.onrender.com (find it at the top of your
# service's page in the Render dashboard).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")

# --- Razorpay -----------------------------------------------------------
# Test-mode keys from https://dashboard.razorpay.com/app/keys (toggle to
# Test Mode first). Live keys look the same shape but start with rzp_live_.
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
# The recurring Plan you create once in the Razorpay dashboard or via API
# (Subscriptions > Plans). This is NOT the same as a Stripe price ID format
# but plays the same role: it defines the amount + billing interval.
RAZORPAY_PLAN_ID = os.environ.get("RAZORPAY_PLAN_ID", "")
# Set after creating the webhook in the Razorpay dashboard (Settings > Webhooks)
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
# How many billing cycles a subscription runs before needing manual renewal.
# Razorpay requires a finite total_count -- 120 monthly cycles = 10 years,
# which is effectively "until canceled" for a real product.
RAZORPAY_SUBSCRIPTION_TOTAL_COUNT = int(os.environ.get("RAZORPAY_SUBSCRIPTION_TOTAL_COUNT", "120"))

# Where the user is told to go back to the desktop app after paying. Since
# there's no app to redirect back into from a browser, this is just a simple
# static "you're done, go back to Sprite Studio" page.
CHECKOUT_SUCCESS_URL = os.environ.get("CHECKOUT_SUCCESS_URL", "https://example.com/success")

# --- Quota / limits ---------------------------------------------------------
GENERATIONS_PER_MONTH = int(os.environ.get("GENERATIONS_PER_MONTH", "300"))
MAX_WIDTH = int(os.environ.get("MAX_WIDTH", "1024"))
MAX_HEIGHT = int(os.environ.get("MAX_HEIGHT", "1024"))

# --- CORS --------------------------------------------------------------
# The desktop app doesn't run in a browser, so this mostly matters if you
# ever add a web client. Comma-separated list of allowed origins, or "*".
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

# --- Brute-force protection --------------------------------------------
# Per-IP rate limit on /auth/login and /auth/signup, and a per-account
# lockout after repeated failed logins. Both are in-memory (see ratelimit.py)
# which is fine for Render's default single-instance setup; if you scale to
# multiple instances, move this to a shared store like Redis instead.
AUTH_RATE_LIMIT_MAX = int(os.environ.get("AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))
MAX_FAILED_LOGIN_ATTEMPTS = int(os.environ.get("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCKOUT_SECONDS = int(os.environ.get("ACCOUNT_LOCKOUT_SECONDS", str(15 * 60)))
