"""
All configuration comes from environment variables so nothing secret ever
lives in source control. On Railway, set these under your service's
Variables tab. Locally, copy .env.example to .env and fill it in.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str, default=None):
    val = os.environ.get(name, default)
    return val


# --- Database -----------------------------------------------------------
# Railway's Postgres add-on injects DATABASE_URL automatically. Locally,
# falls back to a SQLite file so you can run/test without any setup.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sprite_studio.db")
# Railway's Postgres URLs sometimes start with postgres:// — SQLAlchemy 2.x
# requires postgresql://
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
# On Railway, set this to your generated domain, e.g. https://yourapp.up.railway.app
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
