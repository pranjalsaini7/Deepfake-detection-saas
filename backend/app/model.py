"""
Singleton model loader for the Deep-Fake-Detector-v2-Model.

Exposes:
    - classify_image(image)          → [{label, score}]  (via pipeline)
    - classify_with_attention(image) → (results, attentions)  (for explainability)
"""

import sys
import torch
from transformers import pipeline, ViTForImageClassification, ViTImageProcessor

# ── Device detection ─────────────────────────────────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DEVICE_INDEX = 0 if DEVICE == "cuda" else -1

print(f"[MODEL] Using device: {DEVICE}")

# ── Model name ───────────────────────────────────────────────────────
MODEL_NAME = "prithivMLmods/Deep-Fake-Detector-v2-Model"

# ── Load the classifier pipeline ─────────────────────────────────────
print("[MODEL] Loading Deep-Fake-Detector-v2-Model …")
try:
    classifier = pipeline(
        "image-classification",
        model=MODEL_NAME,
        device=DEVICE_INDEX,
    )

    # Also load the raw model + processor for attention extraction
    # Must use "eager" attention (not SDPA) to get attention weights
    vit_model = ViTForImageClassification.from_pretrained(
        MODEL_NAME, attn_implementation="eager"
    )
    vit_model.to(DEVICE)
    vit_model.eval()

    vit_processor = ViTImageProcessor.from_pretrained(MODEL_NAME)

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


def classify_with_attention(image):
    """
    Run inference AND return attention weights from every ViT layer.

    Args:
        image: PIL Image in RGB mode.

    Returns:
        (results, attentions) where:
            results: [{label, score}] sorted descending
            attentions: tuple of tensors, one per layer,
                        each (1, num_heads, seq_len, seq_len)
    """
    # Preprocess
    inputs = vit_processor(images=image, return_tensors="pt").to(DEVICE)

    # Forward pass with attention output
    with torch.no_grad():
        outputs = vit_model(**inputs, output_attentions=True)

    # Convert logits to probabilities
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

    # Build results list matching the pipeline format
    id2label = vit_model.config.id2label
    results = []
    for idx, score in enumerate(probs[0]):
        results.append({
            "label": id2label[idx],
            "score": score.item(),
        })
    results = sorted(results, key=lambda r: r["score"], reverse=True)

    return results, outputs.attentions
