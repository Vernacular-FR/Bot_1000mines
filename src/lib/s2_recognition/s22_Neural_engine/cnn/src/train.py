import argparse
import csv
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from torch import nn, optim

try:
    from .dataset import build_dataloader
    from .model import SmallNet, save_model
except ImportError:
    import sys

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.append(str(CURRENT_DIR))
    from dataset import build_dataloader  # type: ignore
    from model import SmallNet, save_model  # type: ignore


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def accuracy_from_logits(logits: torch.Tensor, targets: torch.Tensor) -> float:
    preds = logits.argmax(dim=1)
    correct = (preds == targets).float().sum().item()
    return correct / targets.size(0)


def train_epoch(
    model: nn.Module,
    dataloader,
    optimizer: optim.Optimizer,
    device: torch.device,
) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    total_acc = 0.0
    total_batches = 0
    for inputs, targets in dataloader:
        inputs = inputs.to(device)
        targets = targets.to(device)
        logits = model(inputs)
        loss = F.cross_entropy(logits, targets)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        total_acc += accuracy_from_logits(logits, targets)
        total_batches += 1
    return total_loss / total_batches, total_acc / total_batches


@torch.no_grad()
def evaluate(
    model: nn.Module,
    dataloader,
    device: torch.device,
) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_acc = 0.0
    total_batches = 0
    for inputs, targets in dataloader:
        inputs = inputs.to(device)
        targets = targets.to(device)
        logits = model(inputs)
        loss = F.cross_entropy(logits, targets)
        total_loss += loss.item()
        total_acc += accuracy_from_logits(logits, targets)
        total_batches += 1
    return total_loss / total_batches, total_acc / total_batches


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_labels_file(labels: Sequence[str], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as f:
        for label in labels:
            f.write(f"{label}\n")


def get_device() -> torch.device:
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne SmallNet sur cnn_dataset.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("../config.yaml"),
        help="Chemin vers le fichier config YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../artifacts"),
        help="Répertoire pour sauvegarder checkpoints et logs.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_cfg = config["dataset"]
    training_cfg = config["training"]

    config_dir = args.config.parent.resolve()
    train_dir = Path(dataset_cfg["train_dir"])
    if not train_dir.is_absolute():
        train_dir = (config_dir / train_dir).resolve()
    val_dir = Path(dataset_cfg["val_dir"])
    if not val_dir.is_absolute():
        val_dir = (config_dir / val_dir).resolve()

    train_loader = build_dataloader(
        train_dir,
        batch_size=dataset_cfg["batch_size"],
        shuffle=True,
        num_workers=dataset_cfg.get("num_workers", 4),
        label_mapping=None,
        augment=True,
    )
    val_loader = build_dataloader(
        val_dir,
        batch_size=dataset_cfg["batch_size"],
        shuffle=False,
        num_workers=dataset_cfg.get("num_workers", 4),
        label_mapping=train_loader.dataset.labels,
        augment=False,
    )

    labels_file_cfg = dataset_cfg.get("labels_file")
    if labels_file_cfg:
        labels_file = Path(labels_file_cfg)
        if not labels_file.is_absolute():
            labels_file = (config_dir / labels_file).resolve()
        write_labels_file(train_loader.dataset.labels, labels_file)
        print(f"[INFO] labels.txt mis à jour: {labels_file}")

    set_seed(training_cfg.get("seed", 42))
    device = get_device()
    model = SmallNet(num_classes=dataset_cfg["num_classes"]).to(device)

    optimizer = optim.Adam(
        model.parameters(),
        lr=training_cfg.get("learning_rate", 1e-3),
        weight_decay=training_cfg.get("weight_decay", 0.0),
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )

    epochs = training_cfg.get("epochs", 30)
    patience = training_cfg.get("early_stopping_patience", 5)
    best_val_loss = float("inf")
    best_epoch = 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / "train_log.csv"
    with log_path.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.writer(log_file)
        writer.writerow(
            [
                "epoch",
                "train_loss",
                "train_acc",
                "val_loss",
                "val_acc",
                "lr",
            ]
        )

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device)
        val_loss, val_acc = evaluate(model, val_loader, device)
        scheduler.step(val_loss)

        current_lr = optimizer.param_groups[0]["lr"]
        with log_path.open("a", newline="", encoding="utf-8") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(
                [
                    epoch,
                    f"{train_loss:.4f}",
                    f"{train_acc:.4f}",
                    f"{val_loss:.4f}",
                    f"{val_acc:.4f}",
                    f"{current_lr:.6f}",
                ]
            )

        print(
            f"[EPOCH {epoch}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.3f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.3f} lr={current_lr:.6f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            save_model(model, args.output_dir / "best_model.pth")

        if epoch - best_epoch >= patience:
            print("[EARLY STOP] Patience atteinte, arrêt de l'entraînement.")
            break

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_model(model, args.output_dir / f"last_model_{timestamp}.pth")
    print(f"[DONE] Meilleur epoch: {best_epoch}, log: {log_path}")


if __name__ == "__main__":
    main()
