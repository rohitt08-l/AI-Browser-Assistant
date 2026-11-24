# Deployment & CI/CD

Every pull request to `main` is linted, tested and built. Every merge to `main` then deploys the backend to **Render** and publishes the packaged **Chrome extension** as a GitHub Release.

```text
PR opened/updated ──► Backend lint & tests ─┐
                      Extension checks ─────┼──► ✅ required checks (no deploy)
                      Docker build & smoke ─┘

Merge to main ──────► same 3 jobs ──► Deploy to Render ──► wait for /health to report the new commit
                                                       └─► Package extension (prod URL) ──► GitHub Release
```

Render's own auto-deploy is **off** (`autoDeploy: false` in `render.yaml`). Deploys are triggered only by the pipeline, after every check has passed, so a broken build never ships.

---

## One-time setup (about 10 minutes)

### 1. Create the Render service

1. Sign up at [render.com](https://render.com) with your GitHub account.
2. Go to **New → Blueprint**, pick this repository, and confirm. Render reads `render.yaml` and creates the `ai-browser-assistant-api` web service (Docker, free plan).
3. When prompted, fill in the secret env vars. At minimum set `GROQ_API_KEY`, or switch `LLM_PROVIDER` to `azure` and fill in the Azure values.
4. Wait for the first deploy. Then open `https://<your-service>.onrender.com/health`, which should return `{"status":"ok", ...}`.

### 2. Connect GitHub Actions to Render

1. In Render, open the service, go to **Settings → Deploy Hook**, and copy the URL.
2. In GitHub, open the repo and go to **Settings → Secrets and variables → Actions**:
   - **Secrets** tab, **New repository secret**: name `RENDER_DEPLOY_HOOK_URL`, value is the hook URL.
   - **Variables** tab, **New repository variable**: name `BACKEND_URL`, value `https://<your-service>.onrender.com`.

`BACKEND_URL` is used to confirm the new version is live, and is baked into the released extension as its default backend.

### 3. Protect `main` (recommended)

In GitHub, go to **Settings → Branches → Add rule** for `main`:
- Require a pull request before merging
- Require status checks to pass: `Backend lint & tests`, `Extension checks`, `Docker build & smoke test`

---

## Day-to-day

| You do | The pipeline does |
|---|---|
| Open or update a PR | Runs lint, tests, extension checks and the Docker build. A dev extension zip is attached to the run. |
| Merge to `main` | Runs all checks, deploys to Render, waits until `/health` reports the merged commit, packages the extension |
| Bump `"version"` in `extension/manifest.json` and merge | Also creates a GitHub Release `extension-vX.Y.Z` with the store-ready zip |
| Need to redeploy without a code change | **Actions → CI/CD → Run workflow** on `main` |

**Publishing the extension:** download the zip from the latest GitHub Release and upload it in the [Chrome Web Store developer dashboard](https://chrome.google.com/webstore/devconsole). After the first publish, lock CORS to your extension by setting `CORS_ALLOW_ORIGIN_REGEX=^chrome-extension://<extension-id>$` in Render.

---

## Notes

- **Free-tier cold starts:** Render's free plan sleeps after about 15 minutes idle, so the first request then takes around 30–60 seconds. Upgrade the plan in `render.yaml` (`plan: starter`) for always-on.
- **Generated PDFs** are stored on the instance's temporary disk and expire after an hour. A restart or redeploy clears them.
- **Running the image locally:**
  ```bash
  docker build -t ai-browser-assistant .
  ```
  ```bash
  docker run -p 8000:8000 --env-file .env ai-browser-assistant
  ```
- **Rollback:** in Render, open **Events**, pick a previous deploy and choose **Rollback**. Or revert the commit on `main`, which redeploys through the pipeline.
