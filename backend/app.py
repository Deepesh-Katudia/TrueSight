import io
import os
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Dict

import numpy as np
from PIL import Image, UnidentifiedImageError

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------
# App + CORS
# -----------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
# In-memory store
# -----------------------------
PHASH_STORE: Dict[str, str] = {}  # sha256 -> phash hex


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


def determine_verdict_and_trust(best_similarity: float, has_registrations: bool) -> tuple[str, float]:
    if not has_registrations or best_similarity <= 0.0:
        return "not_registered", 0.10

    if best_similarity >= 0.90:
        return "likely_real", 0.90
    if best_similarity >= 0.75:
        return "uncertain", 0.60
    return "likely_ai_or_manipulated", 0.30


# -----------------------------
# SQLite helpers
# -----------------------------
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


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

    con.commit()
    con.close()


def load_from_db_into_memory():
    PHASH_STORE.clear()

    con = db()
    cur = con.cursor()

    cur.execute("SELECT content_sha256, phash FROM registrations ORDER BY created_at ASC")
    for row in cur.fetchall():
        PHASH_STORE[row["content_sha256"]] = row["phash"]

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
        "version": "Sprint 1",
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
        "version": "Sprint 1",
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
            "INSERT INTO registrations (content_sha256, phash, label, created_at) VALUES (?,?,?,?)",
            (content_sha, ph, label, created_at)
        )
        con.commit()
        PHASH_STORE[content_sha] = ph

    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "label": label,
        "status": "registered" if not exists else "already_registered",
        "note": "Image registration stored successfully for Sprint 1.",
    }


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")

    content_sha = sha256_bytes(data)
    img = load_image_or_400(data)
    ph = compute_phash(img)

    best_phash_sha = None
    best_phash_sim = 0.0

    for sha, saved_phash in PHASH_STORE.items():
        sim = phash_similarity(ph, saved_phash)
        if sim > best_phash_sim:
            best_phash_sim = sim
            best_phash_sha = sha

    verdict, trust = determine_verdict_and_trust(best_phash_sim, len(PHASH_STORE) > 0)

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO analyses
        (content_sha256, phash, verdict, trust, best_phash_sha, best_phash_sim, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_sha,
            ph,
            verdict,
            float(trust),
            best_phash_sha,
            float(best_phash_sim),
            now_iso(),
        )
    )
    con.commit()
    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "best_match": {
            "content_sha256": best_phash_sha,
            "phash_similarity": float(best_phash_sim),
        },
        "result": {
            "trust": float(trust),
            "verdict": verdict,
        },
        "tags": [verdict],
        "note": "Sprint 1 analysis uses pHash-based verification only.",
    }


@app.get("/history/registrations")
def history_registrations(limit: int = 50):
    limit = max(1, min(int(limit), 200))

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT content_sha256, phash, label, created_at
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
        SELECT id, content_sha256, phash, verdict, trust,
               best_phash_sha, best_phash_sim, created_at
        FROM analyses
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    return {"items": rows}