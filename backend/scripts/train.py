"""
Fine-tune EfficientNet-B4 on the 140k Real vs Fake Faces dataset.

Strategy:
  Phase 1 — Freeze backbone, train only the classifier head (3 epochs)
  Phase 2 — Unfreeze last 2 EfficientNet blocks + head (7 epochs, lower LR)

Uses mixed-precision (AMP) for speed on CUDA GPUs.
Saves best checkpoint by validation accuracy.
"""

import os
import sys
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import timm


def main():
    # ── Config ───────────────────────────────────────────────────────
    DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "archive", "real_vs_fake", "real-vs-fake")
    SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
    CHECKPOINT_PATH = os.path.join(SAVE_DIR, "efficientnet_b4_deepfake.pth")

    BATCH_SIZE = 16
    # num_workers=0 avoids Windows multiprocessing spawn issues
    NUM_WORKERS = 0
    IMG_SIZE = 380
    PHASE1_EPOCHS = 3
    PHASE2_EPOCHS = 7
    PHASE1_LR = 1e-3
    PHASE2_LR = 1e-4
    WEIGHT_DECAY = 1e-4

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[TRAIN] Device: {DEVICE}")

    # ── Data transforms ─────────────────────────────────────────────
    train_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # ── Datasets ─────────────────────────────────────────────────────
    print("[TRAIN] Loading datasets...")
    train_dataset = datasets.ImageFolder(os.path.join(DATA_ROOT, "train"), transform=train_transform)
    val_dataset = datasets.ImageFolder(os.path.join(DATA_ROOT, "valid"), transform=val_transform)

    print(f"[TRAIN] Train: {len(train_dataset)} images")
    print(f"[TRAIN] Valid: {len(val_dataset)} images")
    print(f"[TRAIN] Classes: {train_dataset.classes}")
    # ImageFolder maps alphabetically: fake=0, real=1

    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=True, drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=True,
    )

    # ── Model ────────────────────────────────────────────────────────
    print("[TRAIN] Loading EfficientNet-B4 pretrained...")
    model = timm.create_model("efficientnet_b4", pretrained=True, num_classes=2)
    model = model.to(DEVICE)

    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler("cuda") if DEVICE == "cuda" else None

    os.makedirs(SAVE_DIR, exist_ok=True)

    def train_one_epoch(epoch, total_epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for i, (images, labels) in enumerate(train_loader):
            images = images.to(DEVICE, non_blocking=True)
            labels = labels.to(DEVICE, non_blocking=True)

            optimizer.zero_grad()

            if scaler:
                with torch.amp.autocast("cuda"):
                    outputs = model(images)
                    loss = criterion(outputs, labels)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

            if (i + 1) % 500 == 0:
                acc = 100.0 * correct / total
                avg_loss = running_loss / (i + 1)
                print(f"  [Epoch {epoch}/{total_epochs}] Step {i+1}/{len(train_loader)} — Loss: {avg_loss:.4f}, Acc: {acc:.2f}%")
                sys.stdout.flush()

        epoch_acc = 100.0 * correct / total
        epoch_loss = running_loss / len(train_loader)
        return epoch_loss, epoch_acc

    @torch.no_grad()
    def validate(loader):
        model.eval()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in loader:
            images = images.to(DEVICE, non_blocking=True)
            labels = labels.to(DEVICE, non_blocking=True)

            if DEVICE == "cuda":
                with torch.amp.autocast("cuda"):
                    outputs = model(images)
                    loss = criterion(outputs, labels)
            else:
                outputs = model(images)
                loss = criterion(outputs, labels)

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        val_acc = 100.0 * correct / total
        val_loss = running_loss / len(loader)
        return val_loss, val_acc

    best_val_acc = 0.0
    skip_phase1 = False
    if os.path.exists(CHECKPOINT_PATH):
        print(f"[TRAIN] Found existing checkpoint at {CHECKPOINT_PATH}. Loading weights...")
        model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True))
        _, val_acc = validate(val_loader)
        best_val_acc = val_acc
        print(f"[TRAIN] Resumed with initial validation accuracy: {best_val_acc:.2f}%")
        skip_phase1 = True
        sys.stdout.flush()

    total_params = sum(p.numel() for p in model.parameters())

    if not skip_phase1:
        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: Freeze backbone, train classifier head only
        # ═══════════════════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("PHASE 1: Training classifier head (backbone frozen)")
        print("=" * 60)
        sys.stdout.flush()

        # Freeze all layers
        for param in model.parameters():
            param.requires_grad = False

        # Unfreeze classifier head
        for param in model.classifier.parameters():
            param.requires_grad = True

        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"[TRAIN] Trainable: {trainable:,} / {total_params:,} params")
        sys.stdout.flush()

        optimizer = optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=PHASE1_LR, weight_decay=WEIGHT_DECAY,
        )

        for epoch in range(1, PHASE1_EPOCHS + 1):
            t0 = time.time()
            train_loss, train_acc = train_one_epoch(epoch, PHASE1_EPOCHS)
            val_loss, val_acc = validate(val_loader)
            elapsed = time.time() - t0

            print(f"  Phase 1 Epoch {epoch}: Train Loss={train_loss:.4f} Acc={train_acc:.2f}% | "
                  f"Val Loss={val_loss:.4f} Acc={val_acc:.2f}% | {elapsed:.0f}s")
            sys.stdout.flush()

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(model.state_dict(), CHECKPOINT_PATH)
                print(f"  ✓ Saved best model (val_acc={val_acc:.2f}%)")
                sys.stdout.flush()
    else:
        print("\n[TRAIN] Skipping Phase 1 (already completed and checkpoint loaded). Resuming directly to Phase 2.")
        sys.stdout.flush()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: Unfreeze last 2 EfficientNet blocks + head
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("PHASE 2: Fine-tuning last 2 blocks + head")
    print("=" * 60)
    sys.stdout.flush()

    # Freeze all layers first (crucial if Phase 1 was skipped)
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze last 2 blocks
    for param in model.blocks[-2:].parameters():
        param.requires_grad = True
    # Also unfreeze conv_head and bn2 (after blocks)
    for param in model.conv_head.parameters():
        param.requires_grad = True
    for param in model.bn2.parameters():
        param.requires_grad = True
    # Also unfreeze classifier head
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[TRAIN] Trainable: {trainable:,} / {total_params:,} params")
    sys.stdout.flush()

    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=PHASE2_LR, weight_decay=WEIGHT_DECAY,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=PHASE2_EPOCHS)

    for epoch in range(1, PHASE2_EPOCHS + 1):
        t0 = time.time()
        train_loss, train_acc = train_one_epoch(epoch, PHASE2_EPOCHS)
        val_loss, val_acc = validate(val_loader)
        scheduler.step()
        elapsed = time.time() - t0

        print(f"  Phase 2 Epoch {epoch}: Train Loss={train_loss:.4f} Acc={train_acc:.2f}% | "
              f"Val Loss={val_loss:.4f} Acc={val_acc:.2f}% | {elapsed:.0f}s")
        sys.stdout.flush()

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), CHECKPOINT_PATH)
            print(f"  ✓ Saved best model (val_acc={val_acc:.2f}%)")
            sys.stdout.flush()

    # ═══════════════════════════════════════════════════════════════
    # FINAL: Test evaluation
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("FINAL: Evaluating on test set")
    print("=" * 60)
    sys.stdout.flush()

    # Load best checkpoint
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True))

    test_dataset = datasets.ImageFolder(os.path.join(DATA_ROOT, "test"), transform=val_transform)
    test_loader = DataLoader(
        test_dataset, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=True,
    )
    print(f"[TRAIN] Test: {len(test_dataset)} images")

    test_loss, test_acc = validate(test_loader)
    print(f"\n  ★ Test Accuracy: {test_acc:.2f}%")
    print(f"  ★ Test Loss: {test_loss:.4f}")
    print(f"  ★ Best Val Accuracy: {best_val_acc:.2f}%")
    print(f"  ★ Checkpoint: {CHECKPOINT_PATH}")
    print(f"\n[TRAIN] DONE!")
    sys.stdout.flush()


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    main()
