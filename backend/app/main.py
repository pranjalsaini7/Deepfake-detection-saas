"""
Deepfake Detection API — FastAPI application.

Endpoints:
    POST /detect — accepts an image file, returns deepfake classification.
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io

from app.model import classify_image
from app.supabase_client import get_user_from_token, insert_scan

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="Deepfake Detection API",
    description="Upload a face image to detect whether it is real or AI-generated.",
    version="0.2.0",
)

# ── CORS (allow Next.js dev server) ─────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Allowed image MIME types ─────────────────────────────────────────
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


@app.post("/detect")
async def detect_deepfake(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """
    Accept an image via multipart/form-data, run deepfake classification,
    verify the user's Supabase auth token, insert a scan record,
    and return the top result as {label, confidence}.
    """
    # ── Verify auth token ────────────────────────────────────────────
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    # ── Validate file type ───────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Accepted types: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # ── Read and open the image ──────────────────────────────────────
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not open the uploaded file as an image. "
                   "The file may be corrupted or not a valid image.",
        )

    # ── Run inference ────────────────────────────────────────────────
    try:
        results = classify_image(image)
        top = results[0]

        label = top["label"]
        confidence = round(top["score"], 6)

        # ── Insert scan record ───────────────────────────────────────
        await insert_scan(
            user_id=user["id"],
            filename=file.filename or "unknown",
            label=label,
            confidence=confidence,
        )

        return {
            "label": label,
            "confidence": confidence,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {str(e)}",
        )
