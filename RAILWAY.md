# Host Matrik-N on Railway

Railway builds this folder with the `Dockerfile` and runs gunicorn on `$PORT`.

## 1. Put the code on GitHub

On your computer (or GitHub web):

```bash
git init
git add app.py signal_engine.py index.html config.json requirements.txt Dockerfile railway.json Procfile .gitignore
git commit -m "Matrik-N XAUUSD dashboard"
```

Create an empty repo on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## 2. Deploy on Railway

1. Open [https://railway.app](https://railway.app) and sign in with GitHub.
2. **New Project** → **Deploy from GitHub repo** → pick this repo.
3. Railway should detect `Dockerfile` / `railway.json`.
4. Open the service → **Settings → Networking → Generate Domain**.
   You get a URL like `https://matrik-n-production.up.railway.app`.
5. Optional: **Variables** — Railway injects `PORT` automatically. You can add:
   - `TELEGRAM_BOT_USERNAME=matrixauusdbot`

## 3. Check it

- Site: `https://YOUR-RAILWAY-DOMAIN/`
- API: `https://YOUR-RAILWAY-DOMAIN/api/signal`
- Card: `https://YOUR-RAILWAY-DOMAIN/api/signal/card.png`

First request can take ~10–30s (Yahoo Finance). Health check path is `/api/signal` with a 120s timeout.

## Custom domain

Service → **Settings → Networking → Custom Domain** → add `matrik-n.com` (or similar) and set the CNAME Railway shows at your DNS.

## If the build fails

- Confirm these files are in the **repo root** (same folder as `Dockerfile`).
- Logs: service → **Deployments** → latest → **View logs**.
- Yahoo (`yfinance`) must be reachable outbound; Railway allows that by default.

## Cost

Hobby plan is enough for this dashboard. Sleep/idle depends on your Railway plan.
