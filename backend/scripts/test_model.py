"""
Phase 0 – Model smoke-test script.

Usage:
    python test_model.py <path_to_face_image>

Loads the Deep-Fake-Detector-v2-Model via HuggingFace Transformers,
runs inference on the supplied image, and prints the classification
results sorted by confidence score (descending).
"""

import sys
import os

# Fix Windows console encoding (avoids 'charmap' codec errors with Unicode output)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import torch
    from transformers import pipeline
    from PIL import Image
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Make sure you have activated the virtual environment and installed requirements.txt")
    sys.exit(1)


def main():
    # ── Validate CLI args ────────────────────────────────────────────
    if len(sys.argv) < 2:
        print("Usage: python test_model.py <path_to_face_image>")
        sys.exit(1)

    image_path = sys.argv[1]

    # ── Device detection ─────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Using device: {device}")

    # ── Load the model ───────────────────────────────────────────────
    try:
        print("[INFO] Loading Deep-Fake-Detector-v2-Model …")
        classifier = pipeline(
            "image-classification",
            model="prithivMLmods/Deep-Fake-Detector-v2-Model",
            device=0 if device == "cuda" else -1,
        )
        print("[INFO] Model loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        sys.exit(1)

    # ── Open the image ───────────────────────────────────────────────
    try:
        image = Image.open(image_path).convert("RGB")
        print(f"[INFO] Opened image: {image_path}  (size: {image.size})")
    except Exception as e:
        print(f"[ERROR] Failed to open image '{image_path}': {e}")
        sys.exit(1)

    # ── Run inference ────────────────────────────────────────────────
    try:
        results = classifier(image)
        results_sorted = sorted(results, key=lambda r: r["score"], reverse=True)

        print("\n──── Classification Results ────")
        for r in results_sorted:
            print(f"  {r['label']:20s}  {r['score']:.6f}")
        print("────────────────────────────────\n")
    except Exception as e:
        print(f"[ERROR] Inference failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
