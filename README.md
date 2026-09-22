# TDL Job Card API

Cloud-hosted endpoint that turns a Shopify order into a job-card JSON payload the Illustrator script can drop into place. Deploy once, distribute a single `.jsx` file to every designer.

## Architecture (30 seconds)

```
Designer Illustrator
      │
      ▼   (curl over HTTPS)
https://<your-app>.vercel.app/api/order/5161
      │
      ▼   (server-side Shopify Admin API call)
Shopify → order data → parsed job-card JSON
      ▲
      │
Designer's .jsx script fills the artboard
```

No Python on designer machines. No OAuth per designer. No background service.

## One-time deployment

### 1. Push this repo to GitHub

```bash
cd tdl-jobcard-api
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/tdl-jobcard-api.git
git push -u origin main
```

### 2. Deploy to Vercel

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New** → **Project**
3. Import the `tdl-jobcard-api` repo
4. Framework preset: **Other**
5. Click **Environment Variables** and add:
   - `SHOPIFY_STORE` = `the-design-lap`
   - `SHOPIFY_TOKEN` = `shpat_YOUR_ADMIN_API_ACCESS_TOKEN`
   - `JOBCARD_SECRET` = *(optional)* a random string if you want to require `?key=` on every request
6. Click **Deploy**

After deploy you'll get a URL like `https://tdl-jobcard-api.vercel.app/`

### 3. Test the endpoint

```
https://tdl-jobcard-api.vercel.app/api/order/5161
```

Should return the parsed job-card JSON. If you set `JOBCARD_SECRET`, append `?key=YOUR_SECRET`.

### 4. Point the .jsx script at your deployment

Open `fill_job_card.jsx` and edit these two lines near the top:

```javascript
var ENDPOINT_URL = "https://tdl-jobcard-api.vercel.app/api/order/";
var API_KEY = "";  // or "?key=YOUR_SECRET" if using auth
```

Change `tdl-jobcard-api.vercel.app` to your actual Vercel URL. Commit and push — this way every designer gets the same version from git.

## Per-designer install (2 minutes)

Send each designer:
1. The `fill_job_card.jsx` file
2. This one-line instruction:

> "Put this file at `C:\Program Files\Adobe\Adobe Illustrator 2026\Presets\en_US\Scripts\` (Windows) or `/Applications/Adobe Illustrator 2026/Presets/en_US/Scripts/` (Mac). Restart Illustrator. Then use **File → Scripts → Fill Job Card**. First run asks for your initials."

That's the whole install. No Python. No OAuth. No fetcher.

## Updating the script

When you want to change parsing logic, add checkboxes, etc.:

1. Edit `api/order/[num].py` or `fill_job_card.jsx`
2. `git push`
3. Vercel auto-deploys the Python side within 30 seconds
4. Redistribute the .jsx if that changed (or, better: put it in a shared Dropbox folder your designers pull from)

## Files

| File | Purpose |
|---|---|
| `api/order/[num].py` | Vercel serverless function — GET /api/order/&lt;num&gt; returns the parsed JSON |
| `vercel.json` | Vercel deploy config (Python 3.12 runtime) |
| `fill_job_card.jsx` | Illustrator ExtendScript designers run |
| `.gitignore` | Standard ignores |
| `README.md` | This file |

## Security notes

- The Shopify token is stored in Vercel's env vars — never in git
- `JOBCARD_SECRET` lets you require a `?key=` on every request so random people can't hit your endpoint. Optional but recommended.
- Vercel URLs are public — if you skip the secret, anyone who guesses/finds the URL can pull your order data. Fine for internal-only orgs; consider secret for anything sensitive.

## Troubleshooting

**"Order not found"** — verify the number matches Shopify's `#XXXX` naming.

**500 error** — check Vercel deployment logs. Usually a missing env var.

**"Missing SHOPIFY_STORE or SHOPIFY_TOKEN"** — add them in Vercel dashboard → your project → Settings → Environment Variables → then redeploy.

**Checkbox not toggling for a real order** — pull the order's line item `customAttributes` from Shopify Admin and update `DEFAULT_PATTERNS` in `[num].py`.
