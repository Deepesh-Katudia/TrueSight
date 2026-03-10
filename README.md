# TrueSight - Sprint 1 MVP

TrueSight is an image verification application designed to help users check whether an uploaded image matches a previously registered image.  
This Sprint 1 MVP focuses on **pHash-based image verification**, **basic trust results**, **tags**, **history tracking**, and **SQLite storage**.

## Sprint 1 Scope

The Sprint 1 version includes the core usable workflow of the application:

- Upload an image
- Register an image for future reference
- Analyze an image using **perceptual hashing (pHash)**
- View a **basic trust result**
- View **verification tags**
- View **SHA-256** and **pHash identifiers**
- Access **registration and analysis history**
- Store data in **SQLite**

This version does **not** include CLIP-based similarity, provenance ledger scoring, or advanced forensic export features.

---

## Tech Stack

### Frontend
- React
- Vite
- JavaScript

### Backend
- FastAPI
- Python

### Database
- SQLite

### Image Processing
- Pillow
- NumPy
- Perceptual Hashing (pHash)

---

## Project Structure

```bash
truesight-main/
│
├── backend/
│   ├── storage/
│   ├── app.py
│   ├── ledger.py
│   ├── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
└── README.md
````

---

## Features

### 1. Image Registration

Users can upload an image and register it in the system.
The backend stores:

* Content SHA-256
* pHash
* Optional label
* Timestamp

### 2. Image Analysis

Users can upload an image for analysis.
The system:

* Generates pHash for the uploaded image
* Compares it with registered images
* Finds the best pHash match
* Returns a trust score and verdict

### 3. Tags / Verdicts

The Sprint 1 system returns one of the following result tags:

* `likely_real`
* `uncertain`
* `likely_ai_or_manipulated`
* `not_registered`

### 4. History Tracking

The application stores:

* Registration history
* Analysis history

### 5. SQLite Storage

All registration and analysis records are stored in a local SQLite database.

---

## API Endpoints

### `GET /health`

Checks whether the backend is running.

### `POST /register`

Registers an uploaded image and stores its SHA-256 and pHash.

### `POST /analyze`

Analyzes an uploaded image using pHash-based verification.

### `GET /history/registrations`

Returns registration history.

### `GET /history/analyses`

Returns analysis history.

---

## How to Run the Project

## Backend Setup

Go to the backend folder:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```bash
.\venv\Scripts\Activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend server:

```bash
python -m uvicorn app:app --reload
```

Backend runs at:

```bash
http://localhost:8000
```

OpenAPI docs:

```bash
http://localhost:8000/docs
```

---

## Frontend Setup

Open a new terminal and go to the frontend folder:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Run the frontend:

```bash
npm run dev
```

Frontend runs at:

```bash
http://localhost:5173
```

---

## Important Note

If you previously ran a different version of the backend with a different database schema, delete the old database before starting Sprint 1:

```bash
backend/storage/truesight.db
```

Then restart the backend so the new Sprint 1 tables are created.

---

## Sprint 1 Workflow

The basic application workflow is:

```text
Upload Image -> Register or Analyze -> Generate pHash -> Compare Against Registered Images -> Return Trust Result -> Store History
```

---

## Example Sprint 1 Usage

### Register an Image

1. Upload an image
2. Click **Register**
3. The image is stored with its SHA-256 and pHash

### Analyze an Image

1. Upload an image
2. Click **Analyze**
3. The system compares its pHash with registered images
4. The result shows:

   * pHash similarity
   * trust score
   * verdict/tag
   * identifiers
   * best pHash match

---

## Sprint 1 Limitations

This MVP is intentionally limited to Sprint 1 functionality. It does not yet include:

* CLIP-based similarity matching
* Provenance ledger verification
* Merkle root validation
* Advanced trust score explanation
* CSV export features
* Full forensic reporting

These features are planned for later sprints.

---

## Team Goal for Sprint 1

The goal of Sprint 1 was to deliver a **working MVP** that demonstrates the core concept of TrueSight:

* registering images,
* verifying uploaded images using pHash,
* showing a basic trust result,
* and storing analysis history.

---

## Future Work

Planned improvements for upcoming sprints include:

* CLIP-based neural similarity matching
* Improved trust scoring logic
* Better UI for verification results
* Provenance and audit trail features
* Expanded backend testing
* Final deployment and polish

---

## Authors

TrueSight Capstone Team
CS 691 Computer Science Capstone Project
