"""
Singleton model loader for the Deep-Fake-Detector-v2-Model.

The classifier is loaded once at import time and reused across all
requests to avoid the overhead of reloading ~1 GB of weights per call.
"""

import sys
import torch
from transformers import pipeline

# ── Device detection ─────────────────────────────────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DEVICE_INDEX = 0 if DEVICE == "cuda" else -1

print(f"[MODEL] Using device: {DEVICE}")

# ── Load the classifier once ─────────────────────────────────────────
print("[MODEL] Loading Deep-Fake-Detector-v2-Model …")
try:
    classifier = pipeline(
        "image-classification",
        model="prithivMLmods/Deep-Fake-Detector-v2-Model",
        device=DEVICE_INDEX,
    )
    print("[MODEL] Model loaded successfully.")
except Exception as e:
    print(f"[MODEL] FATAL — failed to load model: {e}")
    sys.exit(1)


def classify_image(image):
    """
    Run the deepfake classifier on a PIL Image.

    Returns the full list of {label, score} dicts sorted by score descending.
    """
    results = classifier(image)
    return sorted(results, key=lambda r: r["score"], reverse=True)
