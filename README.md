# Sprite Studio Cloud — Backend

This is the small server that lets you sell Sprite Studio without your
end users ever seeing an API key. It holds your real Replicate API token,
authenticates users with email/password, gates AI generation behind an
active Razorpay subscription, and tracks a monthly usage quota per user.

The desktop app talks **only** to this server — never directly to
Replicate or Razorpay.

This backend is deployed completely separately from the desktop app — it's
its own service, with its own repo and its own Railway project. The desktop
app just needs to know its URL (`SPRITE_STUDIO_API_URL`).

---

## How payment works here (Razorpay, not Stripe)

Razorpay Subscriptions don't have a hosted "Checkout page" you redirect to,
the way Stripe does. Instead:

1. The desktop app asks this backend to create a subscription.
2. This backend serves a tiny built-in HTML page (`/billing/checkout-page`) that loads Razorpay's payment widget.
3. The desktop app opens that page in the user's normal web browser.
4. The user pays there; Razorpay calls a webhook back to this server to confirm, which is what actually activates their access (never the in-browser confirmation alone).

You don't need to host that HTML page anywhere yourself — this backend serves it.

---

## What you'll need before you start

- A GitHub account (Railway deploys straight from a repo)
- A [Railway](https://railway.app) account (free tier is enough to start)
- A [Replicate](https://replicate.com) account + API token
- A [Razorpay](https://razorpay.com) account, in **Test Mode** (toggle this in the dashboard — no real business verification needed to test)

Budget about 20–30 minutes for the full setup the first time through.

---

## Step 1 — Push this folder to GitHub

This whole `server` folder is its own repo, separate from the desktop app.

```bash
git init
git add .
git commit -m "Sprite Studio Cloud backend"
git branch -M main
git remote add origin https://github.com/<you>/sprite-studio-backend.git
git push -u origin main
```

(`.env` is intentionally *not* committed — only `.env.example` is. Never
commit real secrets.)

---

## Step 2 — Create the Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
2. Pick the repo you just pushed.
3. Railway detects `requirements.txt` and `Procfile` and starts a Python build automatically. Let this first build fail — expected, since no environment variables are set yet.

---

## Step 3 — Add a Postgres database

1. In your Railway project: **+ New** → **Database** → **Add PostgreSQL**.
2. Railway automatically creates a `DATABASE_URL` variable and shares it with your other service — no copy/pasting needed, as long as both are in the same project.

---

## Step 4 — Get a Replicate API token

1. Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
2. Create a token (starts with `r8_`).
3. You'll paste this into Railway in Step 6.

---

## Step 5 — Set up Razorpay (Test Mode)

### 5a. Switch to Test Mode

In the Razorpay dashboard, use the toggle (usually top-left) to switch into **Test Mode** — everything below uses test keys and test payments, no real money moves.

### 5b. Get your API keys

1. Go to **Settings → API Keys** (or **Account & Settings → API Keys**).
2. Generate Test Mode keys: a **Key ID** (`rzp_test_...`) and **Key Secret**.
3. You'll add both to Railway in Step 6.

### 5c. Create a recurring Plan

1. Go to **Subscriptions → Plans → Create Plan** (still in Test Mode).
2. Set the billing interval to monthly, set your price, give it a name.
3. Save, then copy the **Plan ID** (starts with `plan_`).

### 5d. Create the webhook

You need your Railway URL *first* for this, so:

1. Finish Step 6 below (other env vars set, app deployed and running).
2. Once you have a working URL like `https://your-app.up.railway.app`, go to **Settings → Webhooks → Add New Webhook** in Razorpay (make sure you're still creating this in Test Mode).
3. Webhook URL: `https://your-app.up.railway.app/billing/webhook`
4. Set a **Secret** — type any random string, Razorpay just needs it to sign requests. Copy it for Step 6.
5. Select these **Active Events**:
   - `subscription.authenticated`
   - `subscription.activated`
   - `subscription.charged`
   - `subscription.pending`
   - `subscription.halted`
   - `subscription.cancelled`
   - `subscription.completed`
6. Save.

---

## Step 6 — Set environment variables on Railway

In your Railway service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `JWT_SECRET` | a long random string — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `REPLICATE_API_TOKEN` | your `r8_...` token from Step 4 |
| `RAZORPAY_KEY_ID` | your `rzp_test_...` key from Step 5b |
| `RAZORPAY_KEY_SECRET` | your key secret from Step 5b |
| `RAZORPAY_PLAN_ID` | your `plan_...` ID from Step 5c |
| `RAZORPAY_WEBHOOK_SECRET` | the secret you set in Step 5d (add this *after* your first successful deploy, then redeploy) |
| `PUBLIC_BASE_URL` | your Railway domain once you have one, e.g. `https://your-app.up.railway.app` |
| `GENERATIONS_PER_MONTH` | `300` (or your preferred cap) |

`DATABASE_URL` is already set automatically by the Postgres plugin from Step 3.

After saving, Railway redeploys automatically. Once it's green, get your
public domain under Settings → Networking → Generate Domain (if you don't
have one yet), then come back and set `PUBLIC_BASE_URL` to it and redeploy
once more — this URL is used to build the checkout page link, so it has to
be correct.

---

## Step 7 — Point the desktop app at your backend

In the desktop app's environment, set:

```
SPRITE_STUDIO_API_URL=https://your-app.up.railway.app
```

Without this, the app defaults to `localhost:8000` and Cloud sign-in won't
work.

---

## Step 8 — Test the real flow end-to-end

1. Open the desktop app, sign up for a new account.
2. Click **Subscribe** — your browser opens this server's own checkout page, with Razorpay's payment widget on it.
3. Pay using a [Razorpay test card](https://razorpay.com/docs/payments/payments/test-card-upi-details/) (while still in Test Mode) — e.g. card `4111 1111 1111 1111`, any future expiry, any CVV.
4. After paying, the page shows a confirmation message. Close the tab and go back to the app.
5. Click **Refresh** in the Account panel — your subscription should show as active (this can take a few seconds, since it depends on the webhook arriving).
6. Try generating an image from the Cloud tab — it should call Replicate for real now.

If something doesn't activate, check:
- Railway service logs (Deployments → View Logs) for errors
- Razorpay dashboard → **Webhooks** → click your endpoint → see delivery attempts and responses, which will show you exactly what was sent and whether your server accepted it

---

## Local development (optional)

```bash
cp .env.example .env   # then fill in real values
pip install -r requirements.txt
uvicorn main:app --reload
```

This runs against a local SQLite file (`sprite_studio.db`) instead of
Postgres, so you can test signup/login/`/me` without touching Railway.
Razorpay's webhook won't reach `localhost` directly — use the
[Razorpay CLI](https://razorpay.com/docs/webhooks/test/) or a tunneling tool
like ngrok if you want to test webhooks locally; otherwise just test against
the deployed Railway instance.

---

## Going live later

When you're ready for real payments:

1. In Razorpay, complete KYC/business verification and switch out of Test Mode.
2. Repeat Step 5 with live keys (`rzp_live_...`), a live Plan, and a new live-mode webhook + secret.
3. Update the Railway variables with the live values.
4. Everything else stays the same.
