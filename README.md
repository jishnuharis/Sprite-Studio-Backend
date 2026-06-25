# Sprite Studio Cloud API

A small backend that lets your desktop app generate AI images for subscribers
without ever shipping your Replicate API key to the client.

How it fits together:

```
Desktop App  --(email/password)-->  Your Backend  --(your API key)-->  Replicate
                                          |
                                       Stripe (subscriptions)
```

## 1. Get your secrets

- **Replicate API token**: https://replicate.com/account/api-tokens
- **Stripe account**: https://dashboard.stripe.com
  - Create one recurring "Price" for your subscription (e.g. $9.99/month) →
    copy its Price ID (starts with `price_`)
  - Get your Secret key from Developers → API keys (starts with `sk_`)
- **JWT secret**: run `python3 -c "import secrets; print(secrets.token_hex(32))"`

## 2. Deploy to Railway (simplest option)

1. Push this `server/` folder to a GitHub repo.
2. Go to https://railway.app → New Project → Deploy from GitHub repo.
3. Railway auto-detects Python and runs it. Add a **Postgres** plugin from
   Railway's "+ New" menu — it sets `DATABASE_URL` for you automatically.
4. In your service's Variables tab, add:
   ```
   REPLICATE_API_TOKEN=r8_xxxxx
   JWT_SECRET=<from step 1>
   STRIPE_SECRET_KEY=sk_live_xxxxx
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx   (see step 3)
   STRIPE_PRICE_ID=price_xxxxx
   GENERATIONS_PER_MONTH=300
   ```
5. Set the start command to:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Deploy. Railway gives you a public URL like `https://yourapp.up.railway.app`
   — that's the `SPRITE_STUDIO_API_URL` your desktop app will call.

(Render.com works the same way if you'd rather use that.)

## 3. Wire up the Stripe webhook

In the Stripe Dashboard → Developers → Webhooks → Add endpoint:
- URL: `https://yourapp.up.railway.app/billing/webhook`
- Events to send: `checkout.session.completed`, `invoice.payment_succeeded`,
  `customer.subscription.updated`, `customer.subscription.deleted`
- Copy the signing secret it gives you into `STRIPE_WEBHOOK_SECRET`.

## 4. Test locally before deploying

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export REPLICATE_API_TOKEN=r8_xxxxx
export STRIPE_SECRET_KEY=sk_test_xxxxx
export STRIPE_WEBHOOK_SECRET=whsec_xxxxx
export STRIPE_PRICE_ID=price_xxxxx

uvicorn main:app --reload
```

Then:
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}'
```

## Notes / things to harden before going fully live

- This MVP has one subscription tier with a flat monthly generation cap
  (`GENERATIONS_PER_MONTH`). Multiple tiers would mean storing a `plan` on
  the user and mapping each plan to its own Stripe Price ID + cap.
- There's no email verification or password-reset flow yet — fine for an
  early version, but add one before a public launch.
- The desktop app should treat a `401` from any endpoint as "session
  expired" and prompt the user to log in again.
- `MAX_WIDTH`/`MAX_HEIGHT` in `config.py` cap generation size server-side —
  don't remove these, they're what stops a tampered client request from
  costing you more than expected.
