# TrueSight — Sprint 3 (Final Sprint)

**AI-powered hybrid image verification.** TrueSight checks whether an uploaded image matches a previously registered image using a hybrid of perceptual hashing and CLIP neural embeddings.

This Sprint 3 build is the final capstone deliverable. It packages the work of Sprints 1 and 2 into a polished, demo-ready, deploy-ready system.

---

## What's New in Sprint 3

- **Hybrid scoring model finalized:**
  `hybrid_score = 0.55 × pHash similarity + 0.45 × CLIP similarity`
- **Verdict surface fully wired** through the API and UI:
  `Exact Match` · `Near Duplicate` · `Semantically Similar` · `Different` · `Not Registered`
- **Frontend** updated to show pHash similarity, CLIP similarity, hybrid score, trust score, verdict, best match, and tags side-by-side, with proper loading, empty, and error states.
- **Vercel deployment ready** for the frontend, with `VITE_API_URL` env-var support so the deployed UI can talk to a backend hosted anywhere.
- **Configurable CORS** on the backend via the `FRONTEND_ORIGINS` env var.

---

## Architecture

```
truesight-main/
├── backend/                  FastAPI + SQLite + pHash + CLIP
│   ├── app.py
│   ├── ledger.py             (cryptographic ledger helper, available for future use)
│   ├── requirements.txt
│   └── storage/              SQLite DB + uploaded images (gitignored)
├── frontend/                 React + Vite SPA
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── frontend/vercel.json      Vercel build config (frontend only)
├── .gitignore
└── README.md
```

The backend is intentionally split from the frontend so each can be deployed independently. The frontend reads its API base URL from `VITE_API_URL` at build time.

---

## Tech Stack

**Backend:** FastAPI · SQLite · OpenCLIP (ViT-B-32) · Pillow · NumPy · PyTorch
**Frontend:** React 18 · Vite 5 · plain CSS-in-JS (no UI framework)
**Deployment:** Vercel (frontend) · Render / Fly.io / Railway (backend)

---

## Hybrid Scoring Model

Every analysis returns three signals plus a final trust score:

| Signal | Source | What it captures |
|--------|--------|------------------|
| **pHash similarity** | DCT-based perceptual hash | Structural / pixel-level similarity |
| **CLIP similarity** | OpenCLIP ViT-B-32 image embedding cosine | Semantic / content similarity |
| **Hybrid score** | `0.55 × pHash + 0.45 × CLIP` | Combined confidence |
| **Trust score** | Verdict-driven calibration of the hybrid score | Final confidence shown to the user |

### Verdict thresholds

| Condition | Verdict |
|-----------|---------|
| No registrations exist | `not_registered` |
| `pHash ≥ 0.98` AND `CLIP ≥ 0.98` | `exact_match` |
| `hybrid ≥ 0.88` OR `pHash ≥ 0.90` | `near_duplicate` |
| `CLIP ≥ 0.85` | `semantically_similar` |
| otherwise | `different` |

If the optional ML libs (`torch`, `open_clip_torch`) fail to load, the backend transparently falls back to a lightweight RGB embedding so the pipeline keeps working — the response field `embedding_backend` reports which path was used.

---

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`                      | Service banner + route list |
| `GET`  | `/health`                | Health + embedding backend + registration count |
| `POST` | `/register`              | Register an image (SHA-256 + pHash + CLIP embedding) |
| `POST` | `/analyze`               | Analyze an image and return verdict + similarities |
| `GET`  | `/history/registrations` | Recent registrations |
| `GET`  | `/history/analyses`      | Recent analyses |
| `GET`  | `/docs`                  | Interactive Swagger UI |

### `/analyze` response shape

```json
{
  "content_sha256": "...",
  "phash": "...",
  "embedding_backend": "open_clip_vit_b_32",
  "best_match": {
    "content_sha256": "...",
    "phash_match_sha256": "...",
    "clip_match_sha256": "...",
    "phash_similarity": 0.9421,
    "clip_similarity": 0.8873,
    "hybrid_score": 0.9175
  },
  "result": {
    "trust": 0.9175,
    "verdict": "near_duplicate"
  },
  "tags": ["near_duplicate", "structural_match"],
  "note": "Sprint 3 hybrid verification: 0.55 * pHash + 0.45 * CLIP similarity."
}
```

---

## Local Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

The backend will be reachable at:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

> The first request after a cold start downloads the OpenCLIP weights (~150 MB) the first time. Subsequent runs use the local cache.

### 2. Frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env        # optional; default already points to localhost:8000
npm install
npm run dev
```

Open http://localhost:5173.

---

## Smoke Test (5 minutes)

Run through this checklist before demoing:

1. **Register the same image** → expect `status: registered`, then `status: already_registered` on a second submit.
2. **Analyze the same image** → expect `verdict: exact_match`, both similarities ≈ 1.0.
3. **Analyze a near-duplicate** (e.g. resized or re-saved JPEG of the original) → expect `near_duplicate` with high pHash.
4. **Analyze a semantically related image** (different photo of the same subject) → expect `semantically_similar` with high CLIP, lower pHash.
5. **Analyze an unrelated image** → expect `different` with low scores.
6. **Click History** → both Analyses and Registrations tabs populate.
7. **Upload an invalid file** (e.g. a `.txt` renamed to `.jpg`) → expect a 400 error and a red error toast in the UI.

---

## Deployment

### Frontend on Vercel

Only the `frontend/` workspace deploys to Vercel. The backend will not work on Vercel — see the next section.

1. Push this repo to GitHub.
2. On https://vercel.com → **Add New Project** → import the GitHub repo.
3. **Set Root Directory to `frontend`** (this is the most important step — Vercel's project wizard lets you pick a subdirectory; pick `frontend`).
4. Vercel will auto-detect **Vite** as the framework. Leave the build/output commands at their defaults.
5. In **Environment Variables**, add:
   - `VITE_API_URL` = the public URL of your deployed backend (see below).
6. Click **Deploy**.

Subsequent pushes to `main` redeploy automatically. The `frontend/vercel.json` adds a SPA-style rewrite so client-side routes don't 404 on refresh.

> **Common mistake:** Do not set Root Directory to `backend`. The backend cannot run on Vercel; deploying it there fails with `ENOENT … backend/frontend/package.json` or similar errors. If you already created a misconfigured Vercel project, open **Project → Settings → General → Root Directory**, change it to `frontend`, and redeploy.

### Backend — *not* on Vercel

The backend cannot run on Vercel's serverless functions because:
- PyTorch + OpenCLIP weights exceed Vercel's 250 MB function size limit.
- SQLite + uploaded images need persistent disk; Vercel's filesystem is ephemeral.
- CLIP cold-start latency is far above Vercel's serverless timeouts.

**Recommended host: [Render](https://render.com)** (free tier supports persistent disks, longer cold starts, and Python web services).

Quick Render setup:
1. Create a **Web Service** pointing at this repo.
2. **Root directory:** `backend`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`
5. **Environment variables:**
   - `FRONTEND_ORIGINS` = your Vercel URL(s), comma-separated (e.g. `https://truesight.vercel.app,https://truesight-main.vercel.app`)
6. (Optional) attach a persistent disk mounted at `backend/storage` so the SQLite DB survives redeploys.

Once Render gives you a URL like `https://truesight-api.onrender.com`, paste it into Vercel's `VITE_API_URL` env var and redeploy the frontend.

Fly.io and Railway also work; the build/start commands above are portable.

---

## Environment Variables

| Where | Name | Purpose |
|-------|------|---------|
| Frontend | `VITE_API_URL` | Base URL of the backend API (build-time) |
| Backend  | `FRONTEND_ORIGINS` | Extra CORS origins, comma-separated |

`localhost:5173` and `127.0.0.1:5173` are always allowed in CORS for local dev — no env var needed for that case.

No secrets are ever required by the application code. Do not commit `.env` files; only `.env.example` is tracked.

---

## Authors

TrueSight Capstone Team — CS 691 Computer Science Capstone Project.
