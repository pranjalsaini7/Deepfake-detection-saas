"""
Face detection using MediaPipe Tasks API (v0.10+).

Detects the largest face in an image and returns a cropped region
with padding, so the heatmap focuses on the face area.
"""

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import os
import urllib.request

# Path to the face detection model
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "blaze_face_short_range.tflite")
_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"

_detector = None


def _ensure_model():
    """Download the face detection model if it doesn't exist."""
    if not os.path.exists(_MODEL_PATH):
        os.makedirs(_MODEL_DIR, exist_ok=True)
        print(f"[FACE] Downloading face detection model...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print(f"[FACE] Model saved to {_MODEL_PATH}")


def _get_detector():
    global _detector
    if _detector is None:
        _ensure_model()
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=0.5,
        )
        _detector = vision.FaceDetector.create_from_options(options)
    return _detector


def detect_and_crop_face(pil_image, padding_ratio=0.3):
    """
    Detect the largest face and return a cropped PIL image + bounding box.

    Args:
        pil_image: PIL.Image in RGB mode.
        padding_ratio: Extra padding around the detected face (0.3 = 30%).

    Returns:
        (cropped_image, bbox_dict) where bbox_dict has keys:
            x, y, w, h — coordinates in the original image.
        If no face is found, returns (original_image, full_image_bbox).
    """
    img_array = np.array(pil_image)
    h, w = img_array.shape[:2]

    # Convert to MediaPipe Image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)

    detector = _get_detector()
    result = detector.detect(mp_image)

    if not result.detections:
        # No face found — use the full image
        print("[FACE] No face detected, using full image.")
        return pil_image, {"x": 0, "y": 0, "w": w, "h": h}

    # Pick the detection with the highest confidence
    best = max(result.detections, key=lambda d: d.categories[0].score)
    bb = best.bounding_box

    # bb has origin_x, origin_y, width, height (absolute pixels)
    cx = bb.origin_x
    cy = bb.origin_y
    cw = bb.width
    ch = bb.height

    # Add padding
    pad_x = int(cw * padding_ratio)
    pad_y = int(ch * padding_ratio)

    x1 = max(0, cx - pad_x)
    y1 = max(0, cy - pad_y)
    x2 = min(w, cx + cw + pad_x)
    y2 = min(h, cy + ch + pad_y)

    cropped = pil_image.crop((x1, y1, x2, y2))
    bbox = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

    print(f"[FACE] Detected face: ({x1},{y1}) → ({x2},{y2}), confidence={best.categories[0].score:.2f}")

    return cropped, bbox
