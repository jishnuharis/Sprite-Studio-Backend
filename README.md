# Sprite Studio Cloud — Backend

This is the small server that lets you sell Sprite Studio without your
end users ever seeing an API key. It holds your real Replicate API token,
authenticates users with email/password, gates AI generation behind an
active Razorpay subscription, and tracks a monthly usage quota per user.

The desktop app talks **only** to this server — never directly to
Replicate or Razorpay.

This backend is deployed completely separately from the desktop app (which
lives in the sibling `app/` folder, with its own README). It's its own
service, with its own repo and its own Render web service. The desktop app
just needs to know this server's URL (`SPRITE_STUDIO_API_URL`).

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

- A GitHub account (Render deploys straight from a repo)
- A [Render](https://render.com) account (the free tier is enough to start — see the cold-start note below)
- A [Replicate](https://replicate.com) account + API token
- A [Razorpay](https://razorpay.com) account, in **Test Mode** (toggle this in the dashboard — no real business verification needed to test)

Budget about 20–30 minutes for the full setup the first time through.

> **Free tier heads-up:** Render's free web services spin down after about
> 15 minutes with no traffic, and take 30–50 seconds to wake back up on the
> next request. That means the first cloud sign-in or generation after a
> quiet period will feel slow/stuck before it suddenly works — that's normal,
> not a bug. Upgrade to a paid Render instance once you have real users to
> avoid this.

---

## Step 1 — Push this folder to GitHub

This `server` folder is its own repo, separate from the `app/` folder.

```bash
cd server
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

## Step 2 — Create the Render Postgres database

1. In the Render dashboard: **New +** → **PostgreSQL**.
2. Give it a name, pick the free plan to start, create it.
3. Once it's up, open it and copy the **Internal Database URL** (not the
   external one — internal is free and faster since both services live in
   the same Render network). You'll paste this in Step 4.

---

## Step 3 — Create the web service

1. **New +** → **Web Service** → connect the GitHub repo you just pushed.
2. Render should detect Python automatically. Set these explicitly to be sure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

   (There's also a `Procfile` in this folder with the same start command,
   which some Render service types pick up automatically — but setting the
   Start Command explicitly in the dashboard is the most reliable way to
   make sure it's used.)
3. Pick the free instance type to start, then **Create Web Service**. Let
   this first deploy fail — expected, since no environment variables are
   set yet. Your service's URL (something like `https://your-app.onrender.com`)
   is shown at the top of its page as soon as it's created; copy it, you'll
   need it in Step 4 and Step 6.

---

## Step 4 — Get a Replicate API token

1. Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
2. Create a token (starts with `r8_`).
3. You'll paste this into Render in Step 6.

---

## Step 5 — Set up Razorpay (Test Mode)

### 5a. Switch to Test Mode

In the Razorpay dashboard, use the toggle (usually top-left) to switch into **Test Mode** — everything below uses test keys and test payments, no real money moves.

### 5b. Get your API keys

1. Go to **Settings → API Keys** (or **Account & Settings → API Keys**).
2. Generate Test Mode keys: a **Key ID** (`rzp_test_...`) and **Key Secret**.
3. You'll add both to Render in Step 6.

### 5c. Create a recurring Plan

1. Go to **Subscriptions → Plans → Create Plan** (still in Test Mode).
2. Set the billing interval to monthly, set your price, give it a name.
3. Save, then copy the **Plan ID** (starts with `plan_`).

### 5d. Create the webhook

You need your Render URL *first* for this, so:

1. Finish Step 6 below (other env vars set, app deployed and running).
2. Using your Render URL from Step 3 (e.g. `https://your-app.onrender.com`), go to **Settings → Webhooks → Add New Webhook** in Razorpay (make sure you're still creating this in Test Mode).
3. Webhook URL: `https://your-app.onrender.com/billing/webhook`
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

## Step 6 — Set environment variables on Render

In your Render web service → **Environment** tab, add:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Internal Database URL you copied in Step 2 |
| `JWT_SECRET` | a long random string — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `REPLICATE_API_TOKEN` | your `r8_...` token from Step 4 |
| `RAZORPAY_KEY_ID` | your `rzp_test_...` key from Step 5b |
| `RAZORPAY_KEY_SECRET` | your key secret from Step 5b |
| `RAZORPAY_PLAN_ID` | your `plan_...` ID from Step 5c |
| `RAZORPAY_WEBHOOK_SECRET` | the secret you set in Step 5d (add this *after* your first successful deploy, then redeploy) |
| `PUBLIC_BASE_URL` | your Render URL from Step 3, e.g. `https://your-app.onrender.com` |
| `GENERATIONS_PER_MONTH` | `300` (or your preferred cap) |

Saving triggers a redeploy automatically. Once it's live, double check
`PUBLIC_BASE_URL` matches your actual Render URL exactly — it's used to
build the checkout page link, so it has to be correct.

---

## Step 7 — Point the desktop app at your backend

In the desktop app's environment (see `app/README.md`), set:

```
SPRITE_STUDIO_API_URL=https://your-app.onrender.com
```

Without this, the app defaults to `localhost:8000` and Cloud sign-in won't
work.

---

## Step 8 — Test the real flow end-to-end

1. Open the desktop app, sign up for a new account.
2. Click **Upgrade to Pro** — your browser opens this server's own checkout page, with Razorpay's payment widget on it.
3. Pay using a [Razorpay test card](https://razorpay.com/docs/payments/payments/test-card-upi-details/) (while still in Test Mode) — e.g. card `4111 1111 1111 1111`, any future expiry, any CVV.
4. After paying, the page shows a confirmation message. Close the tab and go back to the app.
5. Open the Account panel — your subscription should show as active within a few seconds (it depends on the webhook arriving, so give it a moment and reopen the panel if needed).
6. Try generating an image from the Cloud tab — it should call Replicate for real now.

If something doesn't activate, check:
- Render service logs (your service → **Logs** tab) for errors
- Razorpay dashboard → **Webhooks** → click your endpoint → see delivery attempts and responses, which will show you exactly what was sent and whether your server accepted it

---

## Local development (optional)

```bash
cp .env.example .env   # then fill in real values
pip install -r requirements.txt
uvicorn main:app --reload
```

This runs against a local SQLite file (`sprite_studio.db`) instead of
Postgres, so you can test signup/login/`/me` without touching Render.
Razorpay's webhook won't reach `localhost` directly — use the
[Razorpay CLI](https://razorpay.com/docs/webhooks/test/) or a tunneling tool
like ngrok if you want to test webhooks locally; otherwise just test against
the deployed Render instance.

---

## Security notes

- Passwords are hashed with bcrypt and never stored or logged in plaintext.
- Sessions are signed JWTs (30-day expiry by default, `JWT_EXPIRES_DAYS`).
  There's no server-side revocation list, so "sign out" is client-side only
  — good enough for this app, but know that a stolen token stays valid until
  it expires.
- `/auth/login` and `/auth/signup` are rate-limited per IP
  (`AUTH_RATE_LIMIT_MAX` per `AUTH_RATE_LIMIT_WINDOW_SECONDS`), and an
  account locks out for `ACCOUNT_LOCKOUT_SECONDS` after
  `MAX_FAILED_LOGIN_ATTEMPTS` wrong passwords in a row, to slow down
  credential-stuffing and brute-force attempts.
- Both of those protections are in-memory, scoped to one process. Render's
  free/starter tiers run a single instance, so that's fine out of the box.
  If you scale to multiple instances, move `ratelimit.py`'s storage to
  something shared (e.g. Redis) so limits apply across all of them.
- Login/signup error messages are deliberately generic ("Incorrect email or
  password") so they don't reveal whether a given email is registered.
- There's no email verification or "forgot password" flow yet — anyone who
  knows the current password can change it from inside the app, but there's
  no recovery path if it's forgotten. Worth adding before a real public launch.

---

## Going live later

When you're ready for real payments:

1. In Razorpay, complete KYC/business verification and switch out of Test Mode.
2. Repeat Step 5 with live keys (`rzp_live_...`), a live Plan, and a new live-mode webhook + secret.
3. Update the Render environment variables with the live values.
4. Consider upgrading off Render's free tier so the service doesn't spin
   down between requests.
5. Everything else stays the same.
