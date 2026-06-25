import base64
import datetime

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
import billing
from database import get_db, engine, Base
from models import User
from auth import hash_password, verify_password, create_token, get_current_user
import replicate_client

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sprite Studio Cloud API")


# ─── Schemas ───────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512


# ─── Auth ──────────────────────────────────────────────────────────────────

@app.post("/auth/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if "@" not in req.email or len(req.password) < 8:
        raise HTTPException(400, "Valid email and password (8+ chars) required")
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(400, "Account already exists")

    user = User(email=req.email.lower(), password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id)}


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"token": create_token(user.id)}


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "email": user.email,
        "subscription_status": user.subscription_status,
        "generations_used": user.generations_used,
        "generations_limit": config.GENERATIONS_PER_MONTH,
        "period_end": user.period_end.isoformat() if user.period_end else None,
    }


# ─── Billing ───────────────────────────────────────────────────────────────

@app.post("/billing/create-checkout-session")
def create_checkout_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    url = billing.create_checkout_session(user)
    db.commit()  # persists razorpay_subscription_id that was just created
    return {"checkout_url": url}


@app.post("/billing/cancel-subscription")
def cancel_subscription(user: User = Depends(get_current_user)):
    try:
        billing.cancel_subscription(user)
        return {"message": "Subscription canceled."}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/billing/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("x-razorpay-signature", "")
    try:
        event = billing.verify_webhook(payload, sig_header)
    except Exception as e:
        raise HTTPException(400, f"Webhook signature verification failed: {e}")
    billing.handle_webhook_event(event, db)
    return {"received": True}


@app.get("/billing/success")
def billing_success():
    return {"message": "Subscription active! You can close this tab and return to the app."}


@app.get("/billing/cancel")
def billing_cancel():
    return {"message": "Checkout canceled."}


# ─── Generation ─────────────────────────────────────────────────────────────

@app.post("/generate")
def generate(req: GenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.has_active_subscription():
        raise HTTPException(402, "No active subscription. Subscribe to generate images.")

    if user.generations_used >= config.GENERATIONS_PER_MONTH:
        raise HTTPException(
            429,
            f"Monthly limit of {config.GENERATIONS_PER_MONTH} generations reached. "
            f"Resets {user.period_end.isoformat() if user.period_end else 'next billing cycle'}.",
        )

    try:
        png_bytes = replicate_client.generate_image(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=req.width,
            height=req.height,
        )
    except Exception as e:
        raise HTTPException(502, f"Image generation failed: {e}")

    user.generations_used += 1
    db.commit()

    return {
        "image_base64": base64.b64encode(png_bytes).decode("ascii"),
        "generations_used": user.generations_used,
        "generations_limit": config.GENERATIONS_PER_MONTH,
    }
