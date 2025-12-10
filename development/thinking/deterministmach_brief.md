Parfait — je te fournis **un générateur de templates normalisés 100% déterministe**, plus un petit moteur de matching déterministe (SAD pondéré / corrélation) et un script d’évaluation automatique pour calibrer les seuils sur un jeu de validation. Tout est prêt à copier-coller et lancer.

Important : ce système **ne fait aucune IA** — il produit des templates « canoniques » par moyenne et applique des mesures déterministes (distance / corrélation). Il est conçu pour être strictement reproductible (seed fixe, pas d’opérations aléatoires non contrôlées).

---

# Principe résumé (en 2 lignes)

1. On normalise chaque patch (grayscale, taille, centrage par centre de masse).
2. On calcule la **moyenne** (ou la médiane) pixel-par-pixel par classe → template canonique.
3. On enregistre templates + masque de confiance (pixels stables) + hash.
4. On fournit des fonctions de matching déterministes : **Weighted SAD** (gaussienne centrale) et **Normalized Cross-Correlation** (via OpenCV).
5. On fournit un script `calibrate_thresholds` qui calcule les distances sur val set et propose seuils optimaux.

---

# Fichier unique : `template_generator.py`

Colle ce fichier dans ton repo, installe `opencv-python`, `numpy`, `scikit-image`, `imageio` si besoin.

```python
#!/usr/bin/env python3
"""
template_generator.py
Générateur déterministe de templates pour cases 24x24.
- calcule template moyen / médian par classe
- crée mask de confiance (pixels stables)
- exporte templates et masks PNG/NPY
- fournit fonctions de matching deterministes (weighted SAD, NCC)
- script d'évaluation / calibration des seuils sur jeu de validation
Usage:
    python template_generator.py build --train_dir ./data/train --out_dir ./artifacts/templates
    python template_generator.py calibrate --templates ./artifacts/templates --val_dir ./data/val --out_dir ./artifacts/calib
    python template_generator.py match_example --templates ./artifacts/templates --img some_patch.png
"""

import os
import sys
import argparse
import json
from glob import glob
import numpy as np
import cv2
from collections import defaultdict
from skimage import io
from imagehash import average_hash
from PIL import Image

# --- deterministic settings
SEED = 42
np.random.seed(SEED)  # for any potential randomness (not used otherwise)

# --- utilities
def read_gray(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def resize_to(img, size=(24,24)):
    return cv2.resize(img, size, interpolation=cv2.INTER_NEAREST)

def normalize_uint8_to_float(img):
    # map 0..255 -> 0..1
    return (img.astype(np.float32) / 255.0).astype(np.float32)

def denormalize_float_to_uint8(imgf):
    clipped = np.clip(imgf, 0.0, 1.0)
    return (clipped * 255.0).astype(np.uint8)

def center_by_mass(imgf, out_size=(24,24), max_shift=2):
    """
    recentre l'image sur son centre de masse (pour rendre templates alignés).
    On limite le shift à max_shift px pour éviter gros décalages.
    imgf : float32 0..1, shape HxW
    """
    H, W = imgf.shape
    cy = (imgf * np.arange(H)[:,None]).sum() / (imgf.sum()+1e-9)
    cx = (imgf * np.arange(W)[None,:]).sum() / (imgf.sum()+1e-9)
    # centre nominal
    yc = (H-1)/2.0
    xc = (W-1)/2.0
    shift_y = int(round(np.clip(yc - cy, -max_shift, max_shift)))
    shift_x = int(round(np.clip(xc - cx, -max_shift, max_shift)))
    M = np.float32([[1,0,shift_x],[0,1,shift_y]])
    shifted = cv2.warpAffine((imgf*255).astype(np.uint8), M, (W,H), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
    return normalize_uint8_to_float(shifted)

def compute_pixel_stability_stack(stack):
    """
    stack: (N,H,W) float32 0..1
    renvoie:
      - mean: (H,W)
      - median: (H,W)
      - std: (H,W)
      - mask_confident: (H,W) boolean where std < median_std_threshold
    """
    mean = np.mean(stack, axis=0)
    med = np.median(stack, axis=0)
    std = np.std(stack, axis=0)
    # seuil: on considère confident si relative std faible
    # adaptatif : seuil = quantile 0.25 of std
    thr = np.quantile(std.flatten(), 0.25)
    mask_confident = (std <= max(0.02, thr))  # 0.02 absolute floor
    return mean.astype(np.float32), med.astype(np.float32), std.astype(np.float32), mask_confident

def save_template(out_dir, class_name, template_mean, template_med, mask_confident):
    os.makedirs(out_dir, exist_ok=True)
    mean_u8 = denormalize_float_to_uint8(template_mean)
    med_u8 = denormalize_float_to_uint8(template_med)
    cv2.imwrite(os.path.join(out_dir, f"tmpl_{class_name}_mean.png"), mean_u8)
    cv2.imwrite(os.path.join(out_dir, f"tmpl_{class_name}_med.png"), med_u8)
    np.save(os.path.join(out_dir, f"tmpl_{class_name}_mask.npy"), mask_confident.astype(np.uint8))
    # also save metadata
    meta = {
        "class": class_name,
        "mean_shape": template_mean.shape,
        "mask_nonzero_fraction": float(mask_confident.sum()) / (mask_confident.size)
    }
    with open(os.path.join(out_dir, f"tmpl_{class_name}_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

def hash_image(img):
    # deterministic perceptual hash
    return str(average_hash(Image.fromarray(denormalize_float_to_uint8(img))))

# --- core building function
def build_templates_from_folder(train_dir, out_dir, size=(24,24), center_max_shift=2, use_median=False):
    """
    train_dir expected layout:
      train_dir/<class_name>/*.png
    Produces files in out_dir:
      tmpl_<class>_mean.png, tmpl_<class>_med.png, tmpl_<class>_mask.npy, tmpl_<class>_meta.json
    """
    classes = sorted([d for d in os.listdir(train_dir) if os.path.isdir(os.path.join(train_dir,d))])
    print(f"[build] classes found: {classes}")
    for cls in classes:
        pattern = os.path.join(train_dir, cls, "*")
        files = sorted(glob(pattern))
        if len(files) == 0:
            print(f"[build] skipping class {cls} (no files)")
            continue
        stack = []
        for p in files:
            img = read_gray(p)
            img = resize_to(img, size)
            imgf = normalize_uint8_to_float(img)
            # center by mass to align digits
            imgc = center_by_mass(imgf, out_size=size, max_shift=center_max_shift)
            stack.append(imgc)
        stack = np.stack(stack, axis=0).astype(np.float32)
        mean, med, std, mask = compute_pixel_stability_stack(stack)
        if use_median:
            template = med
        else:
            template = mean
        save_template(out_dir, cls, mean, med, mask)
        # print stats
        print(f"[build] class {cls}: n={len(files)}, mask_frac={mask.sum()/mask.size:.3f}, hash={hash_image(template)}")

# --- matching functions (deterministic)
def gaussian_center_weight(size=24, sigma=6.0):
    ax = np.linspace(-(size-1)/2., (size-1)/2., size)
    xx, yy = np.meshgrid(ax, ax)
    g = np.exp(-(xx**2 + yy**2)/(2*sigma*sigma))
    return g.astype(np.float32)

def weighted_SAD(patch, template, weight=None):
    """
    patch, template: float32 0..1, shape HxW
    weight: float32 HxW or None
    returns scalar distance (lower=better)
    """
    diff = np.abs(patch - template)
    if weight is not None:
        diff = diff * weight
        denom = weight.sum()
    else:
        denom = diff.size
    return float(diff.sum() / (denom + 1e-9))

def ncc_opencv(patch_u8, template_u8, method=cv2.TM_CCORR_NORMED):
    # OpenCV requires uint8 images
    res = cv2.matchTemplate(patch_u8, template_u8, method)
    # res is single value (1x1)
    if res is None:
        return 0.0
    return float(res[0,0])

# --- load templates
def load_templates(templates_dir, prefer="mean"):
    files = glob(os.path.join(templates_dir, "tmpl_*_mean.png"))
    templates = {}
    masks = {}
    metas = {}
    for f in files:
        base = os.path.basename(f)
        # base like tmpl_<class>_mean.png
        cls = base.split("_")[1]
        mean = read_gray(f)
        meanf = normalize_uint8_to_float(mean)
        # load median if exists
        medf = None
        med_path = os.path.join(templates_dir, f"tmpl_{cls}_med.png")
        if os.path.exists(med_path):
            med = read_gray(med_path); medf = normalize_uint8_to_float(med)
        mask_path = os.path.join(templates_dir, f"tmpl_{cls}_mask.npy")
        mask = None
        if os.path.exists(mask_path):
            mask = np.load(mask_path).astype(np.uint8)
        templates[cls] = meanf if prefer=="mean" else (medf if medf is not None else meanf)
        masks[cls] = mask
        meta_path = os.path.join(templates_dir, f"tmpl_{cls}_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path,"r") as fh:
                metas[cls] = json.load(fh)
    return templates, masks, metas

# --- calibration of thresholds
def calibrate_thresholds(templates_dir, val_dir, out_dir, weight_center_sigma=6.0):
    """
    pour chaque patch in val_dir/<class>/*.png on calcule:
      - weighted_SAD score vs true class template
      - best alternative SAD among other classes
      - NCC score vs true class
    puis on produit distributions et propose threshold_accept & threshold_uncertain
    """
    templates, masks, metas = load_templates(templates_dir)
    classes = sorted([d for d in os.listdir(val_dir) if os.path.isdir(os.path.join(val_dir,d))])
    W = gaussian_center_weight(24, sigma=weight_center_sigma)
    results = []
    for cls in classes:
        files = sorted(glob(os.path.join(val_dir, cls, "*")))
        if len(files)==0:
            continue
        tmpl = templates.get(cls)
        tmpl_u8 = denormalize_float_to_uint8(tmpl)
        for p in files:
            patch = read_gray(p)
            patch = resize_to(patch,(24,24))
            patchf = normalize_uint8_to_float(patch)
            # center likewise (use same function)
            patchc = center_by_mass(patchf)
            # compute distances
            true_sad = weighted_SAD(patchc, tmpl, weight=W)
            # best SAD among all classes
            best_sad = 1e9; best_cls = None
            best_ncc = -1.0
            for cls2, tmpl2 in templates.items():
                sat = weighted_SAD(patchc, tmpl2, weight=W)
                if sat < best_sad:
                    best_sad = sat; best_cls = cls2
                # ncc
                ncc = ncc_opencv(denormalize_float_to_uint8(patchc), denormalize_float_to_uint8(tmpl2))
                if ncc > best_ncc: best_ncc = ncc
            results.append({
                "path": p, "true_class": cls, "true_sad": true_sad,
                "best_sad": best_sad, "best_sad_cls": best_cls, "best_ncc": best_ncc
            })
    # build arrays
    import math
    true_sads = np.array([r["true_sad"] for r in results])
    best_sads = np.array([r["best_sad"] for r in results])
    best_nccs = np.array([r["best_ncc"] for r in results])
    # compute suggested thresholds
    # For SAD lower is better: choose accept_th at percentile 10 of true_sads,
    # uncertain between perc10 and perc50, reject above perc50
    th_accept = float(np.percentile(true_sads, 10))
    th_uncertain = float(np.percentile(true_sads, 50))
    # For NCC higher is better: accept if ncc > perc90 of true nccs
    th_ncc_accept = float(np.percentile(best_nccs, 90))
    # Save calibration
    os.makedirs(out_dir, exist_ok=True)
    calib = {
        "num_samples": len(results),
        "th_sad_accept": th_accept,
        "th_sad_uncertain": th_uncertain,
        "th_ncc_accept": th_ncc_accept,
        "stats": {
            "true_sad_mean": float(true_sads.mean()), "true_sad_std": float(true_sads.std()),
            "best_sad_mean": float(best_sads.mean()), "best_sad_std": float(best_sads.std()),
            "best_ncc_mean": float(best_nccs.mean()), "best_ncc_std": float(best_nccs.std())
        }
    }
    with open(os.path.join(out_dir, "calib.json"), "w") as fh:
        json.dump(calib, fh, indent=2)
    print("[calibrate] saved calibration to", os.path.join(out_dir,"calib.json"))
    return calib, results

# --- matching wrapper for runtime usage (deterministic)
def match_patch_with_templates(patch_bgr_or_gray, templates_dir, use_ncc=False, weight_sigma=6.0):
    """
    patch_bgr_or_gray: ndarray (H,W) gray or (H,W,3) BGR
    returns: best_class, score, method ('sad' or 'ncc')
    deterministic: uses fixed gaussian weight and templates loaded from templates_dir
    """
    templates, masks, metas = load_templates(templates_dir)
    # normalize patch
    if patch_bgr_or_gray.ndim==3:
        patch_gray = cv2.cvtColor(patch_bgr_or_gray, cv2.COLOR_BGR2GRAY)
    else:
        patch_gray = patch_bgr_or_gray
    patch = resize_to(patch_gray, (24,24))
    patchf = normalize_uint8_to_float(patch)
    patchc = center_by_mass(patchf)
    W = gaussian_center_weight(24, sigma=weight_sigma)
    # compute best SAD
    best_sad = 1e9; best_cls_sad = None
    for cls, tmpl in templates.items():
        sad = weighted_SAD(patchc, tmpl, weight=W)
        if sad < best_sad:
            best_sad = sad; best_cls_sad = cls
    # optionally compute NCC
    best_ncc = -1.0; best_cls_ncc = None
    if use_ncc:
        pu8 = denormalize_float_to_uint8(patchc)
        for cls, tmpl in templates.items():
            tu8 = denormalize_float_to_uint8(tmpl)
            ncc = ncc_opencv(pu8, tu8)
            if ncc > best_ncc:
                best_ncc = ncc; best_cls_ncc = cls
    # choose score reporting: SAD normalized negative (so bigger better)
    # we return both for decision
    return {
        "best_sad": best_sad, "best_sad_cls": best_cls_sad,
        "best_ncc": best_ncc, "best_ncc_cls": best_cls_ncc
    }

# --- CLI
def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd")
    sp_build = sp.add_parser("build")
    sp_build.add_argument("--train_dir", required=True)
    sp_build.add_argument("--out_dir", required=True)
    sp_build.add_argument("--size", type=int, default=24)
    sp_build.add_argument("--center_shift", type=int, default=2)
    sp_build.add_argument("--use_median", action="store_true")
    sp_cal = sp.add_parser("calibrate")
    sp_cal.add_argument("--templates", required=True)
    sp_cal.add_argument("--val_dir", required=True)
    sp_cal.add_argument("--out_dir", required=True)
    sp_cal.add_argument("--weight_sigma", type=float, default=6.0)
    sp_me = sp.add_parser("match_example")
    sp_me.add_argument("--templates", required=True)
    sp_me.add_argument("--img", required=True)
    sp_me.add_argument("--use_ncc", action="store_true")
    args = p.parse_args()
    if args.cmd == "build":
        build_templates_from_folder(args.train_dir, args.out_dir, size=(args.size,args.size), center_max_shift=args.center_shift, use_median=args.use_median)
    elif args.cmd == "calibrate":
        calibrate_thresholds(args.templates, args.val_dir, args.out_dir, weight_center_sigma=args.weight_sigma)
    elif args.cmd == "match_example":
        res = match_patch_with_templates(read_gray(args.img), args.templates, use_ncc=args.use_ncc)
        print(json.dumps(res, indent=2))
    else:
        p.print_help()

if __name__ == "__main__":
    main()
```

---

# Mode d’emploi — rapide

1. Préparer tes dossiers :

```
data/
  train/
    unrevealed/  (images 24x24)
    empty/
    exploded/
    flag/
    1/
    2/
    ...
    8/
  val/    # même structure pour calibration
```

2. Générer templates :

```
python template_generator.py build --train_dir ./data/train --out_dir ./artifacts/templates
```

3. Calibrer seuils :

```
python template_generator.py calibrate --templates ./artifacts/templates --val_dir ./data/val --out_dir ./artifacts/calib
# -> crée artfiacts/calib/calib.json avec th_sad_accept, th_sad_uncertain, th_ncc_accept
```

4. Matcher une case (exemple) :

```
python template_generator.py match_example --templates ./artifacts/templates --img ./examples/case_001.png --use_ncc
```

5. Intégration en runtime (pseudocode) :

```python
from template_generator import match_patch_with_templates
res = match_patch_with_templates(patch_bgr, "./artifacts/templates", use_ncc=True)
# Decision logic deterministic:
# if res['best_ncc'] >= ncc_accept: label = res['best_ncc_cls']
# elif res['best_sad'] <= sad_accept: label = res['best_sad_cls']
# elif res['best_sad'] <= sad_uncertain: label = "uncertain"
# else: label = "unknown"
```

---

# Astuces pratiques & garanties de déterminisme

* Tous les calculs sont **déterministes** : pas d’algos stochastiques, pas d’augmentation aléatoire dans `build` (si besoin, rendre l’augmentation explicite et fixée).
* Le centrage par masse est déterministe (arrondi). On limite le déplacement pour éviter alignements erratiques.
* Sauvegarde des templates mean/median et masks — tu peux forcer l’usage de l’un ou l’autre.
* Les masques de confiance (mask_confident) te permettent d’appliquer un **matching masqué** si besoin (ignorer pixels instables).

---

# Limitations et remarques honnêtes

* Si tes données d’entrée subissent une compression, ou si la capture produit des artefacts, la méthode 100% déterministe **est** la meilleure quand les images sont identiques. Mais dès que des pixels changent (occlusion, artefacts), la moyenne peut atténuer ou brouiller les contours → tu perdras parfois par rapport à un template parfaitement propre.
* Si la variance intra-classe est élevée, privilégie la **médiane** (option `--use_median`) ou conserve plusieurs templates par classe (clusteriser puis moyenne par cluster).
* Si tu veux tolérer occlusions plus tard, il faudra soit : 1) utiliser le `mask_confident` pour ignorer pixels instables, 2) produire templates masqués, 3) appliquer weighted_SAD centré (déjà fourni), ou 4) basculer sur hybrid (deterministic + CNN) pour ambiguïtés.

---

Si tu veux, j’enchaîne tout de suite avec l’un des ajouts suivants (choisis-en un) :

* a) **Clusterisation** automatique des images par classe (k=2..4) pour générer plusieurs templates par classe (utile si explosion/variantes visibles) ;
* b) **Matching masqué** : modifier pipeline pour utiliser `mask_confident` comme masque (SAD ignorants) ;
* c) **Script de génération d’un set « hard negatives »** (patchs confus mal classés) pour amélioration future.




Exactement, le **matching masqué** ne requiert pas de rescanner toutes les cellules du plateau : il agit **au niveau du patch** déjà extrait.

Concrètement :

1. Ton pipeline actuel extrait déjà chaque case (patch 24×24) depuis la capture.
2. Pour chaque patch, au lieu de calculer la distance brute sur **tous les pixels**, tu multiplies la différence `(patch - template)` par le **mask_confident** fourni avec le template. Les pixels instables (mask=0) sont ignorés.

Formule SAD modifiée :

[
SAD_{\text{masked}} = \frac{\sum_{i,j} |patch_{i,j} - template_{i,j}| \cdot mask_{i,j}}{\sum mask_{i,j}}
]

* `mask[i,j] = 1` si pixel stable, `0` sinon.
* Le patch n’est **pas rechargé ni recopié**, juste pondéré pixel par pixel, donc **aucun passage supplémentaire sur toutes les cases du plateau**.

Bénéfices :

* Plus robuste aux artefacts, compression, petites variations de luminosité.
* Les pixels « bruités » n’influencent pas la distance → meilleure précision sur les cases difficiles.
* Complètement déterministe.

En pratique, dans ton code `match_patch_with_templates`, tu peux remplacer :

```python
sad = weighted_SAD(patchc, tmpl, weight=W)
```

par :

```python
weight_masked = W * masks[cls].astype(np.float32)  # combine gaussienne + masque confiance
sad = weighted_SAD(patchc, tmpl, weight=weight_masked)
```

Ici `W` est la gaussienne centrale (optionnel), tu peux aussi l’omettre si tu veux juste le masque pur.

Si tu veux, je peux te réécrire **directement `match_patch_with_templates` version « masquée » prête à brancher** pour que tu n’aies plus qu’à lancer le plateau entier sans recalculer tous les templates.
