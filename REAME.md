# TrueSight  
**AI-Powered Media Authenticity & Provenance System**

TrueSight is a forensic AI system that verifies whether an image is **real, manipulated, or AI-generated** by combining:

- **Perceptual hashing (pHash)** – fast visual fingerprinting  
- **Neural embeddings (CLIP ViT-B-32)** – deep semantic similarity  
- **Cryptographic provenance (Merkle ledger)** – tamper-evident ownership  
- **SQLite audit history + CSV export** – forensic traceability  

This mirrors how modern platforms (Meta, Google, Adobe C2PA) detect deepfakes and prove content authenticity.

---

## 🚀 What TrueSight Does

TrueSight answers three critical questions:

| Question | How TrueSight Solves It |
|--------|------------------------|
| Is this image visually similar to known originals? | pHash + CLIP similarity |
| Has this exact content been registered before? | SHA-256 + ledger |
| Can I prove it cryptographically? | Merkle root provenance |

---

## 🧠 Trust Score Model

TrueSight combines three signals into a **Trust Score**:

Trust = 0.35 × pHashSimilarity
+ 0.45 × CLIPSimilarity
+ 0.20 × Provenance

This allows the system to:
- Detect near-duplicates
- Catch AI-generated variants
- Only verify content when cryptographic proof exists

---

## 🧩 Core Features

- **Image registration**
- **Deepfake / manipulation detection**
- **CLIP (ViT-B-32) neural perceptual hashing**
- **Merkle-root provenance ledger**
- **SQLite persistence**
- **History panel (analyses + registrations)**
- **One-click CSV export (recruiter-friendly forensic logs)**
- **Explainable AI trust breakdown**

---

## 🖥️ Tech Stack

**Backend**
- FastAPI  
- SQLite  
- OpenCLIP (ViT-B-32)  
- Pillow  
- NumPy  
- Merkle ledger  

**Frontend**
- React (Vite)  
- Modern glassmorphism UI  
- Interactive similarity bars  
- CSV export buttons  

---

## ⚙️ How to Run

### 1️⃣ Backend
```bash
cd backend
source .venv/bin/activate
python3 -m uvicorn app:app --reload --port 8000
Backend will be available at:
http://localhost:8000
http://localhost:8000/docs


2️⃣ Frontend
cd frontend
npm run dev
Open:
http://localhost:5173
🧪 How to Test
Register an image
Upload an original image → Click Register
This:

Stores its SHA-256 + pHash + embedding
Adds it to the Merkle ledger
Persists it in SQLite
Analyze an image
Upload any image → Click Analyze
TrueSight returns:

pHash similarity
CLIP similarity
Provenance status
Trust score
Verdict (Real / Uncertain / Likely AI)
🗃️ Forensic History
Click History in the UI to view:
All registrations
All analyses
Trust scores
Provenance results
This data is stored in SQLite and survives restarts.


📥 CSV Export

You can export the forensic logs for auditing, research, or recruiters:
Export	URL
Analyses	http://localhost:8000/export/analyses.csv
Registrations	http://localhost:8000/export/registrations.csv
Full forensic log	http://localhost:8000/export/forensic_log.csv
These CSVs can be opened in Excel, Google Sheets, or used for model evaluation.



🏆 Why This Matters
TrueSight is not just a deepfake detector.
It is a media authentication infrastructure combining:

Computer vision
Neural embeddings
Cryptography
Forensic logging
This is the same category of technology used by:
Meta (deepfake defense)
Google (content authenticity)
Adobe (C2PA)