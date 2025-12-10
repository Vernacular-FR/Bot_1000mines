from pathlib import Path
from typing import Optional

import torch
from torch import nn


class SmallNet(nn.Module):
    """
    Réseau convolutionnel compact pour classifier les patches 24x24.
    Architecture :
        Conv(1→16, k=5, p=2) + ReLU + MaxPool(2)
        Conv(16→32, k=5, p=2) + ReLU + MaxPool(2)
        FC 32*6*6 → 128 → 64 → num_classes
    """

    def __init__(self, num_classes: int = 12) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(16, 32, kernel_size=5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 6 * 6, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x


def save_model(model: nn.Module, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)


def load_model(
    path: Path, num_classes: int = 12, device: Optional[torch.device] = None
) -> SmallNet:
    model = SmallNet(num_classes=num_classes)
    state_dict = torch.load(path, map_location=device or "cpu")
    model.load_state_dict(state_dict)
    return model


__all__ = ["SmallNet", "save_model", "load_model"]
