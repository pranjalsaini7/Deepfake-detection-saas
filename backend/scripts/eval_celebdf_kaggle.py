"""
Out-Of-Distribution (OOD) Evaluation Script for Celeb-DF v2 Dataset on Kaggle.
This script is self-contained and auto-installs missing dependencies.
It runs evaluation directly inside a Kaggle Notebook or any environment containing Celeb-DF v2,
without needing to download the dataset locally.

How to Use on Kaggle:
1. Create a new Python Notebook on Kaggle.
2. Set "GPU T4 x2" or "GPU P100" as the Accelerator (highly recommended).
3. Add the Celeb-DF v2 dataset to the notebook (search for "celeb-df-v2" in Kaggle datasets).
4. Upload your model weights checkpoint `efficientnet_b4_deepfake.pth` as a private dataset or upload it directly.
5. Copy-paste this script into a cell and run it!
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path

# ── Auto-install Dependencies ─────────────────────────────────────────
required_libs = ["timm", "mediapipe", "opencv-python", "scikit-learn", "matplotlib", "pandas", "tqdm", "pillow"]
missing_libs = []
for lib in required_libs:
    try:
        if lib == "opencv-python":
            import cv2
        elif lib == "pillow":
            from PIL import Image
        else:
            __import__(lib)
    except ImportError:
        missing_libs.append(lib)

if missing_libs:
    print(f"Installing missing dependencies: {missing_libs}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_libs])
        print("All dependencies installed successfully.")
    except Exception as e:
        print(f"Failed to install dependencies: {e}. Please install them manually.")
        sys.exit(1)

import cv2
import torch
import torch.nn as nn
import timm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import urllib.request
from tqdm import tqdm
from PIL import Image
from torchvision import transforms
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score, confusion_matrix, ConfusionMatrixDisplay

# ── Model Architecture (Identical to local setup) ──────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
LABELS = {0: "Real", 1: "Fake"}
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]
_SIZE = 380

base_transform = transforms.Compose([
    transforms.Resize((_SIZE, _SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=_MEAN, std=_STD),
])

# 8-variant TTA transforms
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

TEMPERATURE = 0.7
TEMP_THRESHOLD = 0.6
CROP_WEIGHTS = {
    "full": 0.4,
    "upper": 0.15,
    "lower": 0.15,
    "left": 0.15,
    "right": 0.15,
}

# ── Face Detector ────────────────────────────────────────────────────
class BlazeFaceDetector:
    def __init__(self):
        self.model_dir = "models"
        self.model_path = os.path.join(self.model_dir, "blaze_face_short_range.tflite")
        self.model_url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
        self.detector = None

    def _ensure_model(self):
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_dir, exist_ok=True)
            print("[FACE] Downloading Face Detection Model...")
            urllib.request.urlretrieve(self.model_url, self.model_path)
            print(f"[FACE] Model saved to {self.model_path}")

    def get_detector(self):
        if self.detector is None:
            self._ensure_model()
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            base_options = mp_python.BaseOptions(model_asset_path=self.model_path)
            options = vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=0.4,
            )
            self.detector = vision.FaceDetector.create_from_options(options)
        return self.detector

    def detect_and_crop(self, pil_image, padding_ratio=0.3):
        import mediapipe as mp
        img_array = np.array(pil_image)
        h, w = img_array.shape[:2]
        
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
        detector = self.get_detector()
        result = detector.detect(mp_image)

        if not result.detections:
            return None, None

        best = max(result.detections, key=lambda d: d.categories[0].score)
        bb = best.bounding_box
        
        cx, cy, cw, ch = bb.origin_x, bb.origin_y, bb.width, bb.height
        pad_x = int(cw * padding_ratio)
        pad_y = int(ch * padding_ratio)

        x1 = max(0, cx - pad_x)
        y1 = max(0, cy - pad_y)
        x2 = min(w, cx + cw + pad_x)
        y2 = min(h, cy + ch + pad_y)

        if (x2 - x1) < 10 or (y2 - y1) < 10:
            return None, None

        return pil_image.crop((x1, y1, x2, y2)), {"x": x1, "y": y1, "w": x2-x1, "h": y2-y1}

# ── Inference Pipeline Helpers ────────────────────────────────────────
def _run_tta(model, image):
    all_probs = []
    for t in tta_transforms:
        tensor = t(image).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.nn.functional.softmax(logits, dim=-1)
            all_probs.append(probs.cpu().numpy()[0])
    return np.mean(all_probs, axis=0)

def _generate_crops(face_image):
    w, h = face_image.size
    return {
        "full": face_image,
        "upper": face_image.crop((0, 0, w, int(h * 0.6))),
        "lower": face_image.crop((0, int(h * 0.4), w, h)),
        "left": face_image.crop((0, 0, int(w * 0.6), h)),
        "right": face_image.crop((int(w * 0.4), 0, w, h)),
    }

def _apply_temperature(logits_avg, raw_confidence):
    if raw_confidence <= TEMP_THRESHOLD:
        return logits_avg
    scaled = logits_avg / TEMPERATURE
    exp_scaled = np.exp(scaled - np.max(scaled))
    return exp_scaled / exp_scaled.sum()

def classify_face_crop(model, face_image, fast_mode=True):
    """
    Classifies a cropped face image.
    Supports Fast Mode (1 forward pass) and full ensemble mode (40 forward passes).
    """
    face_image = face_image.convert("RGB")
    if face_image.width < 50 or face_image.height < 50:
        face_image = face_image.resize((380, 380), Image.LANCZOS)

    if fast_mode:
        # Fast mode: single forward pass with base transform
        tensor = base_transform(face_image).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()[0]
        pred_idx = np.argmax(probs)
        return probs[1]  # Return probability of class 1 (Fake)
    else:
        # Full ensemble mode (5 crops * 8 TTA = 40 runs)
        crops = _generate_crops(face_image)
        crop_scores = {}
        for name, crop_img in crops.items():
            if crop_img.width < 20 or crop_img.height < 20:
                crop_img = crop_img.resize((380, 380), Image.LANCZOS)
            crop_scores[name] = _run_tta(model, crop_img)

        final_scores = np.zeros(2)
        for name, scores in crop_scores.items():
            final_scores += CROP_WEIGHTS[name] * scores

        raw_confidence = float(np.max(final_scores))
        calibrated = _apply_temperature(final_scores, raw_confidence)
        return calibrated[1]  # Return calibrated probability of class 1 (Fake)

# ── Video Processing ──────────────────────────────────────────────────
def process_video(model, face_detector, video_path, num_frames=10, fast_mode=True):
    """
    Samples frames from video, extracts faces, and averages the prediction probability.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return None

    # Linearly sample frames
    indices = np.linspace(0, total_frames - 1, num=num_frames, dtype=int)
    fake_probs = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        
        # Detect and crop face
        cropped, _ = face_detector.detect_and_crop(pil_img)
        if cropped is not None:
            prob_fake = classify_face_crop(model, cropped, fast_mode=fast_mode)
            fake_probs.append(prob_fake)

    cap.release()
    
    # If no faces were detected in the sampled frames, default to 0.5
    if not fake_probs:
        return 0.5

    return np.mean(fake_probs)

# ── Auto-Detect Paths ─────────────────────────────────────────────────
def find_dataset_and_model_paths():
    """Auto-detect Celeb-DF v2 and Model Checkpoint paths on Kaggle."""
    dataset_dir = None
    model_path = None

    # Common Kaggle root
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        # Search for Celeb-DF
        for path in kaggle_input.rglob("List_of_testing_videos.txt"):
            dataset_dir = path.parent
            print(f"[AUTO] Found Celeb-DF test list at: {path}")
            break
        
        # Search for deepfake weights
        for path in kaggle_input.rglob("*.pth"):
            if "deepfake" in path.name.lower() or "efficientnet" in path.name.lower():
                model_path = path
                print(f"[AUTO] Found model checkpoint at: {path}")
                break

    return dataset_dir, model_path

# ── Main Run ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OOD Evaluation on Celeb-DF v2")
    parser.add_argument("--dataset_dir", type=str, default=None, help="Path to Celeb-DF dataset root")
    parser.add_argument("--model_path", type=str, default=None, help="Path to model checkpoint .pth file")
    parser.add_argument("--num_frames", type=int, default=10, help="Number of frames to sample per video")
    parser.add_argument("--fast_mode", type=bool, default=True, help="Fast mode (no TTA or multi-crop)")
    parser.add_argument("--limit_videos", type=int, default=None, help="Limit number of videos for quick test")
    
    args = parser.parse_args(args=[] if "ipykernel" in sys.modules else None)

    # 1. Search paths
    auto_dataset, auto_model = find_dataset_and_model_paths()
    dataset_dir = args.dataset_dir or auto_dataset
    model_path = args.model_path or auto_model

    # Check validation
    if not dataset_dir or not os.path.exists(dataset_dir):
        print("\n❌ [ERROR] Celeb-DF dataset directory not found or not specified.")
        print("Please add the Celeb-DF v2 dataset to your Kaggle notebook or specify --dataset_dir.")
        return

    if not model_path or not os.path.exists(model_path):
        print("\n❌ [ERROR] Model checkpoint path (.pth) not found or not specified.")
        print("Please upload efficientnet_b4_deepfake.pth to your Kaggle notebook or specify --model_path.")
        return

    print(f"\nConfiguration:")
    print(f" - Device: {DEVICE}")
    print(f" - Dataset Dir: {dataset_dir}")
    print(f" - Model Path: {model_path}")
    print(f" - Frames sampled per video: {args.num_frames}")
    print(f" - Fast Mode: {args.fast_mode}")
    print(f" - Limit Videos: {args.limit_videos or 'All (518)'}")

    # 2. Load Model
    print("\n[MODEL] Loading EfficientNet-B4...")
    model = timm.create_model("efficientnet_b4", pretrained=False, num_classes=2)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()
    model = model.to(DEVICE)
    print("[MODEL] Model loaded successfully.")

    # 3. Load Face Detector
    face_detector = BlazeFaceDetector()

    # 4. Parse Test Video List
    test_list_path = os.path.join(dataset_dir, "List_of_testing_videos.txt")
    if not os.path.exists(test_list_path):
        print(f"❌ [ERROR] Test list file not found: {test_list_path}")
        return

    test_videos = []
    with open(test_list_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ")
            label = int(parts[0])
            rel_path = parts[1]
            test_videos.append((label, rel_path))

    if args.limit_videos:
        # Sample evenly across classes if limiting
        reals = [v for v in test_videos if v[0] == 0]
        fakes = [v for v in test_videos if v[0] == 1]
        lim_each = args.limit_videos // 2
        test_videos = reals[:lim_each] + fakes[:lim_each]
        print(f"[DATA] Limited evaluation to {len(test_videos)} videos ({len(reals[:lim_each])} real, {len(fakes[:lim_each])} fake).")

    # 5. Run Evaluation
    print(f"\n🚀 Running evaluation on {len(test_videos)} videos...")
    
    y_true = []
    y_scores = []
    results = []

    for label, rel_path in tqdm(test_videos, desc="Evaluating"):
        video_path = os.path.join(dataset_dir, rel_path)
        if not os.path.exists(video_path):
            # Sometimes paths are lowercase or nested differently in Kaggle, check fallback
            alt_path = os.path.join(dataset_dir, rel_path.replace("YouTube-real/", "YouTube-real/").replace("Celeb-real/", "Celeb-real/").replace("Celeb-synthesis/", "Celeb-synthesis/"))
            if os.path.exists(alt_path):
                video_path = alt_path
            else:
                print(f"\n⚠️ [WARNING] Video file not found, skipping: {video_path}")
                continue

        prob_fake = process_video(model, face_detector, video_path, num_frames=args.num_frames, fast_mode=args.fast_mode)
        if prob_fake is None:
            continue

        y_true.append(label)
        y_scores.append(prob_fake)
        pred_label = 1 if prob_fake > 0.5 else 0

        results.append({
            "video_path": rel_path,
            "ground_truth": label,
            "predicted_label": pred_label,
            "probability_fake": float(prob_fake)
        })

    # Save details to CSV
    df_results = pd.DataFrame(results)
    df_results.to_csv("celebdf_eval_results.csv", index=False)
    print("\n✅ Saved per-video predictions to 'celebdf_eval_results.csv'")

    # 6. Compute Metrics
    y_true = np.array(y_true)
    y_scores = np.array(y_scores)
    y_pred = (y_scores > 0.5).astype(int)

    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary")
    auc = roc_auc_score(y_true, y_scores)

    print("\n" + "="*50)
    print(" OOD EVALUATION METRICS ON CELEB-DF v2")
    print("="*50)
    print(f" Total Videos Evaluated: {len(y_true)}")
    print(f" Accuracy:               {acc*100:.2f}%")
    print(f" Precision (Fake):        {prec*100:.2f}%")
    print(f" Recall (Fake):           {rec*100:.2f}%")
    print(f" F1-Score (Fake):         {f1*100:.2f}%")
    print(f" AUC-ROC Score:          {auc:.4f}")
    print("="*50)

    # 7. Plots
    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["Real", "Fake"])
    disp.plot(cmap=plt.cm.Blues)
    plt.title("Celeb-DF v2 OOD Confusion Matrix")
    plt.savefig("confusion_matrix.png", dpi=300)
    plt.close()
    print("✅ Saved Confusion Matrix plot to 'confusion_matrix.png'")

    # ROC Curve
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    plt.figure()
    plt.plot(fpr, tpr, color="darkorange", lw=2, label=f"ROC curve (AUC = {auc:.4f})")
    plt.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Celeb-DF v2 OOD ROC Curve")
    plt.legend(loc="lower right")
    plt.savefig("roc_curve.png", dpi=300)
    plt.close()
    print("✅ Saved ROC Curve plot to 'roc_curve.png'")


if __name__ == "__main__":
    main()
