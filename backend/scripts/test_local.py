"""
Local-only test: test the EfficientNet + Grad-CAM pipeline without auth.
Calls the model and heatmap modules directly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from app.model import classify_image, get_model, get_device
from app.face_detection import detect_and_crop_face
from app.explainability import generate_heatmap_overlay
import base64

# Load test image
img_path = os.path.join(os.path.dirname(__file__), "..", "..", "pexels-manishjangid-18938081.jpg")
print(f"Loading image: {img_path}")
image = Image.open(img_path).convert("RGB")
print(f"Image size: {image.size}")

# Step 1: Face detection
print("\n=== Face Detection ===")
face_image, bbox = detect_and_crop_face(image)
print(f"Face crop size: {face_image.size}")
print(f"Bbox: {bbox}")

# Step 2: Classification (TTA + multi-crop)
print("\n=== Classification (TTA + Multi-crop) ===")
result = classify_image(face_image)
print(f"Label: {result['label']}")
print(f"Confidence: {result['confidence']}%")
print(f"Low agreement: {result['low_agreement']}")
print(f"Warning: {result['warning']}")

# Step 3: Grad-CAM heatmap
print("\n=== Grad-CAM Heatmap ===")
heatmap_b64 = generate_heatmap_overlay(
    face_image=face_image,
    original_image=image,
    bbox=bbox,
    model=get_model(),
    device=get_device(),
)
print(f"Heatmap base64 length: {len(heatmap_b64)} chars")

# Save heatmap
heatmap_bytes = base64.b64decode(heatmap_b64)
out_path = os.path.join(os.path.dirname(__file__), "..", "..", "test_gradcam_output.png")
with open(out_path, "wb") as f:
    f.write(heatmap_bytes)
print(f"Heatmap saved to: {out_path}")

print("\n=== ALL TESTS PASSED ===")
