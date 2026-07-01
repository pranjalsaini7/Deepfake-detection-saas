"""
Diagnostic script for model and dataset validation using pure Python (no pandas).
1. Checks for ID overlap/data leakage across train, val, and test CSVs.
2. Checks validation set class balance.
3. Runs inference on validation examples to identify correct and incorrect predictions.
4. Generates both masked and unmasked (raw) Grad-CAM heatmaps to check for shortcuts (borders, noise, etc.).
"""

import os
import sys
import csv
import torch
import numpy as np
from PIL import Image
import cv2
import timm
from torchvision import transforms
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "archive")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
DIAG_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "diagnostic_gradcam_images")

CHECKPOINT_PATH = os.path.join(MODELS_DIR, "efficientnet_b4_deepfake.pth")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

os.makedirs(DIAG_OUTPUT_DIR, exist_ok=True)

# ── Preprocessing & Transforms ───────────────────────────────────────
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]
_SIZE = 380

val_transform = transforms.Compose([
    transforms.Resize((_SIZE, _SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=_MEAN, std=_STD),
])


def load_csv_ids_and_paths(csv_path):
    ids = set()
    orig_paths = set()
    label_counts = {}
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'id' in row and row['id']:
                ids.add(row['id'].strip())
            if 'original_path' in row and row['original_path']:
                orig_paths.add(row['original_path'].strip())
            if 'label_str' in row and row['label_str']:
                lbl = row['label_str'].strip()
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
                
    return ids, orig_paths, label_counts


def check_leakage_and_composition():
    print("=== Step 1 & 2: Dataset Overlap and Composition ===")
    
    train_csv_path = os.path.join(ARCHIVE_DIR, "train.csv")
    valid_csv_path = os.path.join(ARCHIVE_DIR, "valid.csv")
    test_csv_path = os.path.join(ARCHIVE_DIR, "test.csv")
    
    if not (os.path.exists(train_csv_path) and os.path.exists(valid_csv_path) and os.path.exists(test_csv_path)):
        print("CSV files not found. Skipping CSV check.")
        return False
        
    print("Loading Train CSV...")
    train_ids, train_orig_paths, train_counts = load_csv_ids_and_paths(train_csv_path)
    print("Loading Val CSV...")
    val_ids, val_orig_paths, val_counts = load_csv_ids_and_paths(valid_csv_path)
    print("Loading Test CSV...")
    test_ids, test_orig_paths, test_counts = load_csv_ids_and_paths(test_csv_path)
    
    print(f"\nDataset sizes:")
    print(f"  Train: {sum(train_counts.values())} rows")
    print(f"  Val: {sum(val_counts.values())} rows")
    print(f"  Test: {sum(test_counts.values())} rows")
    
    print("\nClass Balance in Validation Set:")
    for lbl, count in val_counts.items():
        total = sum(val_counts.values())
        print(f"  {lbl}: {count} ({count/total*100:.2f}%)")
        
    train_val_overlap = train_ids.intersection(val_ids)
    train_test_overlap = train_ids.intersection(test_ids)
    val_test_overlap = val_ids.intersection(test_ids)
    
    print(f"\nDirect ID Overlaps:")
    print(f"  Train/Val Overlap: {len(train_val_overlap)} ids")
    print(f"  Train/Test Overlap: {len(train_test_overlap)} ids")
    print(f"  Val/Test Overlap: {len(val_test_overlap)} ids")
    
    overlap_orig_paths = train_orig_paths.intersection(val_orig_paths)
    print(f"  Original Path Overlap: {len(overlap_orig_paths)} paths")
    
    return True


def run_gradcam_diagnostics():
    print("\n=== Step 3: Run Grad-CAM on Validation Examples ===")
    if not os.path.exists(CHECKPOINT_PATH):
        print(f"Checkpoint not found at {CHECKPOINT_PATH}. Cannot run Grad-CAM.")
        return
        
    # Load model
    print(f"Loading model checkpoint from {CHECKPOINT_PATH}...")
    model = timm.create_model("efficientnet_b4", pretrained=False, num_classes=2)
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True))
    model.eval()
    model = model.to(DEVICE)
    
    # Target layer for Grad-CAM
    target_layer = model.blocks[-1]
    cam = GradCAM(model=model, target_layers=[target_layer])
    
    # Find validation files to test
    # We want 5 real and 5 fake validation examples
    val_dir = os.path.join(ARCHIVE_DIR, "real_vs_fake", "real-vs-fake", "valid")
    
    real_dir = os.path.join(val_dir, "real")
    fake_dir = os.path.join(val_dir, "fake")
    
    real_files = [os.path.join(real_dir, f) for f in os.listdir(real_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    fake_files = [os.path.join(fake_dir, f) for f in os.listdir(fake_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    # Sample 5 of each class
    import random
    random.seed(42)
    sample_real = random.sample(real_files, 5)
    sample_fake = random.sample(fake_files, 5)
    
    all_samples = [(f, "real", 1) for f in sample_real] + [(f, "fake", 0) for f in sample_fake]
    
    results = []
    
    # We also want to import the face landmark mask code to show raw vs masked
    sys.path.append(BACKEND_DIR)
    from app.explainability import _build_face_mask
    from app.face_detection import detect_and_crop_face
    
    for path, class_name, true_label in all_samples:
        filename = os.path.basename(path)
        print(f"\nProcessing {class_name} sample: {filename}")
        
        try:
            image = Image.open(path).convert("RGB")
            orig_w, orig_h = image.size
            
            # Detect face
            warning = None
            try:
                face_image, bbox = detect_and_crop_face(image)
                face_found = True
            except Exception as e:
                face_image = image
                bbox = {"x": 0, "y": 0, "w": orig_w, "h": orig_h}
                face_found = False
                warning = "No face detected"
                
            # Classify
            face_tensor = val_transform(face_image).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                logits = model(face_tensor)
                probs = torch.softmax(logits, dim=1)[0]
                pred_label = probs.argmax().item()
                confidence = probs[pred_label].item() * 100
                
            pred_class = "real" if pred_label == 1 else "fake"
            is_correct = (pred_label == true_label)
            print(f"  Prediction: {pred_class} ({confidence:.2f}%) | True: {class_name} | Correct: {is_correct} | Face found: {face_found}")
            
            # Run raw Grad-CAM on the cropped face
            cam_input = val_transform(face_image).unsqueeze(0).to(DEVICE)
            grayscale_cam = cam(input_tensor=cam_input)[0]
            
            # Show cam on image
            face_resized = face_image.convert("RGB").resize((_SIZE, _SIZE), Image.LANCZOS)
            rgb_img = np.array(face_resized).astype(np.float32) / 255.0
            
            # Raw Grad-CAM visualization
            raw_visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
            
            # Masked Grad-CAM visualization
            face_mask = _build_face_mask(face_resized)
            if face_mask.shape != grayscale_cam.shape:
                face_mask = cv2.resize(face_mask, (grayscale_cam.shape[1], grayscale_cam.shape[0]))
            masked_cam = grayscale_cam * face_mask
            if masked_cam.max() > 0:
                masked_cam = masked_cam / masked_cam.max()
            masked_visualization = show_cam_on_image(rgb_img, masked_cam, use_rgb=True)
            
            # Save side by side comparison: [Original Face, Raw Heatmap, Masked Heatmap]
            combined = np.hstack([
                np.array(face_resized),
                raw_visualization,
                masked_visualization
            ])
            
            out_name = f"{class_name}_{'correct' if is_correct else 'incorrect'}_{filename}"
            out_path = os.path.join(DIAG_OUTPUT_DIR, out_name)
            Image.fromarray(combined).save(out_path)
            print(f"  ✓ Saved combined Grad-CAM diagnostic to {out_path}")
            
            results.append({
                "filename": filename,
                "true_label": class_name,
                "pred_label": pred_class,
                "confidence": confidence,
                "correct": is_correct,
                "face_found": face_found,
                "warning": warning,
                "output_image": out_name
            })
            
        except Exception as e:
            print(f"  Error processing sample: {e}")
            import traceback
            traceback.print_exc()

    # Create summary report
    print("\nGrad-CAM Diagnostics Summary:")
    for r in results:
        print(f"  {r['filename']} ({r['true_label']}): Pred={r['pred_label']} ({r['confidence']:.1f}%) | Correct={r['correct']} | Image: {r['output_image']}")


if __name__ == "__main__":
    success = check_leakage_and_composition()
    if success:
        run_gradcam_diagnostics()
