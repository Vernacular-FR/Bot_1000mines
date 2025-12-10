"""
API Python pour charger SmallNet et exécuter des inférences sur les patches.
"""

from pathlib import Path
from typing import Dict, List, Sequence, Optional

import cv2
import numpy as np
import torch
import yaml

from .model import SmallNet, load_model


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_label_mapping(
    train_dir: Optional[Path],
    labels_file: Optional[Path] = None,
) -> Sequence[str]:
    if labels_file:
        try:
            lines = [
                line.strip()
                for line in labels_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except FileNotFoundError:
            lines = []
        if lines:
            return lines
        print(f"[CNN] labels_file vide ou introuvable: {labels_file}, fallback sur train_dir")

    if train_dir and train_dir.exists():
        labels = sorted(p.name for p in train_dir.iterdir() if p.is_dir())
        if labels:
            return labels
        raise RuntimeError(f"Aucun label trouvé dans {train_dir}")

    raise RuntimeError(
        "Impossible de charger les labels: labels_file et dataset train_dir indisponibles"
    )


def normalize_patch(image: np.ndarray) -> torch.Tensor:
    if image.shape != (24, 24):
        image = cv2.resize(image, (24, 24), interpolation=cv2.INTER_AREA)
    tensor = image.astype(np.float32) / 255.0
    tensor = (tensor - 0.5) / 0.5
    return torch.from_numpy(tensor).unsqueeze(0)


class CNNCellClassifier:
    def __init__(
        self,
        config_path: Path,
        model_path: Path,
        device: torch.device | None = None,
    ) -> None:
        self.config_path = config_path
        self.model_path = model_path
        self.config = load_config(config_path)
        dataset_cfg = self.config["dataset"]
        inference_cfg = self.config.get("inference", {})

        config_dir = self.config_path.parent
        train_dir = Path(dataset_cfg["train_dir"])
        if not train_dir.is_absolute():
            train_dir = (config_dir / train_dir).resolve()
        labels_file_cfg = dataset_cfg.get("labels_file")
        labels_file = None
        if labels_file_cfg:
            labels_file = Path(labels_file_cfg)
            if not labels_file.is_absolute():
                labels_file = (config_dir / labels_file).resolve()

        self.labels = load_label_mapping(train_dir, labels_file)
        if len(self.labels) != dataset_cfg["num_classes"]:
            print(
                "[CNN] Avertissement: num_classes=%d mais %d labels détectés"
                % (dataset_cfg["num_classes"], len(self.labels))
            )
        self.accept_threshold = inference_cfg.get("threshold_accept", 0.8)
        self.uncertain_threshold = inference_cfg.get("threshold_uncertain", 0.6)

        if device is None:
            device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.device = device
        self.model: SmallNet = load_model(
            model_path, num_classes=len(self.labels), device=device
        ).to(device)
        self.model.eval()

    def predict_patches(self, patches: Sequence[np.ndarray]) -> List[Dict]:
        if not patches:
            return []
        tensors = [normalize_patch(p) for p in patches]
        batch = torch.stack(tensors).to(self.device)
        with torch.no_grad():
            logits = self.model(batch)
            probs = torch.nn.functional.softmax(logits, dim=1).cpu().numpy()

        results: List[Dict] = []
        for prob_vec in probs:
            top_idx = int(np.argmax(prob_vec))
            results.append(
                {
                    "label": self.labels[top_idx],
                    "confidence": float(prob_vec[top_idx]),
                    "probs": {
                        self.labels[i]: float(prob_vec[i])
                        for i in range(len(self.labels))
                    },
                }
            )
        return results


__all__ = ["CNNCellClassifier", "load_config", "load_label_mapping", "normalize_patch"]
