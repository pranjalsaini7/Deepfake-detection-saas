# VERITAS — AI-Powered Deepfake Detection Platform

VERITAS is an enterprise-grade digital forensics platform featuring real-time deepfake detection, face-masked Grad-CAM explainability heatmaps, face-crop ensembling, and developer API access.

Built with **Next.js 16**, **FastAPI (Python 3.11)**, **PyTorch**, **MediaPipe**, **Supabase**, **Vercel**, and **Render**.

---

## 🌟 Key Highlights & Design

- **Landing Page**: Served at `/` via Next.js rewrites (`public/index-veritas.html`). Features off-white cinematic aesthetic, Lenis smooth scrolling, live **Indian Standard Time (IST)** clock, and dynamic warm-orange cursor-following ambient glow.
- **Explainability**: Face-masked Grad-CAM heatmaps overlayed on facial landmarks (using MediaPipe FaceMesh).
- **Multi-Crop Inference**: Combines full face crops with 4 sub-regions and 8-variant Test-Time Augmentation (TTA).
- **Developer API & Portal**: Supabase authentication (`/login`, `/signup`), protected dashboard (`/dashboard`), and SHA-256 hashed API key management.

---

## 🏗️ Architecture Overview

```
┌───────────────────────────┐     ┌───────────────────────────┐     ┌───────────────────────────┐
│     Next.js 16 (Vercel)   │────▶│   FastAPI Backend (Render)│────▶│   Supabase Postgres       │
│     localhost:3000        │     │   localhost:8000          │     │   (Auth & Database)       │
└───────────────────────────┘     └─────────────┬─────────────┘     └───────────────────────────┘
                                                │
                                      ┌─────────▼───────────┐
                                      │  EfficientNet-B4    │
                                      │  + Grad-CAM Overlay │
                                      │  + FaceMesh Crop    │
                                      └─────────────────────┘
```

---

## ⚡ Quick Start (Local Development)

### 1. Backend (FastAPI)
```bash
cd backend
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate     # On Windows
# Install dependencies
pip install -r requirements.txt
# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Frontend (Next.js)
```bash
cd frontend
# Install node packages
npm install
# Run development server
npm run dev
```

Visit **http://localhost:3000/** in your browser.

---

## 🚀 Deployment Guide

### Frontend Deployment (Vercel)
1. Push project to GitHub.
2. Import repository on [Vercel](https://vercel.com/new).
3. Set **Root Directory** to `frontend`.
4. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
5. Click **Deploy**.

### Backend Deployment (Render)
1. Import repository on [Render](https://render.com/).
2. Select **Web Service** using `render.yaml` or Docker runtime.
3. Set **Root Directory** to `backend`.
4. Add environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `FRONTEND_URL` (your Vercel app domain)
5. Click **Deploy**.

---

## 📊 Model Performance

| Dataset | Accuracy | AUC-ROC | Notes |
| :--- | :---: | :---: | :--- |
| 🎯 **In-Distribution** | **99.97%** | **0.9998** | Fine-tuned EfficientNet-B4 on GAN fakes vs. FFHQ reals |
| ⚠️ **Celeb-DF v2 (OOD)** | 51.00% | 0.6352 | Cross-manipulation generalization benchmark |

---

## 🔒 Security & License

- API Keys are SHA-256 hashed before database insertion.
- Auth protected routes (`/dashboard`) guarded via React AuthContext.
- MIT License.
