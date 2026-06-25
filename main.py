import base64
import datetime

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import config
import billing
import replicate_client
from auth import hash_password, verify_password, create_token, get_current_user
from database import get_db, init_db
from models import User

app = FastAPI(title="Sprite Studio Cloud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def health():
    """Used by the desktop app to quickly check the server is reachable."""
    return {"status": "ok", "service": "sprite-studio-cloud"}


# ── Auth ────────────────────────────────────────────────────────────────────

@app.post("/auth/signup")
def signup(body: dict, db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return {"token": token}


@app.post("/auth/login")
def login(body: dict, db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_token(user.id)
    return {"token": token}


# ── Account ─────────────────────────────────────────────────────────────────

@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "email": user.email,
        "subscription_status": user.subscription_status,
        "generations_used": user.generations_used,
        "generations_limit": config.GENERATIONS_PER_MONTH,
        "billing_period_start": user.billing_period_start.isoformat() if user.billing_period_start else None,
    }


# ── Billing (Razorpay) ───────────────────────────────────────────────────────

@app.post("/billing/create-subscription")
def create_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Creates a Razorpay subscription and returns a URL (this server's own
    /billing/checkout-page) that the desktop app should open in the user's
    browser to actually pay and activate it."""
    try:
        result = billing.create_subscription(user, db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    checkout_url = f"{config.PUBLIC_BASE_URL}/billing/checkout-page?subscription_id={result['subscription_id']}"
    return {"checkout_url": checkout_url, "subscription_id": result["subscription_id"]}


@app.get("/billing/checkout-page")
def checkout_page(subscription_id: str):
    """A minimal page that loads Razorpay's checkout widget for a given
    subscription. The desktop app opens this URL in the user's default
    browser -- there's no embedded browser in the app to host this in."""
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sprite Studio — Subscribe</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: -apple-system, sans-serif; background:#1a1a2e; color:#eee;
            display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
    .card {{ background:#12121f; border:1px solid #0f3460; border-radius:12px;
              padding:32px; max-width:380px; text-align:center; }}
    h1 {{ color:#e94560; font-size:20px; }}
    button {{ background:#e94560; color:white; border:none; border-radius:8px;
               padding:12px 24px; font-size:15px; font-weight:bold; cursor:pointer; margin-top:12px; }}
    button:hover {{ background:#ff6b6b; }}
    #status {{ margin-top:16px; color:#9a9a9a; font-size:14px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🎨 Sprite Studio Cloud</h1>
    <p>Subscribe to unlock cloud AI image generation.</p>
    <button id="pay-btn">Subscribe Now</button>
    <div id="status"></div>
  </div>
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <script>
    document.getElementById('pay-btn').onclick = function () {{
      var options = {{
        key: "{config.RAZORPAY_KEY_ID}",
        subscription_id: "{subscription_id}",
        name: "Sprite Studio",
        description: "Cloud AI Generation Subscription",
        theme: {{ color: "#e94560" }},
        handler: function (response) {{
          document.getElementById('status').innerHTML =
            "✅ Payment received! You can close this tab and go back to Sprite Studio.";
          document.getElementById('pay-btn').style.display = 'none';
        }},
        modal: {{
          ondismiss: function () {{
            document.getElementById('status').innerHTML = "Checkout closed. Click the button to try again.";
          }}
        }}
      }};
      var rzp = new Razorpay(options);
      rzp.on('payment.failed', function (response) {{
        document.getElementById('status').innerHTML =
          "❌ Payment failed: " + (response.error && response.error.description || "please try again.");
      }});
      rzp.open();
    }};
  </script>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@app.post("/billing/cancel-subscription")
def cancel_subscription_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Razorpay has no hosted billing portal, so cancellation is a direct
    action from the app rather than a redirect to manage billing elsewhere."""
    try:
        billing.cancel_subscription(user, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"cancelled": True}


@app.post("/billing/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    try:
        result = billing.handle_webhook_event(payload, signature, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ── Generation ──────────────────────────────────────────────────────────────

@app.post("/generate")
def generate(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.subscription_status not in billing.ACTIVE_STATUSES:
        raise HTTPException(status_code=402, detail="No active subscription. Please subscribe to generate images.")

    if user.generations_used >= config.GENERATIONS_PER_MONTH:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly generation limit reached ({config.GENERATIONS_PER_MONTH}). "
                   "It resets on your next billing date.",
        )

    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="A prompt is required")
    negative_prompt = body.get("negative_prompt", "")

    # Server-side safety rails: clamp size regardless of what the client
    # asked for, and the model itself is fixed -- the client never picks it.
    width = min(int(body.get("width", 512)), config.MAX_WIDTH)
    height = min(int(body.get("height", 512)), config.MAX_HEIGHT)
    width = max(width, 64)
    height = max(height, 64)

    try:
        image_b64 = replicate_client.generate_image_base64(
            prompt, negative_prompt, width, height
        )
    except replicate_client.ReplicateError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")

    user.generations_used += 1
    db.commit()

    return {"image_base64": image_b64}
