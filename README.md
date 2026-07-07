# Deepfake Detection SaaS

AI-powered deepfake detection platform featuring Grad-CAM explainability, face-crop ensembling, and a developer API. Built with Next.js, FastAPI, Supabase, and a custom fine-tuned EfficientNet-B4.

---

## System Architecture

```
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│   Next.js 16     │────▶│   FastAPI (Python)    │────▶│   Supabase   │
│   Frontend       │     │   Backend             │     │   (Postgres  │
│   localhost:3000  │     │   localhost:8000      │     │    + Auth)   │
└──────────────────┘     └──────────┬───────────┘     └──────────────┘
                                    │
                          ┌─────────▼──────────┐
                          │  EfficientNet-B4   │
                          │  + Grad-CAM        │
                          │  + FaceMesh        │
                          └────────────────────┘
```

---

## Core Features

- **Multi-Crop Inference**: Combines full face crops with 4 sub-regions and 8-variant Test-Time Augmentation (TTA).
- **Explainability**: Face-masked Grad-CAM heatmaps overlayed on facial landmarks (using MediaPipe FaceMesh).
- **Developer API**: Key generation and revocation with SHA-256 hashed storage.
- **Rate Limiting**: Daily limit of 5 scans per user, shared globally across Web UI and Developer API.

---

## Setup & Run

### 1. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt
# Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
uvicorn app.main:app --reload
```

### 2. Frontend
```bash
cd frontend
npm install
# Configure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local
npm run dev
```

### 3. Database
Run the SQL migration scripts in `backend/scripts/` to create the required tables (`scans`, `api_keys`, `usage`).

---

## API Endpoints

| Method | Endpoint | Auth Header | Description |
| :--- | :--- | :--- | :--- |
| **POST** | `/detect` | `Authorization: Bearer <JWT>` | Image detection with Grad-CAM heatmap |
| **POST** | `/detect-video` | `Authorization: Bearer <JWT>` | Video detection (12-frame sampling) |
| **POST** | `/api/detect` | `X-API-Key: sk_...` | Developer API image detection |
| **POST** | `/api-keys/generate` | `Authorization: Bearer <JWT>` | Generate a new developer API key |

---

## Model Performance & Generalization

### Evaluation Results

| Dataset | Accuracy | AUC-ROC | Notes |
| :--- | :---: | :---: | :--- |
| **In-distribution** | **99.97%** | **0.9998** | StyleGAN fakes vs. Flickr (FFHQ) reals |
| **Celeb-DF v2 (OOD)** | **51.00%** | **0.6352** | Face-swap manipulation, unseen generator |

### Generalization & Out-of-Distribution (OOD) Analysis

> [!WARNING]
> **Generalization Caveat**: The model was trained exclusively on GAN-generated fakes (StyleGAN) and generalizes poorly to face-swap manipulation methods (Celeb-DF v2).

This behavior is well-documented in deepfake detection literature: models trained on specific generative methods (e.g., GAN attribution) struggle to detect structural or blend boundaries typical of identity-swapping methods. Cross-manipulation generalization requires training on diverse datasets.

- **Future Work**: Fine-tune the classifier on datasets like **FaceForensics++** (incorporating FaceSwap, Deepfakes, Face2Face, and NeuralTextures) to construct a more robust, generalizable detector.

---

## Deployment (Docker)
```bash
cd backend
docker build -t deepfake-api .
docker run -p 8000:8000 -e SUPABASE_URL=... -e SUPABASE_SERVICE_ROLE_KEY=... deepfake-api
```
