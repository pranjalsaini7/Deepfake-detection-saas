"""
Deepfake Detection API — FastAPI application.

Endpoints:
    POST /detect — accepts an image file, returns deepfake classification
                   with Grad-CAM heatmap overlay, TTA + multi-crop scoring.
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

from app.model import classify_image, get_model, get_device
from app.face_detection import detect_and_crop_face
from app.explainability import generate_heatmap_overlay
from app.supabase_client import get_user_from_token, insert_scan

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="Deepfake Detection API",
    description="Upload a face image to detect whether it is real or AI-generated.",
    version="0.4.0",
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
    Accept an image, detect face, run EfficientNet-B4 with TTA + multi-crop,
    generate Grad-CAM heatmap, return:
        {label, confidence, low_agreement, warning, heatmap}
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
    warning = None
    try:
        face_image, bbox = detect_and_crop_face(image)
        print(f"[DETECT] Face bbox: {bbox}")
    except Exception as e:
        print(f"[DETECT] Face detection failed, using full image: {e}")
        face_image = image
        bbox = {"x": 0, "y": 0, "w": image.width, "h": image.height}
        warning = "No face detected — heatmap may be inaccurate"

    # ── Run inference (TTA + multi-crop) ─────────────────────────────
    try:
        result = classify_image(face_image)
        label = result["label"]
        confidence = result["confidence"]
        low_agreement = result["low_agreement"]

        # Override warning if face wasn't detected
        if warning:
            result["warning"] = warning

        # ── Generate Grad-CAM heatmap ────────────────────────────────
        heatmap_b64 = generate_heatmap_overlay(
            face_image=face_image,
            original_image=image,
            bbox=bbox,
            model=get_model(),
            device=get_device(),
        )

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
            "low_agreement": low_agreement,
            "warning": result.get("warning"),
            "heatmap": heatmap_b64,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {str(e)}",
        )
