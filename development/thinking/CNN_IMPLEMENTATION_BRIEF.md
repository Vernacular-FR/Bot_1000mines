# Prompt pour l’IA de code – Implémentation d’un CNN léger pour reconnaissance de cases du Démineur

## Objectif

Accélérer la reconnaissance des chiffres du Démineur en remplaçant les comparaisons d’images par un réseau de neurones convolutif (CNN) compact, rapide et précis.

## Tâches à effectuer

### 1. **Structure du projet**

* Créer une arborescence claire :

  * `data/raw/` pour les screenshots bruts.
  * `data/digits/0..8/` pour les images de chiffres isolés.
  * `model/` pour le code du CNN et les poids.
  * `src/` pour le code de capture, prétraitement et inference.

### 2. **Extraction automatique des chiffres**

* Écrire un script qui :

  * Charge un screenshot complet du Démineur.
  * Découpe proprement chaque case (coordonnées fixes ou détectées).
  * Normalise l’image (grayscale, 32x32 px, valeurs 0-1).
  * Sauvegarde chaque case dans le bon dossier `data/digits/<label>/`.

### 3. **Dataset et augmentation minimale**

* Appliquer automatiquement :

  * Légers shifts (2–4 px).
  * Légers changements de luminosité.
  * Aucun blur ni rotation (inutile pour ce cas).

### 4. **Modèle CNN minimaliste**

* Construire un modèle *très* simple :

  * **Conv(16 filtres, 3x3)** + ReLU
  * **Conv(32, 3x3)** + ReLU
  * MaxPool
  * Dense(64) + ReLU
  * Dense(9) + Softmax
* Objectif : **<20 ms par inference**.
* Exporter en `model/cnn_digits.h5` + version quantifiée si possible.

### 5. **Entraînement automatique**

* Implémenter un script `train.py` qui :

  * Charge les datasets.
  * Génère un split train/val.
  * Entraîne 5–10 epochs.
  * Sauvegarde le meilleur modèle.

### 6. **Pipeline d’inference**

* Créer `predict.py` qui :

  * Charge le modèle en mémoire.
  * Reçoit une case (numpy array ou image).
  * Applique prétraitement.
  * Retourne un chiffre 0–8.
  * Doit être utilisable dans une boucle haute-fréquence.

### 7. **Intégration dans ton bot existant**

* Remplacer l’ancienne méthode de comparaison d’image par :

  * Capture d’écran.
  * Découpage case par case.
  * Appel à `predict(image)`.

### 8. **Optimisation de performance**

* Charger le modèle une seule fois (pas à chaque frame).
* Utiliser `cv2.resize` pour la vitesse.
* Limiter les allocations dynamiques dans la boucle.
* (Optionnel) Export ONNX pour tester `onnxruntime` si besoin.

### 9. **Tests automatiques**

* Générer un script qui :

  * Valide 100–1000 cases.
  * Affiche accuracy + temps moyen d’inference.

---

## Instruction finale pour l’IA de code

**Implémente *toutes* les étapes ci-dessus, en produisant automatiquement les fichiers, en respectant la structure indiquée, et sans me demander de validation intermédiaire sauf en cas de destruction potentielle de fichiers existants.**










Parfait — voici **un lot complet, précis et actionnable** que tu peux copier-coller dans ton IA de code (ou dans un ticket/gist). L’objectif : fournir une **implémentation clé en main** d’un petit CNN pour classer tes cases 24×24 (classes : `unrevealed` + `digit_1..8`), avec pipeline d’entraînement, d’inférence batched, export et quelques optimisations CPU (quantization / ONNX). Je laisse de côté toute gestion des explosions comme tu l’as demandé, mais je rends l’architecture **extensible** pour l’ajout futur d’un pré-filtre couleur/masque.

Je donne :

1. instructions générales / structure de repo,
2. spécifications techniques et hyper-paramètres,
3. scripts (dataset, model, train, infer, bench, export),
4. tests et métriques à produire,
5. optimisations et points d’attention.

Je fournis aussi des références à lire (classiques) — sans prétendre à l’exhaustivité.

---

# A — Structure du dépôt (à créer)

```
mines_cnn/
├── data/
│   ├── train/          # images organisées par classe (unrevealed, 1..8)
│   │   ├── unrevealed/
│   │   ├── 1/
│   │   └── ...
│   └── val/
├── notebooks/          # optional : tests visuels
├── src/
│   ├── dataset.py      # loader & augmentations
│   ├── model.py        # definition CNN
│   ├── train.py        # training loop
│   ├── infer.py        # inference batched (CPU)
│   ├── bench.py        # bench / time profiling
│   └── utils.py        # helper (metrics, save/load)
├── exports/
├── requirements.txt
├── README.md
└── config.yaml         # hyperparams
```

---

# B — Spécifications / exigences

* Input patch : 24×24 pixels, BGR capture → convert to grayscale (1 channel) or keep 3 channels if tu veux tirer parti des couleurs plus tard. Pour l’instant : **grayscale**.
* Classes : `unrevealed` + `digit_1` … `digit_8` → **10 classes**.
* Framework recommandé : **PyTorch** (simple, exportable en ONNX). Tu peux adapter à TF si tu préfères.
* Format dataset : /train/<class>/*.png (ou .jpg), même pour la val.
* Batch inference : absolument faire des batches (ex. batch_size=256) au lieu d’appeler le modèle per patch.
* Mesures obligatoires : *accuracy, confusion matrix, per-class precision/recall, distribution des scores (softmax max)*.
* Seed pour reproductibilité : fixer `torch.manual_seed(...)`, `np.random.seed(...)`.

---

# C — Architecture recommandée (minuscule, LeNet-like)

Nom : `SmallNet` (taille réduite, ~60k paramètres)

Composants :

* Conv2d(1, 16, kernel=5, padding=2) → ReLU → MaxPool(2)
* Conv2d(16, 32, kernel=5, padding=2) → ReLU → MaxPool(2)
* Flatten
* Linear(32 * 6 * 6, 128) → ReLU
* Linear(128, 64) → ReLU
* Linear(64, 10) → Softmax

Remarques :

* Avec entrée 24×24 → après 2x MaxPool(2) on a 6×6.
* Option : remplace ReLU par LeakyReLU si tu veux plus de robustesse.
* Option « tiny » : réduire filtres à 8/16 si besoin de plus faible empreinte.

---

# D — `requirements.txt`

```
torch>=2.0
torchvision
opencv-python
numpy
tqdm
scikit-learn
onnx
onnxruntime
```

---

# E — Fichiers clés (code) — instructions à transmettre à l’IA de code

### 1) `src/dataset.py`

* Implémenter `MinesDataset(torch.utils.data.Dataset)` :

  * Lecture image (OpenCV), conversion en grayscale `cv2.cvtColor(..., cv2.COLOR_BGR2GRAY)`.
  * Normaliser en float32 : `(img / 255.0 - 0.5) / 0.5` (ou juste `/255`).
  * Retourner `torch.tensor` shape `(1, 24, 24)` et label int.
  * Augmentations légères **uniquement pour l’entraînement** : translations ≤ 1 px, bruit gaussien faible, rotations très petites ±2°, variations de contraste/brightness minimes. (But: ne pas altérer la forme des glyphes.)
  * DataLoader : `num_workers=4` (configurable), `pin_memory=True` si GPU.

### 2) `src/model.py`

* Implémenter `class SmallNet(nn.Module):` avec l’architecture donnée.
* Fournir une fonction `load_model(path)` et `save_model(path)`.

### 3) `src/train.py`

* Argument parser (config.yaml override possible).
* Charger train/val DataLoader.
* Optimizer : `Adam(lr=1e-3)` (ou SGD+momentum 0.9 si tu préfères).
* Scheduler : `ReduceLROnPlateau` ou `StepLR`.
* Loss : `CrossEntropyLoss`.
* Epochs par défaut : 30 (early stopping sur val loss si pas d’amélioration 5 epochs).
* Metrics : accuracy, per-class precision/recall (sklearn), confusion matrix.
* Checkpoint : sauvegarder best model par val accuracy.
* Logging : imprimer epoch / step / val metrics, sauver CSV résumé.

### 4) `src/infer.py`

* API : `predict_batch(model, batch_images)` → retourne `labels, scores` (score = softmax max).
* Faire inference batched (par ex. batch_size=256 configurable).
* Implémenter `infer_grid(image_full, grid_coords)` qui : découpe chaque case 24×24 à partir de la grille (tu as déjà les coords), forme batch, exécute predict. Retourne liste de `(class, score)`.

### 5) `src/bench.py`

* Script qui : charge un ensemble de test (N patches), exécute `n_runs` inférences en batch, mesure `time.perf_counter()` pour chaque run et calcule median/mean/std per batch and per patch.
* Sauver un rapport `bench.json` indiquant `num_patches, batch_size, mean_time_per_patch, std, throughput_patches_per_s`.

### 6) `src/utils.py`

* Helpers pour conversion OpenCV<->torch, affichage confusion matrix (matplotlib optional), sauvegarde/chargements.

### 7) `export` (ONNX + quantization)

* Après entraînement, exporter modèle PyTorch en ONNX :

```py
dummy = torch.randn(1,1,24,24)
torch.onnx.export(model, dummy, "exports/mines.onnx", opset_version=12,
                  input_names=["input"], output_names=["output"])
```

* Tester avec `onnxruntime` pour vérifier outputs égaux (tolérance petite).
* Pour CPU speedup : proposer **dynamic quantization** via PyTorch :

```py
quantized = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
torch.save(quantized.state_dict(), "exports/mines_quant.pth")
```

* Ou exporter ONNX then use `onnxruntime` with `ORT` optimizations. (Mesurer gains.)

---

# F — Hyper-paramètres recommandés (point de départ)

* batch_size (train) : 128 (ou 256 si mémoire ok)
* epochs : 30 (early stopping)
* lr : 1e-3 (Adam)
* weight_decay : 1e-5 (optionnel)
* augment prob : translation 0.5, gaussian noise sigma=0.01 prob=0.3
* threshold confiance (inference) : `score >= 0.8` → accept; `0.6–0.8` → marquer `uncertain` et éventuellement fallback à template matching; `<0.6` → `unknown`.

> Fixer ces valeurs dans `config.yaml` et logguer les expériences.

---

# G — Tests & validation à exiger

1. **Dataset sanity** : script `scripts/check_dataset.py` qui vérifie toutes images 24×24, non corrompues, classes équilibrées (ou log imbalance).
2. **Train/Val split** : 80/20 par défaut. Produire `classification_report` (precision/recall/f1) et confusion matrix.
3. **Bench** : `bench.py` doit produire le temps moyen d’inférence pour N=3000 patches en batchs et la throughput.
4. **Robustness** : tester sur petites perturbations synthétiques (±1 px shift, +noise, small contrast changes) et mesurer drop de précision.
5. **Regression** : enregistrer un “golden” model et vérifier que nouvelles versions ne perdent pas plus de X% d’accuracy.

---

# H — Intégration dans ta pipeline actuelle

* Remplacer la boucle « matchTemplate par case » par :

  1. découpe toutes les cases → assembler `numpy array` shape `(N,1,24,24)`
  2. appeler `infer.py` en un seul batch (ou batches) → récupérer labels et scores
  3. pour scores < `threshold_low` appeler fallback `matchTemplate` ou marquer `unknown` pour re-traitement manuel.
* Cela évite appels Py→C++ répétés et profite pleinement du batch.

---

# I — Optimisations CPU (options à implémenter après mesure)

* **Quantization** (PyTorch dynamic) pour tiny speed gain.
* **ONNX + onnxruntime** pour déploiement sur CPU — souvent plus rapide.
* **TorchScript (jit.trace)** pour fusion d’ops ; tester `torch.jit.script`.
* **Parallel IO** : découpage patches avec `numpy` vectorisé (éviter boucles Python lourdes).
* **Affinity / threads** : régler `OMP_NUM_THREADS` / `MKL_NUM_THREADS` si nécessaire.
* **Profiling** : `torch.profiler` ou `time.perf_counter()` dans `bench.py`.

---

# J — Politique de fallback & extension future

* Fallbacks à prévoir :

  * si `score < 0.6` → fallback template matching sur 1–3 top candidates ;
  * si `0.6 <= score < 0.8` → marquer `uncertain` et utiliser règle heuristique (ex. prioriser non-revelé/digit by frequency).
* Extension explosions plus tard : ajouter pré-filtre couleur HSV pour détecter pixels jaunes/rouges et appliquer **masque** lors de matching (ou feed au CNN images avec 3 channels pour qu’il apprenne à ignorer zones explosives).

---

# K — Tests unitaires à créer (exemples)

* `tests/test_dataset.py` : vérifier shapes, min/max values, augmentations.
* `tests/test_model_forward.py` : passe un batch dummy et vérifie output shape `(N,10)` et somme softmax≈1.
* `tests/test_infer_speed.py` : assert `mean_time_per_patch` < X (remplacer X par valeur mesurée acceptable ; sinon signaler “to be tuned”).

---

# L — Commandes / workflows (exécutables)

* Préparer environment :

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

* Entraîner :

```bash
python src/train.py --config config.yaml
```

* Bench / inference local :

```bash
python src/bench.py --model exports/best.pth --test-data data/val
python src/infer.py --model exports/best.pth --grid path/to/gridcoords.json --image screenshot.png
```

* Export ONNX :

```bash
python -c "from src.model import load; m=load('exports/best.pth'); m.export_onnx('exports/mines.onnx')"
```

---

# M — Résultats attendus et vérification

* Construire un petit set de validation (200–500 patches) couvrant `unrevealed`, `1..8`.
* Après un entraînement bref (5–10 epochs) tu dois voir une montée rapide de l’accuracy sur ce dataset si les templates sont exacts.
* **Mesurer** : précision globale (accuracy), et la *distribution des scores* ; fixer seuils basés sur histogramme.

> Je ne donne pas de chiffres précis d’inférence (ms, throughput) car cela dépend de ta machine. **Mesure** via `bench.py` et ajuste hyper-params/quantization en conséquence.

---

# N — Régressions, logs et reproductibilité

* Sauvegarder : `model.pt`, `config.yaml`, `train_seed`, `train_log.csv`, `val_confusion_matrix.png` dans `exports/` à chaque run.
* Garder un petit README dans `exports/` avec la ligne de commande et les métriques de run.

---

# O — Références (à lire si tu veux)

* LeCun, Y., Bottou, L., Bengio, Y., & Haffner, P. (1998). *Gradient-based learning applied to document recognition*. (LeNet original).
* OpenCV docs — Template Matching & matchTemplate (pour le fallback).
* PyTorch documentation — quantization, JIT, ONNX export.

---

# P — Texte prêt à coller pour ton IA de code

(Version compacte, tout-à-fait à copier dans le prompt)

> Implémente un dépôt `mines_cnn` selon la structure fournie. Objectif : classifier des patches 24×24 en 10 classes (`unrevealed`, `digit_1..8`). Utiliser PyTorch.
>
> * Écrire `src/dataset.py` : loader, augmentations légères (translation ±1px, bruit gaussien faible, small contrast). Normaliser en float32 et renvoyer `(1,24,24)`.
> * Écrire `src/model.py` : `SmallNet` LeNet-like (Conv(1→16,5)->ReLU->MaxPool, Conv(16→32,5)->ReLU->MaxPool, FCs 128→64→10).
> * Écrire `src/train.py` : train loop (Adam lr=1e-3), CrossEntropy, epochs=30, early stopping, sauvegarde meilleur modèle. Générer `train_log.csv` et `confusion_matrix.png`.
> * Écrire `src/infer.py` : découpage batched de N patches (batch_size configurable), inference batched, retourner label+score softmax max. Gérer seuils (accept >=0.8, uncertain 0.6–0.8, fallback <0.6).
> * Écrire `src/bench.py` : mesurer temps pour N patches, throughput, exporter `bench.json`.
> * Ajouter export ONNX et exemple d’utilisation d’onnxruntime. Proposer quantization dynamique et JIT trace.
> * Ajouter tests unitaires de base (dataset shape, model forward, bench).
> * Ne pas inclure gestion des explosions pour l’instant, mais rendre code extensible pour ajouter pré-filtre couleur + masque dans le futur.
> * Fournir README et config.yaml, requirements.txt.
> * Exiger que le code logge les seeds (torch, numpy) pour la reproductibilité.
> * Inclure un script d’évaluation `scripts/evaluate_thresholds.py` qui produit histogramme des scores et propose seuils optimaux.
>   Implémente tout ça et fournis un run d’exemple sur un petit jeu de validation.

---

Si tu veux, je **fournis maintenant** :

* le code complet de `src/model.py` + `src/train.py` + `src/infer.py` prêt à coller (PyTorch),
* ou uniquement un fichier `prompt.txt` prêt à envoyer à ton IA de code.

Dis-moi lequel et je l’écris tout de suite (code complet, commenté et prêt à lancer).
