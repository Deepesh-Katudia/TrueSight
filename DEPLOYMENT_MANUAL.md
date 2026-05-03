# TrueSight Deployment Manual

## 1. Audience

This manual is intended for system administrators, IT support staff, DevOps engineers, and project maintainers who need to deploy, configure, verify, or troubleshoot TrueSight.

The reader should be comfortable with:

- Git and GitHub repositories
- Python virtual environments
- Node.js and npm
- Basic command-line usage on Windows, macOS, or Linux
- Vercel and Render dashboards for cloud deployment

## 2. Deployment Overview

TrueSight is deployed as two services:

| Component | Technology | Host | URL |
|-----------|------------|------|-----|
| Frontend | React 18 + Vite | Vercel | `https://frontend-lac-eight-77.vercel.app` |
| Backend API | FastAPI + SQLite + image embeddings | Render Free Web Service | `https://truesight-backend-lw79.onrender.com` |

The frontend communicates with the backend through the build-time environment variable `VITE_API_URL`.

The backend allows browser requests from the Vercel frontend through the `FRONTEND_ORIGINS` environment variable.

Render Free has a 512 MiB memory limit, so the deployed backend uses:

```text
TRUESIGHT_EMBEDDING_BACKEND=fallback
```

This keeps the backend within the free memory limit by using pHash plus the lightweight RGB embedding fallback instead of loading PyTorch/OpenCLIP.

## 3. Repository Layout

```text
truesight-main/
  backend/
    app.py
    ledger.py
    requirements.txt
    requirements-render.txt
    storage/
  frontend/
    src/
    package.json
    package-lock.json
    vercel.json
  render.yaml
  README.md
  DEPLOYMENT_MANUAL.md
```

## 4. Prerequisites

### 4.1 Common Requirements

Install these on every deployment workstation:

| Tool | Required Version | Purpose |
|------|------------------|---------|
| Git | Current stable | Clone and push the repository |
| Python | 3.11 recommended | Run the FastAPI backend |
| Node.js | 18 or newer | Build and run the Vite frontend |
| npm | Bundled with Node.js | Install frontend dependencies |
| Browser | Current Chrome, Edge, Firefox, or Safari | Verify the UI |

### 4.2 Cloud Accounts

Required cloud accounts:

- GitHub account with access to `Deepesh-Katudia/TrueSight`
- Render account connected to the GitHub repository
- Vercel account or team `codewithdeepesh29s-projects`

### 4.3 Backend Dependency Sets

Use the correct requirements file for the deployment target:

| Target | Requirements File | Notes |
|--------|-------------------|-------|
| Local full ML development | `backend/requirements.txt` | Installs PyTorch and OpenCLIP |
| Render Free deployment | `backend/requirements-render.txt` | Avoids PyTorch/OpenCLIP memory pressure |

## 5. Platform-Specific Local Deployment

These instructions run TrueSight locally. Use them before or after cloud deployment to verify behavior.

### 5.1 Windows

Open PowerShell from the repository root.

#### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

If PowerShell blocks activation scripts, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Backend local URL:

```text
http://localhost:8000
```

#### Frontend

Open a second PowerShell window.

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend local URL:

```text
http://localhost:5173
```

### 5.2 macOS

Open Terminal from the repository root.

#### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

#### Frontend

Open a second Terminal window.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### 5.3 Linux

Open a terminal from the repository root.

#### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

If `python3 -m venv` is unavailable on Debian or Ubuntu:

```bash
sudo apt update
sudo apt install python3-venv
```

#### Frontend

Open a second terminal window.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## 6. Cloud Deployment Instructions

### 6.1 Backend Deployment on Render

The backend is deployed from the root `render.yaml` Blueprint.

Current Render backend URL:

```text
https://truesight-backend-lw79.onrender.com
```

Health endpoint:

```text
https://truesight-backend-lw79.onrender.com/health
```

Render Blueprint settings:

| Setting | Value |
|---------|-------|
| Service name | `truesight-backend` |
| Runtime | Python |
| Plan | Free |
| Root directory | `backend` |
| Build command | `pip install --upgrade pip && pip install -r requirements-render.txt` |
| Start command | `python -m uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Render environment variables:

| Variable | Value |
|----------|-------|
| `PYTHON_VERSION` | `3.11.9` |
| `TRUESIGHT_EMBEDDING_BACKEND` | `fallback` |
| `FRONTEND_ORIGINS` | `https://frontend-lac-eight-77.vercel.app,https://frontend-codewithdeepesh29s-projects.vercel.app,https://frontend-codewithdeepesh29-codewithdeepesh29s-projects.vercel.app` |

Deployment steps:

1. Push the latest repository changes to GitHub.
2. Open Render.
3. Choose **New** -> **Blueprint**.
4. Connect the GitHub repository `Deepesh-Katudia/TrueSight`.
5. Select the `main` branch.
6. Confirm Render detects `render.yaml`.
7. Deploy the Blueprint.
8. Wait for the service to show a live state.
9. Open `/health` and confirm the backend returns JSON.

Expected health response:

```json
{
  "status": "ok",
  "version": "Sprint 3",
  "embedding_backend": "fallback_rgb_embedding",
  "registrations": 5
}
```

### 6.2 Frontend Deployment on Vercel

Current Vercel frontend URL:

```text
https://frontend-lac-eight-77.vercel.app
```

Current production deployment:

```text
dpl_Fz47BCq9CFZF4BxUacAPUxLwjQUm
```

Vercel project settings:

| Setting | Value |
|---------|-------|
| Project | `frontend` |
| Root directory | `frontend` |
| Framework | Vite |
| Build command | `npm run build` |
| Output directory | `dist` |

Vercel environment variable:

| Variable | Environment | Value |
|----------|-------------|-------|
| `VITE_API_URL` | Production | `https://truesight-backend-lw79.onrender.com` |

Deployment steps:

1. Open Vercel.
2. Select the `frontend` project.
3. Confirm the root directory is `frontend`.
4. Open **Settings** -> **Environment Variables**.
5. Confirm `VITE_API_URL` exists in Production.
6. Set `VITE_API_URL` to the Render backend URL if it changed.
7. Redeploy the production frontend.

CLI deployment command:

```bash
cd frontend
npx vercel deploy --prod --yes --scope codewithdeepesh29s-projects
```

## 7. Configuration Instructions

### 7.1 Backend CORS

The backend reads allowed frontend origins from:

```text
FRONTEND_ORIGINS
```

Production value:

```text
https://frontend-lac-eight-77.vercel.app,https://frontend-codewithdeepesh29s-projects.vercel.app,https://frontend-codewithdeepesh29-codewithdeepesh29s-projects.vercel.app
```

Local development origins are always allowed by the backend:

```text
http://localhost:5173
http://127.0.0.1:5173
```

### 7.2 Frontend API URL

The frontend reads the backend base URL from:

```text
VITE_API_URL
```

Production value:

```text
https://truesight-backend-lw79.onrender.com
```

Local development value:

```text
http://localhost:8000
```

Because this is a Vite build-time variable, changing it requires a new frontend build and deployment.

### 7.3 Storage

The backend stores SQLite data and uploaded images under:

```text
backend/storage/
```

Render Free uses ephemeral disk. Data may be lost after restarts, redeploys, or service replacement.

For durable production data, use one of these options:

- Upgrade Render and attach a persistent disk mounted at `backend/storage`
- Move relational data to Render Postgres
- Move uploaded images to object storage

## 8. Deployment Scripts and Snippets

### 8.1 Windows Local Startup Script

Save as `scripts/start-local-windows.ps1` if needed:

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn app:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
```

### 8.2 macOS/Linux Local Startup Script

Save as `scripts/start-local.sh` if needed:

```bash
#!/usr/bin/env bash
set -e

(cd backend && source .venv/bin/activate && python -m uvicorn app:app --reload --port 8000) &
(cd frontend && npm run dev) &

wait
```

### 8.3 Vercel Environment Update

Use this when the Render backend URL changes:

```bash
cd frontend
vercel env rm VITE_API_URL production --yes --scope codewithdeepesh29s-projects
printf "https://truesight-backend-lw79.onrender.com" | vercel env add VITE_API_URL production --scope codewithdeepesh29s-projects
vercel deploy --prod --yes --scope codewithdeepesh29s-projects
```

### 8.4 Backend Health Check

PowerShell:

```powershell
(Invoke-WebRequest -UseBasicParsing https://truesight-backend-lw79.onrender.com/health).Content
```

Bash:

```bash
curl https://truesight-backend-lw79.onrender.com/health
```

## 9. Testing the Deployment

### 9.1 Backend Smoke Test

Open:

```text
https://truesight-backend-lw79.onrender.com/health
```

Expected:

- `status` is `ok`
- `version` is `Sprint 3`
- `embedding_backend` is `fallback_rgb_embedding` on Render Free

### 9.2 Frontend Smoke Test

Open:

```text
https://frontend-lac-eight-77.vercel.app
```

Expected:

- The TrueSight UI loads without a blank screen.
- Upload controls are visible.
- Register and analyze actions can reach the backend.

### 9.3 End-to-End Functional Test

1. Open the frontend URL.
2. Register a valid PNG or JPG image.
3. Register the same image again.
4. Confirm the second registration reports an existing or duplicate registration state.
5. Analyze the same image.
6. Confirm the result includes:
   - pHash similarity
   - embedding backend
   - hybrid score
   - trust score
   - verdict
7. Open the history view and confirm recent registrations or analyses are listed.

### 9.4 Local Verification Commands

Backend syntax and regression test:

```bash
cd backend
python -m py_compile app.py ledger.py test_render_fallback.py
python -m unittest test_render_fallback.py
```

Frontend build:

```bash
cd frontend
npm run build
```

## 10. Troubleshooting

### 10.1 Render: Out of Memory

Symptom:

```text
Out of memory (used over 512Mi)
```

Cause:

The backend attempted to load PyTorch/OpenCLIP on Render Free.

Fix:

- Confirm `render.yaml` uses `requirements-render.txt`.
- Confirm `TRUESIGHT_EMBEDDING_BACKEND=fallback`.
- Redeploy the Render backend.

### 10.2 Render: No Open Ports Detected

Symptom:

```text
No open ports detected
```

Cause:

The backend did not bind to Render's `$PORT`, or startup crashed before binding.

Fix:

Confirm the start command is:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port $PORT
```

Then check logs for any earlier startup crash.

### 10.3 Frontend Cannot Reach Backend

Symptoms:

- Upload actions fail.
- Browser console shows CORS errors.
- Browser console shows network request failures.

Fix:

1. Confirm `VITE_API_URL` in Vercel is:

   ```text
   https://truesight-backend-lw79.onrender.com
   ```

2. Confirm Render `FRONTEND_ORIGINS` includes the active Vercel URL.
3. Redeploy the backend if `FRONTEND_ORIGINS` changed.
4. Redeploy the frontend if `VITE_API_URL` changed.

### 10.4 Backend Works Locally but Not on Render

Likely causes:

- Render is using `requirements-render.txt`, so full OpenCLIP is disabled.
- Render Free disk is ephemeral.
- Render Free service is sleeping and needs a cold start.

Fix:

- Wait for the first request to wake the service.
- Check `/health`.
- Review Render logs.
- Use a paid Render instance for full OpenCLIP or persistent disk.

### 10.5 Vercel Deployment Uses Old Backend URL

Cause:

`VITE_API_URL` is a build-time variable.

Fix:

1. Update `VITE_API_URL` in Vercel.
2. Redeploy the frontend.
3. Hard-refresh the browser.

### 10.6 Python Package Installation Fails

Fixes:

- Confirm Python 3.11 is used.
- Upgrade pip before installing dependencies.
- For Render Free, install `requirements-render.txt`.
- For local full ML development, install `requirements.txt`.

## 11. Rollback

### 11.1 Frontend Rollback

Use the Vercel dashboard:

1. Open the `frontend` project.
2. Go to **Deployments**.
3. Select the last known-good deployment.
4. Promote or redeploy it.

### 11.2 Backend Rollback

Use Render:

1. Open the `truesight-backend` service.
2. Go to deploy history.
3. Select the last known-good commit.
4. Redeploy that commit.

Alternatively, revert the Git commit and push `main`; Render auto-deploys from the connected branch.

## 12. Maintenance Notes

- Keep `render.yaml` and the Render dashboard settings in sync.
- Keep Vercel `VITE_API_URL` synchronized with the active backend URL.
- Keep Render `FRONTEND_ORIGINS` synchronized with active Vercel aliases.
- Do not commit `.env` files.
- Render Free is appropriate for demos, not durable production storage.
- Full OpenCLIP scoring requires more memory than Render Free provides.
