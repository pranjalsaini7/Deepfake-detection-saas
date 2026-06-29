"""
Grad-CAM explainability for EfficientNet-B4.

Uses pytorch-grad-cam to generate a heatmap on the model's last conv block,
applies a facial zone mask from MediaPipe FaceMesh landmarks, and
composites the result back onto the original full image.
"""

import numpy as np
import cv2
from PIL import Image
from io import BytesIO
import base64
import torch
from torchvision import transforms
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image

# ── Preprocessing for Grad-CAM input ────────────────────────────────
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]
_SIZE = 380

_gradcam_transform = transforms.Compose([
    transforms.Resize((_SIZE, _SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=_MEAN, std=_STD),
])

# Landmark indices for facial zone mask
_EYE_LANDMARKS = [33, 133, 362, 263, 159, 145, 386, 374]
_NOSE_LANDMARKS = [6, 197, 195, 5, 4, 1, 2, 98, 327]
_MOUTH_LANDMARKS = [61, 291, 0, 17, 78, 308, 13, 14]
_CHEEK_LANDMARKS = [123, 352, 234, 454, 93, 323]
_FOREHEAD_LANDMARKS = [10, 338, 297, 332, 284, 251, 389, 356,
                       67, 103, 54, 21, 162, 127]
_JAW_LANDMARKS = [172, 136, 150, 149, 176, 148, 152,
                  377, 400, 378, 379, 365, 397]


def _build_face_mask(face_image: Image.Image) -> np.ndarray:
    """
    Use MediaPipe FaceMesh to detect landmarks and build a binary mask
    covering key facial zones (eyes, nose, mouth, cheeks, forehead, jaw).
    Returns a float32 mask of shape (H, W) with values 0 or 1.
    Falls back to an all-ones mask if no face is detected.
    """
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    import os
    import urllib.request

    img_array = np.array(face_image)
    h, w = img_array.shape[:2]

    # Download face landmarker model if needed
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    model_path = os.path.join(model_dir, "face_landmarker.task")
    model_url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

    if not os.path.exists(model_path):
        os.makedirs(model_dir, exist_ok=True)
        print("[HEATMAP] Downloading FaceMesh model...")
        urllib.request.urlretrieve(model_url, model_path)
        print(f"[HEATMAP] Model saved to {model_path}")

    # Create face landmarker
    base_options = mp_python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    # Detect landmarks
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
    result = landmarker.detect(mp_image)

    if not result.face_landmarks:
        print("[HEATMAP] No face landmarks found, using full mask.")
        return np.ones((h, w), dtype=np.float32)

    landmarks = result.face_landmarks[0]

    # Build mask from landmark groups
    mask = np.zeros((h, w), dtype=np.uint8)

    all_groups = [
        _EYE_LANDMARKS,
        _NOSE_LANDMARKS,
        _MOUTH_LANDMARKS,
        _CHEEK_LANDMARKS,
        _FOREHEAD_LANDMARKS,
        _JAW_LANDMARKS,
    ]

    for group in all_groups:
        points = []
        for idx in group:
            if idx < len(landmarks):
                lm = landmarks[idx]
                px = int(lm.x * w)
                py = int(lm.y * h)
                points.append([px, py])
        if len(points) >= 3:
            hull = cv2.convexHull(np.array(points, dtype=np.int32))
            cv2.fillConvexPoly(mask, hull, 255)

    # Dilate mask to cover gaps between regions
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    mask = cv2.dilate(mask, kernel, iterations=2)

    # Apply Gaussian blur for smooth edges
    mask = cv2.GaussianBlur(mask, (31, 31), 0)

    return mask.astype(np.float32) / 255.0


def generate_heatmap_overlay(
    face_image: Image.Image,
    original_image: Image.Image,
    bbox: dict,
    model,
    device: str,
) -> str:
    """
    Generate a Grad-CAM heatmap overlay for the face region,
    masked to facial zones, composited onto the original image.

    Args:
        face_image: cropped face PIL image.
        original_image: full original PIL image.
        bbox: dict with x, y, w, h of face crop in original image.
        model: the EfficientNet model.
        device: "cuda" or "cpu".

    Returns:
        Base64-encoded PNG string of the heatmap overlay.
    """
    face_rgb = face_image.convert("RGB")

    # Prepare input tensor
    input_tensor = _gradcam_transform(face_rgb).unsqueeze(0).to(device)

    # Prepare normalized RGB image for overlay (0-1 float)
    face_resized = face_rgb.resize((_SIZE, _SIZE), Image.LANCZOS)
    rgb_img = np.array(face_resized).astype(np.float32) / 255.0

    # Run Grad-CAM on last EfficientNet block
    target_layer = model.blocks[-1]
    cam = GradCAM(model=model, target_layers=[target_layer])
    grayscale_cam = cam(input_tensor=input_tensor)[0]

    # Build facial zone mask and apply
    face_mask = _build_face_mask(face_resized)

    # Resize mask to match cam output
    if face_mask.shape != grayscale_cam.shape:
        face_mask = cv2.resize(face_mask, (grayscale_cam.shape[1], grayscale_cam.shape[0]))

    # Mask the Grad-CAM output
    masked_cam = grayscale_cam * face_mask

    # Re-normalize after masking
    if masked_cam.max() > 0:
        masked_cam = masked_cam / masked_cam.max()

    # Generate visualization
    visualization = show_cam_on_image(rgb_img, masked_cam, use_rgb=True)

    # Paste heatmap back onto original image at face coordinates
    orig_array = np.array(original_image.convert("RGB"))
    viz_pil = Image.fromarray(visualization)

    # Resize visualization to match original crop size
    crop_w = bbox["w"]
    crop_h = bbox["h"]
    viz_resized = viz_pil.resize((crop_w, crop_h), Image.LANCZOS)

    # Composite onto original
    result_image = Image.fromarray(orig_array.copy())
    result_image.paste(viz_resized, (bbox["x"], bbox["y"]))

    # Resize output to max 800px for reasonable response size
    max_side = 800
    if max(result_image.size) > max_side:
        result_image.thumbnail((max_side, max_side), Image.LANCZOS)

    # Encode to base64 PNG
    buffer = BytesIO()
    result_image.save(buffer, format="PNG", optimize=True)
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Clean up Grad-CAM
    del cam

    return b64_str
