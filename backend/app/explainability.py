"""
ViT Attention Rollout — visual explainability for ViT-based classifiers.

Extracts attention weights from all transformer layers, computes the
attention rollout (recursive matrix multiplication with residual
connections), and generates a heatmap overlay on the input image.
"""

import numpy as np
import torch
import cv2
from PIL import Image
from io import BytesIO
import base64


def compute_attention_rollout(attentions, discard_ratio=0.0):
    """
    Compute attention rollout from a list of attention matrices.

    Args:
        attentions: list of tensors, each (batch, num_heads, seq_len, seq_len)
        discard_ratio: fraction of lowest attention weights to zero out per layer.

    Returns:
        rollout: numpy array of shape (seq_len,) — attention from CLS to each patch.
    """
    # Average across heads for each layer
    result = None

    for attention in attentions:
        # attention shape: (batch, heads, seq_len, seq_len)
        att_mat = attention.detach().cpu().numpy()
        att_mat = att_mat.squeeze(0)           # (heads, seq_len, seq_len)
        att_mat = np.mean(att_mat, axis=0)     # (seq_len, seq_len) — average over heads

        # Optional: discard low-attention values
        if discard_ratio > 0:
            flat = att_mat.flatten()
            threshold = np.quantile(flat, discard_ratio)
            att_mat[att_mat < threshold] = 0

        # Add residual connection (identity matrix) and re-normalize rows
        residual = np.eye(att_mat.shape[0])
        att_mat = 0.5 * att_mat + 0.5 * residual
        att_mat = att_mat / att_mat.sum(axis=-1, keepdims=True)

        if result is None:
            result = att_mat
        else:
            result = result @ att_mat

    # Extract CLS token's attention to all other tokens
    # CLS is at index 0; patch tokens start at index 1
    cls_attention = result[0, 1:]  # exclude CLS-to-CLS

    return cls_attention


def generate_heatmap_overlay(
    image: Image.Image,
    attentions: list,
    patch_grid_size: int = 14,
    alpha: float = 0.5,
    colormap: int = cv2.COLORMAP_JET,
) -> str:
    """
    Generate a heatmap overlay from ViT attention weights.

    Args:
        image: the input PIL image (cropped face).
        attentions: list of attention tensors from the model.
        patch_grid_size: number of patches per side (ViT-base = 14x14 = 196 patches).
        alpha: transparency of the heatmap overlay.
        colormap: OpenCV colormap to use.

    Returns:
        Base64-encoded PNG string of the heatmap overlay image.
    """
    # Compute attention rollout
    cls_attention = compute_attention_rollout(attentions, discard_ratio=0.1)

    # Reshape to 2D grid
    grid_size = int(np.sqrt(len(cls_attention)))
    if grid_size * grid_size != len(cls_attention):
        grid_size = patch_grid_size

    attention_map = cls_attention[:grid_size * grid_size].reshape(grid_size, grid_size)

    # Normalize to [0, 255]
    attention_map = (attention_map - attention_map.min()) / (attention_map.max() - attention_map.min() + 1e-8)
    attention_map = (attention_map * 255).astype(np.uint8)

    # Resize to match input image dimensions
    img_array = np.array(image)
    h, w = img_array.shape[:2]
    attention_resized = cv2.resize(attention_map, (w, h), interpolation=cv2.INTER_CUBIC)

    # Apply colormap
    heatmap = cv2.applyColorMap(attention_resized, colormap)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    # Blend heatmap with original image
    overlay = (alpha * heatmap + (1 - alpha) * img_array).astype(np.uint8)

    # Resize overlay to max 512px on longest side (keeps response size sane)
    overlay_image = Image.fromarray(overlay)
    max_side = 512
    if max(overlay_image.size) > max_side:
        overlay_image.thumbnail((max_side, max_side), Image.LANCZOS)

    # Encode to base64 JPEG (much smaller than PNG)
    buffer = BytesIO()
    overlay_image.save(buffer, format="JPEG", quality=85)
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return b64_str
