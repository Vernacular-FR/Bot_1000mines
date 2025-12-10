"""
Templates - Hiérarchie de templates pour reconnaissance (S2.1)

Implémente la hiérarchie de reconnaissance de symboles:
- Analyse de couleur (premier niveau, rapide)
- Analyse de variance (deuxième niveau, filtrage)
- Template matching (troisième niveau, précis)
- Zero-copy sur les arrays numpy de S1 ImagePatch
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Optional cv2 dependency with fallback
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

from ..s1_capture.s12_patch_segmenter import ImagePatch
from ..s3_tensor.tensor_grid import CellSymbol


class TemplateLevel(Enum):
    """Niveaux de reconnaissance dans la hiérarchie"""
    COLOR_ANALYSIS = "color_analysis"      # Analyse rapide de couleur
    VARIANCE_ANALYSIS = "variance_analysis"  # Analyse de variance
    TEMPLATE_MATCHING = "template_matching" # Matching précis de templates
    UNKNOWN = "unknown"                     # Échec de reconnaissance


@dataclass
class ColorSignature:
    """Signature de couleur pour une cellule"""
    dominant_color: Tuple[int, int, int]  # (R, G, B)
    color_variance: float
    color_histogram: np.ndarray
    confidence: float
    
    def matches_signature(self, other: 'ColorSignature', 
                         threshold: float = 0.8) -> bool:
        """Vérifie si deux signatures correspondent"""
        # Comparaison des couleurs dominantes
        color_diff = np.linalg.norm(
            np.array(self.dominant_color) - np.array(other.dominant_color)
        )
        color_match = color_diff < 50  # Seuil de différence de couleur
        
        # Comparaison de la variance
        variance_diff = abs(self.color_variance - other.color_variance)
        variance_match = variance_diff < 100
        
        return color_match and variance_match


@dataclass
class TemplateMatch:
    """Résultat de matching de template"""
    symbol: CellSymbol
    confidence: float
    match_location: Tuple[int, int]
    match_value: float
    template_level: TemplateLevel
    processing_time: float
    
    def is_reliable(self, threshold: float = 0.7) -> bool:
        """Vérifie si le match est fiable"""
        return self.confidence >= threshold


class CellTemplate:
    """Template pour reconnaissance de cellule"""
    
    def __init__(self, symbol: CellSymbol, template_data: np.ndarray,
                 color_signature: ColorSignature,
                 variance_threshold: float = 500.0):
        """
        Initialise un template de cellule
        
        Args:
            symbol: Symbole représenté
            template_data: Image du template
            color_signature: Signature de couleur
            variance_threshold: Seuil de variance pour le filtrage
        """
        self.symbol = symbol
        self.template_data = template_data
        self.color_signature = color_signature
        self.variance_threshold = variance_threshold
        
        # Précalculer pour l'optimisation (uniquement si cv2 disponible)
        if HAS_CV2 and cv2 is not None:
            self._template_edges = cv2.Canny(
                cv2.cvtColor(template_data, cv2.COLOR_RGB2GRAY), 50, 150
            ) if len(template_data.shape) == 3 else cv2.Canny(template_data, 50, 150)
        else:
            # Fallback: utiliser les données du template directement
            self._template_edges = template_data


class TemplateHierarchy:
    """
    Hiérarchie de templates pour reconnaissance efficiente
    
    Fonctionnalités:
    - Reconnaissance multi-niveaux (couleur → variance → template)
    - Zero-copy sur les arrays numpy
    - Optimisation des performances
    - Gestion des templates dynamiques
    """
    
    def __init__(self, enable_adaptive_thresholds: bool = True,
                 confidence_threshold: float = 0.7):
        """
        Initialise la hiérarchie de templates
        
        Args:
            enable_adaptive_thresholds: Activer les seuils adaptatifs
            confidence_threshold: Seuil de confiance minimum
        """
        # Configuration
        self.enable_adaptive_thresholds = enable_adaptive_thresholds
        self.confidence_threshold = confidence_threshold
        
        # Templates
        self._templates: Dict[CellSymbol, CellTemplate] = {}
        self._color_signatures: Dict[CellSymbol, ColorSignature] = {}
        
        # Seuils adaptatifs
        self._adaptive_thresholds: Dict[str, float] = {
            'color_threshold': 0.8,
            'variance_threshold': 500.0,
            'template_threshold': 0.7
        }
        
        # Statistiques
        self._stats = {
            'recognitions_attempted': 0,
            'color_matches': 0,
            'variance_matches': 0,
            'template_matches': 0,
            'total_recognized': 0,
            'average_processing_time': 0.0
        }
        
        # Initialiser les templates par défaut (uniquement si cv2 disponible)
        if HAS_CV2 and cv2 is not None:
            self._initialize_default_templates()
        else:
            print("⚠️ TemplateHierarchy: cv2 not available, skipping template initialization")
            self._templates = {}
    
    def recognize_cell(self, patch: ImagePatch) -> TemplateMatch:
        """
        Reconnaît le symbole d'une cellule via la hiérarchie
        
        Args:
            patch: Patch d'image de S1 Capture
            
        Returns:
            Résultat de la reconnaissance
        """
        import time
        start_time = time.time()
        
        self._stats['recognitions_attempted'] += 1
        
        try:
            # Niveau 1: Analyse de couleur
            color_result = self._analyze_color_level(patch)
            if color_result:
                self._stats['color_matches'] += 1
                processing_time = time.time() - start_time
                return TemplateMatch(
                    symbol=color_result,
                    confidence=0.9,  # Haute confiance pour couleur
                    match_location=(0, 0),
                    match_value=1.0,
                    template_level=TemplateLevel.COLOR_ANALYSIS,
                    processing_time=processing_time
                )
            
            # Niveau 2: Analyse de variance
            variance_result = self._analyze_variance_level(patch)
            if variance_result:
                self._stats['variance_matches'] += 1
                processing_time = time.time() - start_time
                return TemplateMatch(
                    symbol=variance_result,
                    confidence=0.8,
                    match_location=(0, 0),
                    match_value=0.8,
                    template_level=TemplateLevel.VARIANCE_ANALYSIS,
                    processing_time=processing_time
                )
            
            # Niveau 3: Template matching
            template_result = self._analyze_template_level(patch)
            if template_result:
                self._stats['template_matches'] += 1
                self._stats['total_recognized'] += 1
                processing_time = time.time() - start_time
                return template_result
            
            # Échec de reconnaissance
            processing_time = time.time() - start_time
            return TemplateMatch(
                symbol=CellSymbol.UNKNOWN,
                confidence=0.0,
                match_location=(0, 0),
                match_value=0.0,
                template_level=TemplateLevel.UNKNOWN,
                processing_time=processing_time
            )
            
        except Exception:
            processing_time = time.time() - start_time
            return TemplateMatch(
                symbol=CellSymbol.UNKNOWN,
                confidence=0.0,
                match_location=(0, 0),
                match_value=0.0,
                template_level=TemplateLevel.UNKNOWN,
                processing_time=processing_time
            )
    
    def _analyze_color_level(self, patch: ImagePatch) -> Optional[CellSymbol]:
        """Analyse niveau 1: reconnaissance par couleur"""
        try:
            # Extraire la signature de couleur du patch
            patch_signature = self._extract_color_signature(patch.image_data)
            
            # Comparer avec les signatures connues
            best_match = None
            best_confidence = 0.0
            
            for symbol, signature in self._color_signatures.items():
                if self._compare_color_signatures(patch_signature, signature):
                    confidence = self._calculate_color_confidence(patch_signature, signature)
                    if confidence > best_confidence:
                        best_match = symbol
                        best_confidence = confidence
            
            # Vérifier le seuil
            threshold = self._adaptive_thresholds['color_threshold']
            if best_match and best_confidence >= threshold:
                return best_match
            
            return None
            
        except Exception:
            return None
    
    def _analyze_variance_level(self, patch: ImagePatch) -> Optional[CellSymbol]:
        """Analyse niveau 2: reconnaissance par variance"""
        try:
            # Calculer la variance du patch
            patch_variance = self._calculate_patch_variance(patch.image_data)
            
            # Classification basée sur la variance
            if patch_variance < 100:
                # Très faible variance: vide ou nombre unique
                return CellSymbol.EMPTY
            elif patch_variance > 2000:
                # Très haute variance: nombre élevé ou mine
                return CellSymbol.MINE
            else:
                # Variance moyenne: nombres 1-8
                # Classification plus précise nécessiterait template matching
                return None
            
        except Exception:
            return None
    
    def _analyze_template_level(self, patch: ImagePatch) -> Optional[TemplateMatch]:
        """Analyse niveau 3: template matching précis"""
        try:
            best_match = None
            best_confidence = 0.0
            best_location = (0, 0)
            best_value = 0.0
            
            # Préparer le patch pour le matching
            patch_gray = self._prepare_patch_for_matching(patch.image_data)
            
            # Tester chaque template
            for symbol, template in self._templates.items():
                match_result = self._match_template(patch_gray, template)
                
                if match_result and match_result.confidence > best_confidence:
                    best_match = match_result
                    best_confidence = match_result.confidence
                    best_location = match_result.match_location
                    best_value = match_result.match_value
            
            # Vérifier le seuil
            threshold = self._adaptive_thresholds['template_threshold']
            if best_match and best_confidence >= threshold:
                return best_match
            
            return None
            
        except Exception:
            return None
    
    def _extract_color_signature(self, image: np.ndarray) -> ColorSignature:
        """Extrait la signature de couleur d'une image"""
        # Convertir en RGB si nécessaire
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        
        # Calculer la couleur dominante
        pixels = image.reshape(-1, 3)
        dominant_color = tuple(np.mean(pixels, axis=0).astype(int))
        
        # Calculer la variance de couleur
        color_variance = float(np.var(pixels))
        
        # Calculer l'histogramme de couleur
        hist = cv2.calcHist([image], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = hist.flatten()
        hist = hist / np.sum(hist)  # Normalisation
        
        return ColorSignature(
            dominant_color=dominant_color,
            color_variance=color_variance,
            color_histogram=hist,
            confidence=1.0
        )
    
    def _compare_color_signatures(self, signature1: ColorSignature,
                                 signature2: ColorSignature) -> bool:
        """Compare deux signatures de couleur"""
        # Comparaison des couleurs dominantes
        color_diff = np.linalg.norm(
            np.array(signature1.dominant_color) - np.array(signature2.dominant_color)
        )
        
        # Comparaison des variances
        variance_diff = abs(signature1.color_variance - signature2.color_variance)
        
        # Comparaison des histogrammes
        hist_diff = cv2.compareHist(
            signature1.color_histogram, signature2.color_histogram, cv2.HISTCMP_CORREL
        )
        
        return (color_diff < 50 and variance_diff < 200 and hist_diff > 0.7)
    
    def _calculate_color_confidence(self, signature1: ColorSignature,
                                   signature2: ColorSignature) -> float:
        """Calcule la confiance de correspondance des couleurs"""
        # Distance de couleur normalisée
        color_diff = np.linalg.norm(
            np.array(signature1.dominant_color) - np.array(signature2.dominant_color)
        )
        color_confidence = max(0.0, 1.0 - color_diff / 100.0)
        
        # Différence de variance normalisée
        variance_diff = abs(signature1.color_variance - signature2.color_variance)
        variance_confidence = max(0.0, 1.0 - variance_diff / 500.0)
        
        # Corrélation d'histogramme
        hist_correlation = cv2.compareHist(
            signature1.color_histogram, signature2.color_histogram, cv2.HISTCMP_CORREL
        )
        hist_confidence = max(0.0, hist_correlation)
        
        # Confiance combinée
        return (color_confidence * 0.4 + variance_confidence * 0.3 + hist_confidence * 0.3)
    
    def _calculate_patch_variance(self, image: np.ndarray) -> float:
        """Calcule la variance d'un patch"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        return float(np.var(gray))
    
    def _prepare_patch_for_matching(self, image: np.ndarray) -> np.ndarray:
        """Prépare un patch pour le template matching"""
        # Convertir en niveaux de gris
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Normaliser la taille si nécessaire
        target_size = (24, 24)  # Taille standard des cellules
        if gray.shape != target_size:
            gray = cv2.resize(gray, target_size, interpolation=cv2.INTER_NEAREST)
        
        return gray
    
    def _match_template(self, patch: np.ndarray, 
                       template: CellTemplate) -> Optional[TemplateMatch]:
        """Effectue le template matching"""
        try:
            # Utiliser les contours pour un matching plus robuste
            patch_edges = cv2.Canny(patch, 50, 150)
            
            # Template matching
            result = cv2.matchTemplate(
                patch_edges, template._template_edges, cv2.TM_CCOEFF_NORMED
            )
            
            # Trouver le meilleur match
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > self.confidence_threshold:
                return TemplateMatch(
                    symbol=template.symbol,
                    confidence=float(max_val),
                    match_location=max_loc,
                    match_value=float(max_val),
                    template_level=TemplateLevel.TEMPLATE_MATCHING,
                    processing_time=0.0  # Sera ajouté par l'appelant
                )
            
            return None
            
        except Exception:
            return None
    
    def _initialize_default_templates(self) -> None:
        """Initialise les templates par défaut"""
        # Templates pour les symboles de base
        self._create_basic_templates()
    
    def _create_basic_templates(self) -> None:
        """Crée les templates de base pour les symboles"""
        # Template pour cellule vide (gris clair)
        empty_template = np.full((24, 24, 3), [192, 192, 192], dtype=np.uint8)
        empty_signature = ColorSignature(
            dominant_color=(192, 192, 192),
            color_variance=0.0,
            color_histogram=np.ones(512) / 512,  # Distribution uniforme
            confidence=1.0
        )
        
        self._templates[CellSymbol.EMPTY] = CellTemplate(
            CellSymbol.EMPTY, empty_template, empty_signature
        )
        self._color_signatures[CellSymbol.EMPTY] = empty_signature
        
        # Template pour cellule inconnue (noir)
        unknown_template = np.full((24, 24, 3), [0, 0, 0], dtype=np.uint8)
        unknown_signature = ColorSignature(
            dominant_color=(0, 0, 0),
            color_variance=0.0,
            color_histogram=np.zeros(512),
            confidence=1.0
        )
        
        self._templates[CellSymbol.UNKNOWN] = CellTemplate(
            CellSymbol.UNKNOWN, unknown_template, unknown_signature
        )
        self._color_signatures[CellSymbol.UNKNOWN] = unknown_signature
        
        # Templates pour les nombres (placeholder - seraient générés à partir d'images réelles)
        for i in range(1, 9):
            number_color = (0, 0, 128)  # Bleu foncé pour les nombres
            number_template = np.full((24, 24, 3), [192, 192, 192], dtype=np.uint8)
            # Ajouter le nombre au centre (simplifié)
            cv2.putText(number_template, str(i), (8, 16), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, number_color, 1)
            
            number_signature = ColorSignature(
                dominant_color=(192, 192, 192),  # Fond dominant
                color_variance=1000.0,  # Variance due au nombre
                color_histogram=np.ones(512) / 512,
                confidence=1.0
            )
            
            symbol = getattr(CellSymbol, f'NUMBER_{i}')
            self._templates[symbol] = CellTemplate(
                symbol, number_template, number_signature
            )
            self._color_signatures[symbol] = number_signature
    
    def add_template(self, symbol: CellSymbol, template_image: np.ndarray) -> None:
        """
        Ajoute un nouveau template dynamiquement
        
        Args:
            symbol: Symbole à reconnaître
            template_image: Image du template
        """
        color_signature = self._extract_color_signature(template_image)
        
        template = CellTemplate(
            symbol, template_image, color_signature
        )
        
        self._templates[symbol] = template
        self._color_signatures[symbol] = color_signature
    
    def update_adaptive_thresholds(self, performance_metrics: Dict[str, float]) -> None:
        """
        Met à jour les seuils adaptatifs basés sur les performances
        
        Args:
            performance_metrics: Métriques de performance récentes
        """
        if not self.enable_adaptive_thresholds:
            return
        
        # Ajuster les seuils basés sur le taux de réussite
        success_rate = performance_metrics.get('success_rate', 0.5)
        
        if success_rate < 0.6:
            # Trop d'échecs: abaisser les seuils
            self._adaptive_thresholds['color_threshold'] *= 0.9
            self._adaptive_thresholds['template_threshold'] *= 0.9
        elif success_rate > 0.9:
            # Trop de succès: augmenter les seuils pour plus de précision
            self._adaptive_thresholds['color_threshold'] *= 1.05
            self._adaptive_thresholds['template_threshold'] *= 1.05
        
        # Maintenir les seuils dans des limites raisonnables
        self._adaptive_thresholds['color_threshold'] = np.clip(
            self._adaptive_thresholds['color_threshold'], 0.5, 0.95
        )
        self._adaptive_thresholds['template_threshold'] = np.clip(
            self._adaptive_thresholds['template_threshold'], 0.4, 0.9
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de reconnaissance"""
        stats = self._stats.copy()
        stats.update({
            'templates_count': len(self._templates),
            'recognition_rate': (
                self._stats['total_recognized'] / 
                max(1, self._stats['recognitions_attempted'])
            ),
            'adaptive_thresholds': self._adaptive_thresholds.copy()
        })
        return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        self._stats = {
            'recognitions_attempted': 0,
            'color_matches': 0,
            'variance_matches': 0,
            'template_matches': 0,
            'total_recognized': 0,
            'average_processing_time': 0.0
        }
