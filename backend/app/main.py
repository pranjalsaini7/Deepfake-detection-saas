"""
Deepfake Detection API — FastAPI application.

Endpoints:
    POST /detect         — image detection (Supabase auth)
    POST /detect-video   — video detection (Supabase auth)
    POST /api/detect     — image detection (API key auth)
    POST /api-keys/generate — generate a new API key
    GET  /api-keys       — list user's API keys
    POST /api-keys/revoke — revoke an API key
"""

import sys
import os
import tempfile

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
import cv2
import numpy as np

from app.model import classify_image, get_model, get_device
from app.face_detection import detect_and_crop_face
from app.explainability import generate_heatmap_overlay
from app.supabase_client import (
    get_user_from_token,
    insert_scan,
    create_api_key,
    verify_api_key,
    list_api_keys,
    revoke_api_key,
    check_and_increment_usage,
)

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="Deepfake Detection API",
    description="Upload a face image or video to detect whether it is real or AI-generated.",
    version="0.5.0",
)

# ── CORS (allow Next.js dev server) ─────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Allowed MIME types ───────────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
    "video/avi",
}

# Number of frames to sample from a video
VIDEO_SAMPLE_FRAMES = 12


# ═══════════════════════════════════════════════════════════════════
# Helper: run single-image detection (shared by /detect and /api/detect)
# ═══════════════════════════════════════════════════════════════════

def _detect_single_image(image: Image.Image):
    """
    Run face detection + EfficientNet classification + Grad-CAM on a
    single PIL image. Returns (result_dict, heatmap_b64, warning).
    """
    warning = None
    try:
        face_image, bbox = detect_and_crop_face(image)
    except Exception as e:
        print(f"[DETECT] Face detection failed, using full image: {e}")
        face_image = image
        bbox = {"x": 0, "y": 0, "w": image.width, "h": image.height}
        warning = "No face detected — heatmap may be inaccurate"

    result = classify_image(face_image)
    label = result["label"]
    confidence = result["confidence"]
    low_agreement = result["low_agreement"]

    if warning:
        result["warning"] = warning

    heatmap_b64 = generate_heatmap_overlay(
        face_image=face_image,
        original_image=image,
        bbox=bbox,
        model=get_model(),
        device=get_device(),
    )

    return {
        "label": label,
        "confidence": confidence,
        "low_agreement": low_agreement,
        "warning": result.get("warning"),
        "heatmap": heatmap_b64,
    }


def _detect_frame_for_video(image: Image.Image):
    """
    Run face detection + classification on a single frame for video analysis.
    Returns (result_dict, face_found: bool) — no heatmap for video frames.
    Returns None result if no face is detected.
    """
    try:
        face_image, bbox = detect_and_crop_face(image)
    except Exception:
        return None, False

    result = classify_image(face_image)
    return result, True


# ═══════════════════════════════════════════════════════════════════
# POST /detect — Image detection (Supabase auth) — UNCHANGED LOGIC
# ═══════════════════════════════════════════════════════════════════

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
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Accepted types: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
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

    # ── Rate limit check ──────────────────────────────────────────────
    allowed = await check_and_increment_usage(user["id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Daily scan limit reached (5/day). Upgrade your plan or try again tomorrow.",
        )

    # ── Run detection ────────────────────────────────────────────────
    try:
        result = _detect_single_image(image)

        # Insert scan record
        await insert_scan(
            user_id=user["id"],
            filename=file.filename or "unknown",
            label=result["label"],
            confidence=result["confidence"],
        )

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════
# POST /detect-video — Video detection (Supabase auth)
# ═══════════════════════════════════════════════════════════════════

@app.post("/detect-video")
async def detect_video(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """
    Accept a video, sample 12 frames, run detection on each,
    aggregate results.
    """
    # ── Verify auth token ────────────────────────────────────────────
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    # ── Validate file type ───────────────────────────────────────────
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video type '{file.content_type}'. "
                   f"Accepted types: {', '.join(sorted(ALLOWED_VIDEO_TYPES))}",
        )

    # ── Save to temp file for OpenCV ─────────────────────────────────
    tmp_path = None
    cap = None
    try:
        contents = await file.read()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(tmp_fd)
        with open(tmp_path, "wb") as f:
            f.write(contents)

        # ── Open with OpenCV ─────────────────────────────────────────
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted video file",
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted video file",
            )

        # ── Sample frames evenly ─────────────────────────────────────
        step = max(total_frames // VIDEO_SAMPLE_FRAMES, 1)
        sample_indices = list(range(0, total_frames, step))[:VIDEO_SAMPLE_FRAMES]

        print(f"[VIDEO] Total frames: {total_frames}, sampling {len(sample_indices)} frames (step={step})")

        fake_count = 0
        real_count = 0
        frames_with_no_face = 0
        confidences = []

        for frame_idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            # Convert BGR to RGB PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)

            # Run detection on this frame
            result, face_found = _detect_frame_for_video(pil_image)

            if not face_found:
                frames_with_no_face += 1
                continue

            if result["label"] == "Fake":
                fake_count += 1
            else:
                real_count += 1
            confidences.append(result["confidence"])

        # ── Rate limit check ──────────────────────────────────────────
        allowed = await check_and_increment_usage(user["id"])
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Daily scan limit reached (5/day). Upgrade your plan or try again tomorrow.",
            )

        # ── Check if any frames had faces ────────────────────────────
        total_checked = fake_count + real_count
        if total_checked == 0:
            raise HTTPException(
                status_code=400,
                detail="No face detected in any sampled frame",
            )

        fake_pct = round((fake_count / total_checked) * 100, 2)
        avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        verdict = "Likely Fake" if fake_pct > 50 else "Likely Real"

        # ── Insert scan record ───────────────────────────────────────
        await insert_scan(
            user_id=user["id"],
            filename=file.filename or "unknown_video",
            label=verdict,
            confidence=avg_conf,
        )

        return {
            "fake_frame_percentage": fake_pct,
            "total_frames_checked": total_checked,
            "frames_with_no_face": frames_with_no_face,
            "verdict": verdict,
            "average_confidence": avg_conf,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Video processing failed: {str(e)}",
        )
    finally:
        # ── Memory safety: release resources ─────────────────────────
        if cap is not None:
            cap.release()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
# POST /api/detect — Image detection (API key auth)
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/detect")
async def api_detect(
    file: UploadFile = File(...),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Public API endpoint — authenticates via X-API-Key header.
    Same detection logic as /detect but no Supabase session required.
    """
    # ── Verify API key ───────────────────────────────────────────────
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    try:
        key_record = await verify_api_key(x_api_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # ── Validate file type ───────────────────────────────────────────
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Accepted types: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    # ── Read and open the image ──────────────────────────────────────
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not open the uploaded file as an image.",
        )

    # ── Rate limit check ──────────────────────────────────────────────
    allowed = await check_and_increment_usage(key_record["user_id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Daily scan limit reached (5/day). Upgrade your plan or try again tomorrow.",
        )

    # ── Run detection ────────────────────────────────────────────────
    try:
        result = _detect_single_image(image)

        # Insert scan record under the API key owner
        await insert_scan(
            user_id=key_record["user_id"],
            filename=file.filename or "api_upload",
            label=result["label"],
            confidence=result["confidence"],
        )

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Detection failed. Please try again.",
        )


# ═══════════════════════════════════════════════════════════════════
# API Key Management Endpoints
# ═══════════════════════════════════════════════════════════════════

@app.post("/api-keys/generate")
async def generate_api_key(
    authorization: str = Header(None),
):
    """Generate a new API key for the authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    try:
        result = await create_api_key(user["id"])
        if not result:
            raise HTTPException(status_code=500, detail="Failed to generate API key")

        return {
            "raw_key": result["raw_key"],
            "key_prefix": result["key_prefix"],
            "id": result["id"],
            "created_at": result["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate API key")


@app.get("/api-keys")
async def get_api_keys(
    authorization: str = Header(None),
):
    """List all API keys for the authenticated user (prefixes only)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    keys = await list_api_keys(user["id"])
    return {"keys": keys}


@app.post("/api-keys/revoke")
async def revoke_key(
    authorization: str = Header(None),
    key_id: str = None,
):
    """Revoke an API key by ID."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    if not key_id:
        raise HTTPException(status_code=400, detail="Missing key_id")

    success = await revoke_api_key(key_id, user["id"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke key")

    return {"status": "revoked"}
