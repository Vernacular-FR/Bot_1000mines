# mines_cnn

Prototype local pour entraîner un CNN léger sur les patches générés par `cell_bank`.

## Structure du dossier
```
cnn/
├── README.md
├── config.yaml
├── data/
│   └── cnn_dataset/ (split train/val généré par prepare_cnn_dataset.py)
├── prepare_cnn_dataset.py
└── src/
    ├── __init__.py
    ├── dataset.py
    └── model.py
```

## Préparation du dataset
```powershell
python cnn/data/prepare_cnn_dataset.py `
  --source data_set `
  --dest cnn/data/cnn_dataset `
  --train-ratio 0.8 `
  --seed 42 `
  --overwrite
```
- Résultat : `cnn/data/cnn_dataset/train|val/<label>/`.

## Installation & Entraînement
```powershell
cd cnn
py -3.11 -m venv .venv311
.\.venv311\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
# Mode local (depuis ce dossier)


# Mode global (depuis la racine du repo)
cd ../../../../..
.\Neural_engine\cnn\.venv311\Scripts\activate
python cnn/src/train.py `
  --config cnn/config.yaml `
  --output-dir cnn/artifacts
```
- Si Python 3.11 n’est pas installé : `py install 3.11` ou installeur officiel.
- Le dossier `../artifacts/` contiendra `best_model.pth`, `last_model_*.pth`, `train_log.csv`.

## Modules présents
- `src/dataset.py` : DataLoader + augmentations.
- `src/model.py` : SmallNet (conv-conv-fc) + helpers save/load.
- `src/train.py` : boucle d’entraînement (Adam, ReduceLROnPlateau, early stopping).

## À venir
- `src/infer.py` pour l’inférence batchée.
- `src/bench.py` pour mesurer le throughput.
- Export ONNX / quantization une fois le modèle stabilisé.
