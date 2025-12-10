import math
import random
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader


def _cv_read(path: Path) -> np.ndarray:
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _list_label_folders(root: Path) -> Dict[str, List[Path]]:
    samples: Dict[str, List[Path]] = {}
    for label_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = [
            f
            for f in label_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
        if files:
            samples[label_dir.name] = files
    return samples


def _standardize(image: np.ndarray) -> np.ndarray:
    """Grayscale 24x24 float32 normalized to mean 0, std 1."""
    if image.shape != (24, 24):
        image = cv2.resize(image, (24, 24), interpolation=cv2.INTER_AREA)
    image = image.astype(np.float32) / 255.0
    image = (image - 0.5) / 0.5
    return image


def _apply_augmentations(image: np.ndarray) -> np.ndarray:
    """Small perturbations to avoid overfitting to templates."""
    aug = image.copy()

    # Brightness / contrast jitter
    if random.random() < 0.5:
        alpha = 1.0 + random.uniform(-0.05, 0.05)  # contrast
        beta = random.uniform(-0.05, 0.05)  # brightness
        aug = np.clip(alpha * aug + beta, 0.0, 1.0)

    # Gaussian noise
    if random.random() < 0.3:
        noise = np.random.normal(0.0, 0.01, size=aug.shape).astype(np.float32)
        aug = np.clip(aug + noise, -1.0, 1.0)

    # Sub-pixel shift
    if random.random() < 0.5:
        tx = random.uniform(-1.0, 1.0)
        ty = random.uniform(-1.0, 1.0)
        M = np.float32([[1, 0, tx], [0, 1, ty]])
        aug = cv2.warpAffine(
            aug,
            M,
            (aug.shape[1], aug.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
    return aug


class MinesweeperCellDataset(Dataset):
    """Dataset PyTorch pour les patches 24x24 issus de cell_bank."""

    def __init__(
        self,
        root: Path,
        label_mapping: Sequence[str] = None,
        augment: bool = False,
    ) -> None:
        self.root = Path(root)
        if not self.root.exists():
            raise ValueError(f"Dataset introuvable: {self.root}")
        self.samples_by_label = _list_label_folders(self.root)
        if not self.samples_by_label:
            raise ValueError(f"Aucun patch trouvé dans {self.root}")

        if label_mapping:
            self.labels = list(label_mapping)
        else:
            self.labels = sorted(self.samples_by_label.keys())

        self.label_to_idx = {label: idx for idx, label in enumerate(self.labels)}
        self.samples: List[Tuple[Path, int]] = []
        for label in self.labels:
            paths = self.samples_by_label.get(label, [])
            idx = self.label_to_idx[label]
            self.samples.extend((p, idx) for p in paths)

        self.augment = augment

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        path, label_idx = self.samples[index]
        image = _cv_read(path)
        if image is None:
            raise RuntimeError(f"Impossible de lire {path}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        tensor = _standardize(gray)
        if self.augment:
            tensor = _apply_augmentations(tensor)
        tensor = torch.from_numpy(tensor).unsqueeze(0)  # (1, H, W)
        return tensor, label_idx


def build_dataloader(
    root: Path,
    batch_size: int,
    shuffle: bool,
    num_workers: int = 4,
    label_mapping: Sequence[str] = None,
    augment: bool = False,
) -> DataLoader:
    dataset = MinesweeperCellDataset(
        root=root, label_mapping=label_mapping, augment=augment
    )
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )


__all__ = ["MinesweeperCellDataset", "build_dataloader"]
