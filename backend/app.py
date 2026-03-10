import io
import os
import json
import time
import base64
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

import numpy as np
from PIL import Image, UnidentifiedImageError

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import torch
import open_clip

import csv
from starlette.responses import StreamingResponse


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
# In-memory indexes
# -----------------------------
PHASH_STORE: Dict[str, str] = {}         # sha256 -> phash hex
EMB_STORE: Dict[str, np.ndarray] = {}    # sha256 -> embedding float32 vector

LEDGER: List[Dict[str, Any]] = []        # list of {index, entry_hash, leaf_hash, merkle_root, content_sha256, created_at}
MERKLE_ROOT: str = ""


# -----------------------------
# Utilities
# -----------------------------
def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_image_or_400(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img.convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Invalid/unsupported image. Try PNG or JPG (HEIC may fail)."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read image: {e}")


# -----------------------------
# Perceptual Hash (simple DCT-like pHash)
# -----------------------------
def compute_phash(img: Image.Image, size: int = 32, smaller: int = 8) -> str:
    # Lightweight pHash: grayscale -> resize -> DCT-ish via FFT lowfreq magnitude
    x = img.convert("L").resize((size, size))
    arr = np.asarray(x, dtype=np.float32)
    freq = np.fft.fft2(arr)
    mag = np.abs(freq)[:smaller, :smaller]
    med = np.median(mag[1:, 1:])  # ignore DC
    bits = (mag > med).astype(np.uint8).flatten()
    # pack bits into hex
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
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
# CLIP embedding
# -----------------------------
_DEVICE = "cpu"
_CLIP_MODEL = None
_CLIP_PREPROCESS = None

def get_clip():
    global _CLIP_MODEL, _CLIP_PREPROCESS
    if _CLIP_MODEL is None:
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32",
            pretrained="laion2b_s34b_b79k"
        )
        model.eval()
        model.to(_DEVICE)
        _CLIP_MODEL = model
        _CLIP_PREPROCESS = preprocess
    return _CLIP_MODEL, _CLIP_PREPROCESS

def clip_embedding(img: Image.Image) -> np.ndarray:
    model, preprocess = get_clip()
    with torch.no_grad():
        t = preprocess(img).unsqueeze(0).to(_DEVICE)
        feat = model.encode_image(t)
        feat = feat / feat.norm(dim=-1, keepdim=True)
        vec = feat.squeeze(0).cpu().numpy().astype(np.float32)
        return vec

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)


# -----------------------------
# Merkle Ledger
# -----------------------------
def merkle_root_from_leaves(leaf_hashes: List[str]) -> str:
    if not leaf_hashes:
        return ""
    level = [bytes.fromhex(h) for h in leaf_hashes]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256(left + right).digest())
        level = nxt
    return level[0].hex()

def ledger_add_entry(content_sha: str) -> Dict[str, Any]:
    global MERKLE_ROOT

    index = len(LEDGER)
    created_at = now_iso()

    # leaf hash includes index + content sha so ordering matters
    leaf_payload = f"{index}:{content_sha}"
    leaf_hash = sha256_hex(leaf_payload)

    # entry hash acts like an inclusion pointer
    entry_payload = json.dumps(
        {"index": index, "content_sha256": content_sha, "leaf_hash": leaf_hash, "ts": created_at},
        sort_keys=True
    )
    entry_hash = sha256_hex(entry_payload)

    # compute merkle root with new leaf
    leaves = [e["leaf_hash"] for e in LEDGER] + [leaf_hash]
    MERKLE_ROOT = merkle_root_from_leaves(leaves)

    entry = {
        "index": index,
        "content_sha256": content_sha,
        "leaf_hash": leaf_hash,
        "entry_hash": entry_hash,
        "merkle_root": MERKLE_ROOT,
        "created_at": created_at,
    }
    LEDGER.append(entry)
    return entry


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
        emb BLOB NOT NULL,
        emb_dim INTEGER NOT NULL,
        label TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ledger (
        idx INTEGER PRIMARY KEY,
        content_sha256 TEXT NOT NULL,
        leaf_hash TEXT NOT NULL,
        entry_hash TEXT NOT NULL,
        merkle_root TEXT NOT NULL,
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
        provenance_exact INTEGER NOT NULL,
        best_phash_sha TEXT,
        best_phash_sim REAL,
        best_clip_sha TEXT,
        best_clip_sim REAL,
        merkle_root TEXT,
        created_at TEXT NOT NULL
    )
    """)

    con.commit()
    con.close()

def emb_to_blob(vec: np.ndarray) -> bytes:
    # float32 -> bytes
    return vec.astype(np.float32).tobytes()

def blob_to_emb(blob: bytes, dim: int) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float32)
    if dim > 0 and arr.size != dim:
        # safety: allow partial but reshape is not needed for 1D
        return arr[:dim].astype(np.float32)
    return arr.astype(np.float32)

def load_from_db_into_memory():
    """On startup: rebuild in-memory stores + ledger root."""
    global MERKLE_ROOT
    PHASH_STORE.clear()
    EMB_STORE.clear()
    LEDGER.clear()
    MERKLE_ROOT = ""

    con = db()
    cur = con.cursor()

    # registrations
    cur.execute("SELECT content_sha256, phash, emb, emb_dim FROM registrations ORDER BY created_at ASC")
    for row in cur.fetchall():
        sha = row["content_sha256"]
        PHASH_STORE[sha] = row["phash"]
        EMB_STORE[sha] = blob_to_emb(row["emb"], row["emb_dim"])

    # ledger
    cur.execute("SELECT idx, content_sha256, leaf_hash, entry_hash, merkle_root, created_at FROM ledger ORDER BY idx ASC")
    rows = cur.fetchall()
    for r in rows:
        LEDGER.append({
            "index": int(r["idx"]),
            "content_sha256": r["content_sha256"],
            "leaf_hash": r["leaf_hash"],
            "entry_hash": r["entry_hash"],
            "merkle_root": r["merkle_root"],
            "created_at": r["created_at"],
        })

    # recompute merkle root (source of truth)
    leaves = [e["leaf_hash"] for e in LEDGER]
    MERKLE_ROOT = merkle_root_from_leaves(leaves)

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
        "merkle_root": MERKLE_ROOT,
        "routes": ["/health", "/docs", "/register", "/analyze", "/verify/{entry_hash}", "/history/registrations", "/history/analyses"]
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "merkle_root": MERKLE_ROOT,
        "registrations": len(PHASH_STORE),
        "ledger_entries": len(LEDGER),
    }

@app.post("/register")
async def register_image(file: UploadFile = File(...), label: Optional[str] = None):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")

    content_sha = sha256_bytes(data)

    img = load_image_or_400(data)
    ph = compute_phash(img)
    emb = clip_embedding(img)

    # ledger entry (only if not already registered)
    con = db()
    cur = con.cursor()

    cur.execute("SELECT content_sha256 FROM registrations WHERE content_sha256 = ?", (content_sha,))
    exists = cur.fetchone() is not None

    if not exists:
        created_at = now_iso()
        cur.execute(
            "INSERT INTO registrations (content_sha256, phash, emb, emb_dim, label, created_at) VALUES (?,?,?,?,?,?)",
            (content_sha, ph, emb_to_blob(emb), int(emb.size), label, created_at)
        )

        entry = ledger_add_entry(content_sha)

        cur.execute(
            "INSERT INTO ledger (idx, content_sha256, leaf_hash, entry_hash, merkle_root, created_at) VALUES (?,?,?,?,?,?)",
            (entry["index"], entry["content_sha256"], entry["leaf_hash"], entry["entry_hash"], entry["merkle_root"], entry["created_at"])
        )

        con.commit()

        # update in-memory stores
        PHASH_STORE[content_sha] = ph
        EMB_STORE[content_sha] = emb

    else:
        # if already registered, return latest merkle root / existing ledger entry if available
        entry = LEDGER[-1] if LEDGER else {"index": 0, "entry_hash": "", "merkle_root": MERKLE_ROOT}

    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "label": label,
        "ledger": {
            "entry_hash": entry.get("entry_hash", ""),
            "merkle_root": MERKLE_ROOT,
            "index": entry.get("index", 0)
        },
        "note": "Registered + persisted in SQLite. Ledger updated only for new content.",
    }

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")

    content_sha = sha256_bytes(data)

    img = load_image_or_400(data)
    ph = compute_phash(img)
    emb = clip_embedding(img)

    # Find best matches
    best_ph = {"sha": None, "similarity": 0.0}
    best_emb = {"sha": None, "similarity": 0.0}

    for sha, ph2 in PHASH_STORE.items():
        sim = phash_similarity(ph, ph2)
        if sim > best_ph["similarity"]:
            best_ph = {"sha": sha, "similarity": sim}

    for sha, e2 in EMB_STORE.items():
        sim = cosine_similarity(emb, e2)
        if sim > best_emb["similarity"]:
            best_emb = {"sha": sha, "similarity": sim}

    exact_registered = (content_sha in PHASH_STORE)

    # score (simple weighted)
    w_ph = 0.35
    w_emb = 0.45
    w_prov = 0.20
    trust = (w_ph * best_ph["similarity"]) + (w_emb * best_emb["similarity"]) + (w_prov * (1.0 if exact_registered else 0.0))

    if trust >= 0.70:
        verdict = "likely_real"
    elif trust >= 0.45:
        verdict = "uncertain"
    else:
        verdict = "likely_ai_or_manipulated"

    # Persist analysis record
    con = db()
    cur = con.cursor()

    cur.execute(
        """INSERT INTO analyses
           (content_sha256, phash, verdict, trust, provenance_exact,
            best_phash_sha, best_phash_sim, best_clip_sha, best_clip_sim, merkle_root, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            content_sha, ph, verdict, float(trust), 1 if exact_registered else 0,
            best_ph["sha"], float(best_ph["similarity"]),
            best_emb["sha"], float(best_emb["similarity"]),
            MERKLE_ROOT,
            now_iso()
        )
    )
    con.commit()
    con.close()

    return {
        "content_sha256": content_sha,
        "phash": ph,
        "matches": {
            "best_phash": best_ph,
            "best_embedding": best_emb
        },
        "provenance": {
            "exact_registered": exact_registered,
            "merkle_root": MERKLE_ROOT
        },
        "score": {
            "trust": float(trust),
            "verdict": verdict
        },
        "note": "Using CLIP embeddings (ViT-B-32) for neural perceptual matching. Persisting analyses in SQLite.",
    }

@app.get("/verify/{entry_hash}")
def verify_entry(entry_hash: str):
    for e in LEDGER:
        if e.get("entry_hash") == entry_hash:
            return {"found": True, "entry": e, "merkle_root": MERKLE_ROOT}
    return {"found": False, "merkle_root": MERKLE_ROOT}

@app.get("/history/registrations")
def history_registrations(limit: int = 50):
    limit = max(1, min(int(limit), 200))
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT content_sha256, phash, label, created_at FROM registrations ORDER BY created_at DESC LIMIT ?",
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
        """SELECT id, content_sha256, phash, verdict, trust, provenance_exact,
                  best_phash_sha, best_phash_sim, best_clip_sha, best_clip_sim,
                  merkle_root, created_at
           FROM analyses
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"items": rows}


def _csv_stream(rows: List[Dict[str, Any]], header: List[str], filename: str) -> StreamingResponse:
    def generate():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for r in rows:
            writer.writerow(r)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/export/analyses.csv")
def export_analyses_csv(limit: int = 1000):
    limit = max(1, min(int(limit), 5000))
    con = db()
    cur = con.cursor()
    cur.execute(
        """SELECT id, content_sha256, phash, verdict, trust, provenance_exact,
                  best_phash_sha, best_phash_sim, best_clip_sha, best_clip_sim,
                  merkle_root, created_at
           FROM analyses
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    header = [
        "id", "created_at", "content_sha256", "phash",
        "verdict", "trust", "provenance_exact",
        "best_phash_sha", "best_phash_sim",
        "best_clip_sha", "best_clip_sim",
        "merkle_root"
    ]
    return _csv_stream(rows, header, "truesight_analyses.csv")


@app.get("/export/registrations.csv")
def export_registrations_csv(limit: int = 1000):
    limit = max(1, min(int(limit), 5000))
    con = db()
    cur = con.cursor()
    cur.execute(
        """SELECT content_sha256, phash, label, created_at
           FROM registrations
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    header = ["created_at", "content_sha256", "phash", "label"]
    return _csv_stream(rows, header, "truesight_registrations.csv")


@app.get("/export/forensic_log.csv")
def export_forensic_log_csv(limit: int = 2000):
    """
    Combined timeline (registrations + analyses) as a single forensic log.
    """
    limit = max(1, min(int(limit), 8000))
    con = db()
    cur = con.cursor()

    cur.execute(
        """SELECT created_at, 'registration' as event_type,
                  content_sha256, phash, COALESCE(label,'') as label,
                  '' as verdict, '' as trust, '' as provenance_exact,
                  '' as best_phash_sha, '' as best_phash_sim,
                  '' as best_clip_sha, '' as best_clip_sim,
                  '' as merkle_root
           FROM registrations
           UNION ALL
           SELECT created_at, 'analysis' as event_type,
                  content_sha256, phash, '' as label,
                  verdict, CAST(trust as TEXT) as trust,
                  CAST(provenance_exact as TEXT) as provenance_exact,
                  COALESCE(best_phash_sha,'') as best_phash_sha,
                  COALESCE(CAST(best_phash_sim as TEXT),'') as best_phash_sim,
                  COALESCE(best_clip_sha,'') as best_clip_sha,
                  COALESCE(CAST(best_clip_sim as TEXT),'') as best_clip_sim,
                  COALESCE(merkle_root,'') as merkle_root
           FROM analyses
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,)
    )

    rows = [dict(r) for r in cur.fetchall()]
    con.close()

    header = [
        "created_at", "event_type",
        "content_sha256", "phash", "label",
        "verdict", "trust", "provenance_exact",
        "best_phash_sha", "best_phash_sim",
        "best_clip_sha", "best_clip_sim",
        "merkle_root"
    ]
    return _csv_stream(rows, header, "truesight_forensic_log.csv")
