"""
Deepfake Detection API — FastAPI application.

Endpoints:
    POST /detect — accepts an image file, returns deepfake classification
                   with a base64-encoded attention heatmap overlay.
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

from app.model import classify_with_attention
from app.face_detection import detect_and_crop_face
from app.explainability import generate_heatmap_overlay
from app.supabase_client import get_user_from_token, insert_scan

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="Deepfake Detection API",
    description="Upload a face image to detect whether it is real or AI-generated.",
    version="0.3.0",
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
    Accept an image via multipart/form-data, detect the face, run deepfake
    classification with attention extraction, generate an attention heatmap
    overlay, verify the user, insert a scan record, and return:
        {label, confidence, heatmap}
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

    # ── Detect and crop face ─────────────────────────────────────────
    try:
        face_image, bbox = detect_and_crop_face(image)
        print(f"[DETECT] Face bbox: {bbox}")
    except Exception as e:
        print(f"[DETECT] Face detection failed, using full image: {e}")
        face_image = image
        bbox = {"x": 0, "y": 0, "w": image.width, "h": image.height}

    # ── Run inference with attention ─────────────────────────────────
    try:
        results, attentions = classify_with_attention(face_image)
        top = results[0]

        label = top["label"]
        confidence = round(top["score"], 6)

        # ── Generate heatmap overlay ─────────────────────────────────
        heatmap_b64 = generate_heatmap_overlay(face_image, attentions)

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
            "heatmap": heatmap_b64,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {str(e)}",
        )
