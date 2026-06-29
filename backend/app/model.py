"""
EfficientNet-B4 deepfake classifier with TTA and multi-crop analysis.

Loads a pretrained EfficientNet-B4 (2-class) at startup.
Provides:
    - classify_image(face_crop, bbox)  → full result dict
    - get_model() / get_device()       → for Grad-CAM usage
"""

import sys
import torch
import torch.nn as nn
import timm
import numpy as np
from PIL import Image
from torchvision import transforms

# ── Device detection ─────────────────────────────────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[MODEL] Using device: {DEVICE}")

# ── Load EfficientNet-B4 ─────────────────────────────────────────────
print("[MODEL] Loading EfficientNet-B4 …")
try:
    model = timm.create_model("efficientnet_b4", pretrained=True, num_classes=2)
    model.eval()
    model = model.to(DEVICE)
    print("[MODEL] EfficientNet-B4 loaded successfully.")
except Exception as e:
    print(f"[MODEL] FATAL — failed to load model: {e}")
    sys.exit(1)

# ── Label mapping ────────────────────────────────────────────────────
LABELS = {0: "Real", 1: "Fake"}

# ── Base preprocessing ───────────────────────────────────────────────
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]
_SIZE = 380

base_transform = transforms.Compose([
    transforms.Resize((_SIZE, _SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=_MEAN, std=_STD),
])

# ── TTA transforms (8 variants) ─────────────────────────────────────
tta_transforms = [
    # 1. Standard
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 2. Horizontal flip
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.RandomHorizontalFlip(p=1.0),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 3. Brighter
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.ColorJitter(brightness=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 4. Darker
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.ColorJitter(brightness=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 5. Slight zoom
    transforms.Compose([
        transforms.Resize((420, 420)),
        transforms.CenterCrop(_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 6. Rotate +5°
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.RandomRotation(degrees=(5, 5)),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 7. Rotate -5°
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.RandomRotation(degrees=(-5, -5)),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
    # 8. Slight blur
    transforms.Compose([
        transforms.Resize((_SIZE, _SIZE)),
        transforms.GaussianBlur(kernel_size=3),
        transforms.ToTensor(),
        transforms.Normalize(mean=_MEAN, std=_STD),
    ]),
]

# ── Temperature for calibration ──────────────────────────────────────
TEMPERATURE = 0.7
TEMP_THRESHOLD = 0.6  # Only apply temp scaling when raw conf > this


def get_model():
    """Return the loaded EfficientNet model (for Grad-CAM)."""
    return model


def get_device():
    """Return the device string."""
    return DEVICE


def _run_tta(image: Image.Image) -> np.ndarray:
    """
    Run TTA: 8 augmented versions → average softmax.
    Returns numpy array [real_score, fake_score].
    """
    all_probs = []

    for t in tta_transforms:
        tensor = t(image).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.nn.functional.softmax(logits, dim=-1)
            all_probs.append(probs.cpu().numpy()[0])

    # Average across all TTA variants
    avg_probs = np.mean(all_probs, axis=0)
    return avg_probs


def _generate_crops(face_image: Image.Image) -> dict:
    """
    Generate 5 crops from the face region:
    - full: 100% of face
    - upper: top 60%
    - lower: bottom 60%
    - left: left 60%
    - right: right 60%
    """
    w, h = face_image.size

    crops = {
        "full": face_image,
        "upper": face_image.crop((0, 0, w, int(h * 0.6))),
        "lower": face_image.crop((0, int(h * 0.4), w, h)),
        "left": face_image.crop((0, 0, int(w * 0.6), h)),
        "right": face_image.crop((int(w * 0.4), 0, w, h)),
    }

    return crops


def _apply_temperature(logits_avg: np.ndarray, raw_confidence: float) -> np.ndarray:
    """
    Apply temperature scaling to sharpen confident predictions.
    Only applies when raw confidence > threshold.
    """
    if raw_confidence <= TEMP_THRESHOLD:
        return logits_avg

    # Re-apply softmax with temperature
    scaled = logits_avg / TEMPERATURE
    exp_scaled = np.exp(scaled - np.max(scaled))  # numerical stability
    return exp_scaled / exp_scaled.sum()


# ── Crop weights ─────────────────────────────────────────────────────
CROP_WEIGHTS = {
    "full": 0.4,
    "upper": 0.15,
    "lower": 0.15,
    "left": 0.15,
    "right": 0.15,
}


def classify_image(face_image: Image.Image) -> dict:
    """
    Full detection pipeline:
    1. Generate 5 crops from face
    2. Run TTA on each crop
    3. Weighted average
    4. Temperature scaling
    5. Return structured result

    Returns:
        {
            "label": "Fake" | "Real",
            "confidence": float (0-100),
            "low_agreement": bool,
            "warning": str | None,
        }
    """
    face_image = face_image.convert("RGB")

    # Ensure minimum size for crops
    if face_image.width < 50 or face_image.height < 50:
        face_image = face_image.resize((380, 380), Image.LANCZOS)

    # Generate crops
    crops = _generate_crops(face_image)

    # Run TTA on each crop and collect scores
    crop_scores = {}
    for name, crop_img in crops.items():
        # Ensure crop is large enough
        if crop_img.width < 20 or crop_img.height < 20:
            crop_img = crop_img.resize((380, 380), Image.LANCZOS)
        crop_scores[name] = _run_tta(crop_img)

    # Weighted average across crops
    final_scores = np.zeros(2)
    for name, scores in crop_scores.items():
        final_scores += CROP_WEIGHTS[name] * scores

    # Check agreement across crops
    crop_confidences = []
    for name, scores in crop_scores.items():
        pred_idx = np.argmax(scores)
        crop_confidences.append((pred_idx, np.max(scores)))

    # Crops "disagree" if any crop predicts a different class from the majority
    majority_class = np.argmax(final_scores)
    disagreeing = sum(1 for idx, _ in crop_confidences if idx != majority_class)
    low_agreement = disagreeing >= 2  # 2+ out of 5 disagree

    # Raw confidence before temperature
    raw_confidence = float(np.max(final_scores))

    # Apply temperature scaling
    calibrated = _apply_temperature(final_scores, raw_confidence)

    # Final result
    pred_idx = np.argmax(calibrated)
    confidence = float(calibrated[pred_idx]) * 100  # 0-100 scale

    label = LABELS[pred_idx]

    return {
        "label": label,
        "confidence": round(confidence, 2),
        "low_agreement": low_agreement,
        "warning": None,
    }
