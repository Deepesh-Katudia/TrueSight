import io
import os
import json
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import numpy as np
from PIL import Image, UnidentifiedImageError

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Optional ML imports for Sprint 3 hybrid scoring (pHash + CLIP).
# If unavailable, the app falls back to a lightweight image embedding.
try:
    import torch
except ImportError:
    torch = None

try:
    import open_clip
except ImportError:
    open_clip = None

try:
    import clip as openai_clip
except ImportError:
    openai_clip = None


# -----------------------------
# App + CORS
# -----------------------------
app = FastAPI()

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
extra_origins_env = os.getenv("FRONTEND_ORIGINS", "")
extra_origins = [o.strip() for o in extra_origins_env.split(",") if o.strip()]
ALLOW_ORIGINS = DEFAULT_ORIGINS + extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Paths / DB
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)
DB_PATH = os.path.join(STORAGE_DIR, "truesight.db")

# -----------------------------
# In-memory stores
# -----------------------------
PHASH_STORE: Dict[str, str] = {}          # sha256 -> phash hex
EMBEDDING_STORE: Dict[str, List[float]] = {}  # sha256 -> normalized embedding vector

# -----------------------------
# CLIP / Embedding backend cache
# -----------------------------
CLIP_BACKEND = None
CLIP_MODEL = None
CLIP_PREPROCESS = None
CLIP_DEVICE = "cpu"
EMBEDDING_BACKEND_MODE = os.getenv("TRUESIGHT_EMBEDDING_BACKEND", "auto").strip().lower()


# -----------------------------
# Utilities
# -----------------------------
def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_image_or_400(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img.convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Invalid or unsupported image. Please upload a PNG or JPG file."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read image: {e}")


def json_dumps_vector(v: List[float]) -> str:
    return json.dumps([float(x) for x in v])


def json_loads_vector(s: Optional[str]) -> List[float]:
    if not s:
        return []
    try:
        data = json.loads(s)
        return [float(x) for x in data]
    except Exception:
        return []


# -----------------------------
# Perceptual Hash (pHash)
# -----------------------------
def compute_phash(img: Image.Image, size: int = 32, smaller: int = 8) -> str:
    x = img.convert("L").resize((size, size))
    arr = np.asarray(x, dtype=np.float32)

    freq = np.fft.fft2(arr)
    mag = np.abs(freq)[:smaller, :smaller]

    med = np.median(mag[1:, 1:])  # ignore DC component
    bits = (mag > med).astype(np.uint8).flatten()

    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)

    hex_len = (len(bits) + 3) // 4
    return f"{out:0{hex_len}x}"


def phash_similarity(h1: str, h2: str) -> float:
    if not h1 or not h2 or len(h1) != len(h2):
        return 0.0

    b1 = bin(int(h1, 16))[2:].zfill(len(h1) * 4)
    b2 = bin(int(h2, 16))[2:].zfill(len(h2) * 4)

    same = sum(1 for a, b in zip(b1, b2) if a == b)
    return same / len(b1)


# -----------------------------
# CLIP / Embedding Support
# -----------------------------
def load_clip_backend() -> str:
    """
    Tries to load a real CLIP backend.
    Falls back to a lightweight embedding if CLIP libs are unavailable.
    """
    global CLIP_BACKEND, CLIP_MODEL, CLIP_PREPROCESS, CLIP_DEVICE

    if CLIP_BACKEND is not None:
        return CLIP_BACKEND

    if EMBEDDING_BACKEND_MODE in {"fallback", "fallback_rgb_embedding", "rgb"}:
        CLIP_BACKEND = "fallback_rgb_embedding"
        return CLIP_BACKEND

    if torch is not None and torch.cuda.is_available():
        CLIP_DEVICE = "cuda"
    else:
        CLIP_DEVICE = "cpu"

    try:
        if open_clip is not None and torch is not None:
            model, _, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained="openai"
            )
            model.eval()
            model.to(CLIP_DEVICE)

            CLIP_MODEL = model
            CLIP_PREPROCESS = preprocess
            CLIP_BACKEND = "open_clip_vit_b_32"
            return CLIP_BACKEND
    except Exception:
        pass

    try:
        if openai_clip is not None and torch is not None:
            model, preprocess = openai_clip.load("ViT-B/32", device=CLIP_DEVICE)
            model.eval()

            CLIP_MODEL = model
            CLIP_PREPROCESS = preprocess
            CLIP_BACKEND = "openai_clip_vit_b_32"
            return CLIP_BACKEND
    except Exception:
        pass

    CLIP_BACKEND = "fallback_rgb_embedding"
    return CLIP_BACKEND


def current_embedding_backend_name() -> str:
    if EMBEDDING_BACKEND_MODE in {"fallback", "fallback_rgb_embedding", "rgb"}:
        return "fallback_rgb_embedding"
    return CLIP_BACKEND or "not_loaded"


def normalize_vector(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).flatten()
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def compute_fallback_embedding(img: Image.Image) -> List[float]:
    """
    Lightweight fallback embedding when CLIP is unavailable.
    Not semantically as strong as CLIP, but keeps the pipeline functional.
    """
    small = img.resize((32, 32))
    arr = np.asarray(small, dtype=np.float32) / 255.0
    vec = arr.flatten()
    vec = normalize_vector(vec)
    return vec.astype(np.float32).tolist()


def compute_clip_embedding(img: Image.Image) -> Tuple[List[float], str]:
    backend = load_clip_backend()

    if backend == "fallback_rgb_embedding":
        return compute_fallback_embedding(img), backend

    if torch is None or CLIP_MODEL is None or CLIP_PREPROCESS is None:
        return compute_fallback_embedding(img), "fallback_rgb_embedding"

    try:
        input_tensor = CLIP_PREPROCESS(img).unsqueeze(0).to(CLIP_DEVICE)
        with torch.no_grad():
            features = CLIP_MODEL.encode_image(input_tensor)
            features = features / features.norm(dim=-1, keepdim=True)
            vec = features[0].detach().cpu().numpy().astype(np.float32).tolist()
        return vec, backend
    except Exception:
        return compute_fallback_embedding(img), "fallback_rgb_embedding"


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2:
        return 0.0

    a = np.asarray(v1, dtype=np.float32)
    b = np.asarray(v2, dtype=np.float32)

    if a.shape != b.shape:
        return 0.0

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0

    sim = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0 else sim))


# -----------------------------
# Sprint 3 Scoring / Classification
# -----------------------------
PHASH_WEIGHT = 0.55
CLIP_WEIGHT = 0.45


def compute_hybrid_score(phash_sim: float, clip_sim: float) -> float:
    # Sprint 3 hybrid score: weighted blend of structural (pHash) and semantic (CLIP) similarity.
    score = (PHASH_WEIGHT * phash_sim) + (CLIP_WEIGHT * clip_sim)
    return round(float(score), 4)


def determine_verdict_and_trust(
    best_phash_sim: float,
    best_clip_sim: float,
    hybrid_score: float,
    has_registrations: bool
) -> Tuple[str, float]:
    if not has_registrations:
        return "not_registered", 0.10

    if best_phash_sim >= 0.98 and best_clip_sim >= 0.98:
        return "exact_match", 0.98

    if hybrid_score >= 0.88 or best_phash_sim >= 0.90:
        return "near_duplicate", max(0.88, hybrid_score)

    if best_clip_sim >= 0.85:
        return "semantically_similar", max(0.75, hybrid_score)

    return "different", max(0.20, hybrid_score)


def build_tags(verdict: str) -> List[str]:
    mapping = {
        "exact_match": ["exact_match", "verified"],
        "near_duplicate": ["near_duplicate", "structural_match"],
        "semantically_similar": ["semantically_similar", "semantic_match"],
        "different": ["different"],
        "not_registered": ["not_registered"],
    }
    return mapping.get(verdict, [verdict])


# -----------------------------
# SQLite helpers
# -----------------------------
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def ensure_column(con: sqlite3.Connection, table: str, column_name: str, column_def: str) -> None:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing_cols = [row["name"] for row in cur.fetchall()]
    if column_name not in existing_cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}")


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        content_sha256 TEXT PRIMARY KEY,
        phash TEXT NOT NULL,
        label TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_sha256 TEXT NOT NULL,
        phash TEXT NOT NULL,
        verdict TEXT NOT NULL,
        trust REAL NOT NULL,
        best_phash_sha TEXT,
        best_phash_sim REAL,
        created_at TEXT NOT NULL
    )
    """)

    # Sprint 2 schema upgrades
    ensure_column(con, "registrations", "clip_embedding", "TEXT")
    ensure_column(con, "registrations", "embedding_backend", "TEXT")

    ensure_column(con, "analyses", "clip_embedding", "TEXT")
    ensure_column(con, "analyses", "best_clip_sha", "TEXT")
    ensure_column(con, "analyses", "best_clip_sim", "REAL")
    ensure_column(con, "analyses", "hybrid_score", "REAL")
    ensure_column(con, "analyses", "embedding_backend", "TEXT")

    con.commit()
    con.close()


def load_from_db_into_memory():
    PHASH_STORE.clear()
    EMBEDDING_STORE.clear()

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT content_sha256, phash, clip_embedding
        FROM registrations
        ORDER BY created_at ASC
    """)

    for row in cur.fetchall():
        sha = row["content_sha256"]
        PHASH_STORE[sha] = row["phash"]

        emb = json_loads_vector(row["clip_embedding"])
        if emb:
            EMBEDDING_STORE[sha] = emb

    con.close()


@app.on_event("startup")
def on_startup():
    init_db()
    load_from_db_into_memory()


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {
        "name": "TrueSight API",
        "status": "running",
        "version": "Sprint 3",
        "embedding_backend": current_embedding_backend_name(),
        "routes": [
            "/health",
            "/docs",
            "/register",
            "/analyze",
            "/history/registrations",
            "/history/analyses",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "Sprint 3",
        "embedding_backend": current_embedding_backend_name(),
        "registrations": len(PHASH_STORE),
    }


@app.post("/register")
async def register_image(file: UploadFile = File(...), label: Optional[str] = None):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")

    content_sha = sha256_bytes(data)
    img = load_image_or_400(data)

    ph = compute_phash(img)
    embedding, backend = compute_clip_embedding(img)

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT content_sha256 FROM registrations WHERE content_sha256 = ?",
        (content_sha,)
    )
    exists = cur.fetchone() is not None

    if not exists:
        created_at = now_iso()
        cur.execute(
            """
            INSERT INTO registrations
            (content_sha256, phash, label, created_at, clip_embedding, embedding_backend)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                content_sha,
                ph,
                label,
                created_at,
                json_dumps_vector(embedding),
                backend,
            )
        )
        con.commit()
        PHASH_STORE[content_sha] = ph
        EMBEDDING_STORE[content_sha] = embedding

    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "label": label,
        "embedding_backend": backend,
        "embedding_dimensions": len(embedding),
        "status": "registered" if not exists else "already_registered",
        "note": "Sprint 3 registration stored with pHash fingerprint and CLIP embedding.",
    }


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")

    content_sha = sha256_bytes(data)
    img = load_image_or_400(data)

    ph = compute_phash(img)
    embedding, backend = compute_clip_embedding(img)

    best_phash_sha = None
    best_phash_sim = 0.0

    best_clip_sha = None
    best_clip_sim = 0.0

    best_hybrid_sha = None
    best_hybrid_score = 0.0

    for sha in PHASH_STORE.keys():
        saved_phash = PHASH_STORE.get(sha)
        saved_embedding = EMBEDDING_STORE.get(sha, [])

        p_sim = phash_similarity(ph, saved_phash)
        c_sim = cosine_similarity(embedding, saved_embedding)
        h_sim = compute_hybrid_score(p_sim, c_sim)

        if p_sim > best_phash_sim:
            best_phash_sim = p_sim
            best_phash_sha = sha

        if c_sim > best_clip_sim:
            best_clip_sim = c_sim
            best_clip_sha = sha

        if h_sim > best_hybrid_score:
            best_hybrid_score = h_sim
            best_hybrid_sha = sha

    verdict, trust = determine_verdict_and_trust(
        best_phash_sim=best_phash_sim,
        best_clip_sim=best_clip_sim,
        hybrid_score=best_hybrid_score,
        has_registrations=len(PHASH_STORE) > 0
    )

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO analyses
        (
            content_sha256,
            phash,
            clip_embedding,
            verdict,
            trust,
            best_phash_sha,
            best_phash_sim,
            best_clip_sha,
            best_clip_sim,
            hybrid_score,
            embedding_backend,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_sha,
            ph,
            json_dumps_vector(embedding),
            verdict,
            float(trust),
            best_phash_sha,
            float(best_phash_sim),
            best_clip_sha,
            float(best_clip_sim),
            float(best_hybrid_score),
            backend,
            now_iso(),
        )
    )
    con.commit()
    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "embedding_backend": backend,
        "best_match": {
            "content_sha256": best_hybrid_sha,
            "phash_match_sha256": best_phash_sha,
            "clip_match_sha256": best_clip_sha,
            "phash_similarity": float(round(best_phash_sim, 4)),
            "clip_similarity": float(round(best_clip_sim, 4)),
            "hybrid_score": float(round(best_hybrid_score, 4)),
        },
        "result": {
            "trust": float(round(trust, 4)),
            "verdict": verdict,
        },
        "tags": build_tags(verdict),
        "note": "Sprint 3 hybrid verification: 0.55 * pHash + 0.45 * CLIP similarity.",
    }


@app.get("/history/registrations")
def history_registrations(limit: int = 50):
    limit = max(1, min(int(limit), 200))

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT content_sha256, phash, label, embedding_backend, created_at
        FROM registrations
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    return {"items": rows}


@app.get("/history/analyses")
def history_analyses(limit: int = 50):
    limit = max(1, min(int(limit), 200))

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT
            id,
            content_sha256,
            phash,
            verdict,
            trust,
            best_phash_sha,
            best_phash_sim,
            best_clip_sha,
            best_clip_sim,
            hybrid_score,
            embedding_backend,
            created_at
        FROM analyses
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    return {"items": rows}
