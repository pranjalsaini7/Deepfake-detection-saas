# Deepfake Detection SaaS

AI-powered deepfake detection platform with Grad-CAM explainability, video analysis, and a developer API — built with Next.js, FastAPI, Supabase, and a custom-trained EfficientNet-B4 model achieving **99.97% test accuracy**.

---

## Architecture

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

### Components

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Next.js 16 (React 19) | Auth UI, image/video upload, result display with heatmaps |
| **Backend** | FastAPI + Uvicorn | Detection API, Grad-CAM heatmap generation, API key management |
| **Database** | Supabase (PostgreSQL) | User auth, scan history, API key storage (SHA-256 hashed), usage tracking |
| **ML Model** | EfficientNet-B4 (timm) | Binary classifier (Real vs Fake), fine-tuned on 140k faces |
| **Explainability** | Grad-CAM + MediaPipe FaceMesh | Heatmap overlays restricted to facial regions |

### Detection Pipeline

1. Face detection via MediaPipe FaceDetection
2. 5-region multi-crop (full + upper/lower/left/right)
3. 8-variant Test-Time Augmentation (TTA) per crop
4. Weighted ensemble with temperature-scaled calibration
5. Grad-CAM heatmap generation (FaceMesh-masked to facial landmarks)

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (free tier works)
- CUDA GPU (optional, falls back to CPU)

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials:
#   SUPABASE_URL=https://your-project.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with your Supabase credentials:
#   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
#   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Run the dev server
npm run dev
```

### 3. Database Tables

Run these SQL commands in your Supabase SQL Editor:

```sql
-- Scan history
CREATE TABLE IF NOT EXISTS scans (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id),
  filename TEXT NOT NULL,
  label TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API keys (SHA-256 hashed)
CREATE TABLE IF NOT EXISTS api_keys (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id),
  key_hash TEXT NOT NULL UNIQUE,
  key_prefix TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE
);

-- Usage tracking (rate limiting)
CREATE TABLE IF NOT EXISTS usage (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id),
  daily_scan_count INTEGER DEFAULT 0,
  last_reset_date DATE DEFAULT CURRENT_DATE
);
```

---

## API Endpoints

### Authenticated (Supabase JWT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/detect` | Image detection with Grad-CAM heatmap |
| POST | `/detect-video` | Video detection (12-frame sampling) |
| POST | `/api-keys/generate` | Generate a new API key |
| GET | `/api-keys` | List your API keys |
| POST | `/api-keys/revoke` | Revoke an API key |

### Developer API (API Key)

| Method | Endpoint | Auth Header | Description |
|--------|----------|-------------|-------------|
| POST | `/api/detect` | `X-API-Key: sk_...` | Image detection via API key |

#### Usage Example

```bash
# Generate an API key from the dashboard, then:
curl -X POST http://localhost:8000/api/detect \
  -H "X-API-Key: sk_your_key_here" \
  -F "file=@photo.jpg"
```

#### Response

```json
{
  "label": "Fake",
  "confidence": 99.84,
  "low_agreement": false,
  "warning": null,
  "heatmap": "base64-encoded-png..."
}
```

---

## Rate Limits

| Tier | Limit | Scope |
|------|-------|-------|
| Free | 5 scans/day | Shared across UI and API |

The rate limit counter is shared between `/detect`, `/detect-video`, and `/api/detect` — all use the same user account counter. The count resets at midnight (server time).

When the limit is hit, all endpoints return:
```json
{
  "detail": "Daily scan limit reached (5/day). Upgrade your plan or try again tomorrow."
}
```
HTTP Status: `429 Too Many Requests`

---

## Deployment (Docker)

The backend includes a Dockerfile suitable for Render, Hugging Face Spaces, or any container platform:

```bash
cd backend

# Build
docker build -t deepfake-api .

# Run
docker run -p 8000:8000 \
  -e SUPABASE_URL=https://your-project.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=your-service-role-key \
  deepfake-api
```

> **Note**: The model checkpoint (`models/efficientnet_b4_deepfake.pth`) must be included in the Docker image. It's approximately 75MB.

---

## Model Performance

| Metric | Value |
|--------|-------|
| Architecture | EfficientNet-B4 |
| Dataset | 140K Real and Fake Faces (FFHQ + StyleGAN) |
| Test Accuracy | **99.97%** |
| Test Loss | 0.0010 |
| Inference | TTA (8 variants) + 5-region multi-crop |

---

## License

This project is for educational and research purposes.
