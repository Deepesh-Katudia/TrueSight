import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
LEDGER_PATH = os.path.join(STORAGE_DIR, "ledger.jsonl")
MERKLE_ROOT_PATH = os.path.join(STORAGE_DIR, "merkle_root.txt")

os.makedirs(STORAGE_DIR, exist_ok=True)

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _hash_entry(entry: Dict[str, Any]) -> str:
    payload = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_hex(payload)

def _compute_merkle_root(hashes: List[str]) -> str:
    if not hashes:
        return ""
    level = hashes[:]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(_sha256_hex((left + right).encode("utf-8")))
        level = nxt
    return level[0]

def append_to_ledger(record: Dict[str, Any]) -> Dict[str, Any]:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    entry_hash = _hash_entry(entry)

    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    hashes = []
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                hashes.append(_hash_entry(json.loads(line)))

    merkle_root = _compute_merkle_root(hashes)
    with open(MERKLE_ROOT_PATH, "w", encoding="utf-8") as f:
        f.write(merkle_root)

    return {"entry": entry, "entry_hash": entry_hash, "merkle_root": merkle_root, "index": len(hashes) - 1}

def get_merkle_root() -> str:
    if not os.path.exists(MERKLE_ROOT_PATH):
        return ""
    with open(MERKLE_ROOT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()

def verify_entry(entry_hash: str) -> Dict[str, Any]:
    if not os.path.exists(LEDGER_PATH):
        return {"found": False, "merkle_root": get_merkle_root()}

    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            h = _hash_entry(entry)
            if h == entry_hash:
                return {"found": True, "index": idx, "entry": entry, "merkle_root": get_merkle_root()}

    return {"found": False, "merkle_root": get_merkle_root()}
