import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

import cv2
import numpy as np
import torch
import yaml

from .model import SmallNet, load_model
from .api import load_label_mapping


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_images(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    images: List[Path] = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        images.extend(path.glob(ext))
    return sorted(images)


def normalize_patch(image: np.ndarray) -> torch.Tensor:
    if image.shape != (24, 24):
        image = cv2.resize(image, (24, 24), interpolation=cv2.INTER_AREA)
    image = image.astype(np.float32) / 255.0
    image = (image - 0.5) / 0.5
    tensor = torch.from_numpy(image).unsqueeze(0)  # (1, H, W)
    return tensor


def load_tensor(path: Path) -> torch.Tensor:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Impossible de lire {path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return normalize_patch(gray)


def softmax(logits: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.softmax(logits, dim=1)


def run_inference(
    images: List[Path],
    model_path: Path,
    labels: Sequence[str],
    device: torch.device,
    batch_size: int,
) -> List[Dict]:
    model = load_model(model_path, num_classes=len(labels), device=device)
    model.eval()
    outputs: List[Dict] = []

    with torch.no_grad():
        for idx in range(0, len(images), batch_size):
            batch_paths = images[idx : idx + batch_size]
            tensors = [load_tensor(p) for p in batch_paths]
            batch = torch.stack(tensors).to(device)
            logits = model(batch)
            probs = softmax(logits).cpu().numpy()

            for path, prob_vec in zip(batch_paths, probs):
                top_idx = int(np.argmax(prob_vec))
                outputs.append(
                    {
                        "file": str(path),
                        "label": labels[top_idx],
                        "confidence": float(prob_vec[top_idx]),
                        "probs": {
                            label: float(prob_vec[i])
                            for i, label in enumerate(labels)
                        },
                    }
                )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Inference CLI pour SmallNet.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Chemin vers config.yaml",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("artifacts/best_model.pth"),
        help="Chemin vers le modèle entraîné",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Image unique ou dossier contenant les patches 24x24",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Taille de batch pour l'inférence",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Chemin de sortie JSON facultatif",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_cfg = config["dataset"]
    inference_cfg = config.get("inference", {})

    config_dir = args.config.parent.resolve()
    train_dir = Path(dataset_cfg["train_dir"])
    if not train_dir.is_absolute():
        train_dir = (config_dir / train_dir).resolve()
    labels_file_cfg = dataset_cfg.get("labels_file")
    labels_file = None
    if labels_file_cfg:
        labels_file = Path(labels_file_cfg)
        if not labels_file.is_absolute():
            labels_file = (config_dir / labels_file).resolve()

    labels = load_label_mapping(train_dir, labels_file)
    if len(labels) != dataset_cfg["num_classes"]:
        print(
            f"[WARN] num_classes={dataset_cfg['num_classes']} "
            f"mais labels détectés={len(labels)}. Mise à jour recommandée."
        )

    images = collect_images(args.input)
    if not images:
        raise SystemExit(f"Aucun patch trouvé dans {args.input}")

    device = (
        torch.device("cuda")
        if torch.cuda.is_available()
        else torch.device("cpu")
    )
    batch_size = args.batch_size or inference_cfg.get("batch_size", 256)

    results = run_inference(
        images=images,
        model_path=args.model,
        labels=labels,
        device=device,
        batch_size=batch_size,
    )

    for item in results:
        print(
            f"[PRED] {item['file']} -> {item['label']} "
            f"(conf={item['confidence']:.3f})"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"[OUTPUT] Résultats sauvegardés dans {args.json}")


if __name__ == "__main__":
    main()
