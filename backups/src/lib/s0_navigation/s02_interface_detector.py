"""
InterfaceDetector - Détection d'éléments d'interface UI (S0.2)

Détecte et masque les éléments d'interface pour optimiser l'analyse:
- Identification des éléments UI (status, controls, liens)
- Génération de masques pour exclusion des zones non-jeu
- Calibration des positions relatives au game canvas
- Support pour différentes résolutions et mises en page
"""

import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np


class UIElementType(Enum):
    """Types d'éléments d'interface"""
    STATUS_BAR = "status_bar"
    GAME_CONTROLS = "game_controls"
    ESCAPE_LINK = "escape_link"
    TIMER = "timer"
    MINE_COUNTER = "mine_counter"
    DIFFICULTY_SELECTOR = "difficulty_selector"
    FACE_BUTTON = "face_button"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """Élément d'interface détecté"""
    element_type: UIElementType
    selector: str
    bounds: Tuple[int, int, int, int]  # (x, y, width, height)
    position: Tuple[int, int]  # (x, y) coin supérieur gauche
    size: Tuple[int, int]  # (width, height)
    is_obstructive: bool  # Si l'élément obstrue la grille de jeu
    confidence: float  # Confiance de la détection (0.0..1.0)
    timestamp: float
    
    def get_mask_region(self) -> Tuple[int, int, int, int]:
        """Retourne la région pour le masque d'exclusion"""
        if self.is_obstructive:
            # Étendre légèrement la région pour les éléments obstructifs
            margin = 5
            return (
                self.position[0] - margin,
                self.position[1] - margin,
                self.size[0] + 2 * margin,
                self.size[1] + 2 * margin
            )
        return self.bounds
    
    def overlaps_with(self, x: int, y: int, width: int, height: int) -> bool:
        """Vérifie si l'élément chevauche une région donnée"""
        ex, ey, ew, eh = self.bounds
        
        return not (
            x + width < ex or  # À gauche
            x > ex + ew or     # À droite
            y + height < ey or # Au-dessus
            y > ey + eh        # En-dessous
        )


@dataclass
class InterfaceMask:
    """Masque d'interface pour exclusion"""
    width: int
    height: int
    mask_array: np.ndarray  # True = zone à exclure
    elements: List[UIElement]
    timestamp: float
    
    def should_exclude_pixel(self, x: int, y: int) -> bool:
        """Vérifie si un pixel doit être exclu"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return bool(self.mask_array[y, x])
        return True  # Exclure les pixels hors limites
    
    def get_usable_region(self) -> Tuple[int, int, int, int]:
        """Retourne la région utilisable (x, y, width, height)"""
        # Trouver les bornes de la zone non masquée
        non_masked = np.where(~self.mask_array)
        
        if len(non_masked[0]) == 0:
            return (0, 0, self.width, self.height)  # Tout masqué
        
        y_min, y_max = non_masked[0].min(), non_masked[0].max()
        x_min, x_max = non_masked[1].min(), non_masked[1].max()
        
        return (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)


class InterfaceDetector:
    """
    Détecteur d'interface pour l'optimisation de l'analyse
    
    Fonctionnalités:
    - Détection automatique des éléments UI
    - Génération de masques d'exclusion
    - Calibration dynamique des positions
    - Support pour les variations de layout
    """
    
    def __init__(self, enable_adaptive_detection: bool = True,
                 detection_confidence_threshold: float = 0.7):
        """
        Initialise le détecteur d'interface
        
        Args:
            enable_adaptive_detection: Activer la détection adaptative
            detection_confidence_threshold: Seuil de confiance pour la détection
        """
        # Configuration
        self.enable_adaptive_detection = enable_adaptive_detection
        self.confidence_threshold = detection_confidence_threshold
        
        # Configuration des éléments UI attendus
        self.ui_config = self._get_default_ui_config()
        
        # État de détection
        self.detected_elements: List[UIElement] = []
        self.current_mask: Optional[InterfaceMask] = None
        self.last_detection_time: float = 0.0
        
        # Cache et optimisations
        self._detection_cache: Dict[str, Any] = {}
        self._cache_validity: float = 30.0  # 30 secondes
        
        # Statistiques
        self._stats = {
            'detections_performed': 0,
            'elements_detected': 0,
            'mask_regenerations': 0,
            'average_detection_time': 0.0
        }
    
    def detect_interface_elements(self, screenshot: np.ndarray,
                                 canvas_offset: Tuple[int, int] = (0, 0)) -> List[UIElement]:
        """
        Détecte les éléments d'interface dans une capture d'écran
        
        Args:
            screenshot: Image de la capture d'écran
            canvas_offset: Offset du canvas game dans l'image
            
        Returns:
            Liste des éléments détectés
        """
        start_time = time.time()
        
        # Vérifier le cache
        cache_key = self._generate_cache_key(screenshot.shape, canvas_offset)
        if self._is_cache_valid(cache_key):
            self._stats['detections_performed'] += 1
            return self.detected_elements.copy()
        
        # Détecter chaque type d'élément
        detected = []
        
        for element_config in self.ui_config:
            elements = self._detect_element_type(
                screenshot, element_config, canvas_offset
            )
            detected.extend(elements)
        
        # Filtrer par confiance
        high_confidence_elements = [
            e for e in detected if e.confidence >= self.confidence_threshold
        ]
        
        # Mettre à jour l'état
        self.detected_elements = high_confidence_elements
        self.last_detection_time = time.time()
        
        # Mettre en cache
        self._update_cache(cache_key, screenshot.shape, canvas_offset)
        
        # Mettre à jour les statistiques
        detection_time = time.time() - start_time
        self._update_stats(len(high_confidence_elements), detection_time)
        
        return high_confidence_elements
    
    def generate_interface_mask(self, screenshot: np.ndarray,
                               elements: Optional[List[UIElement]] = None) -> InterfaceMask:
        """
        Génère un masque d'interface à partir des éléments détectés
        
        Args:
            screenshot: Image de référence
            elements: Liste des éléments (None = utilise les éléments détectés)
            
        Returns:
            Masque d'interface
        """
        if elements is None:
            elements = self.detected_elements
        
        height, width = screenshot.shape[:2]
        mask = np.zeros((height, width), dtype=bool)
        
        # Appliquer chaque élément au masque
        for element in elements:
            if element.is_obstructive:
                x, y, w, h = element.get_mask_region()
                
                # S'assurer que les coordonnées sont dans les limites
                x = max(0, min(x, width))
                y = max(0, min(y, height))
                x_end = max(0, min(x + w, width))
                y_end = max(0, min(y + h, height))
                
                mask[y:y_end, x:x_end] = True
        
        # Créer le masque d'interface
        interface_mask = InterfaceMask(
            width=width,
            height=height,
            mask_array=mask,
            elements=elements.copy(),
            timestamp=time.time()
        )
        
        self.current_mask = interface_mask
        self._stats['mask_regenerations'] += 1
        
        return interface_mask
    
    def get_usable_coordinates(self, screenshot: np.ndarray) -> List[Tuple[int, int]]:
        """
        Retourne les coordonnées utilisables (non masquées)
        
        Args:
            screenshot: Image de référence
            
        Returns:
            Liste des coordonnées (x, y) utilisables
        """
        if self.current_mask is None:
            self.generate_interface_mask(screenshot)
        
        if self.current_mask is None:
            return []
        
        # Extraire les coordonnées non masquées
        non_masked_coords = np.where(~self.current_mask.mask_array)
        
        return list(zip(non_masked_coords[1], non_masked_coords[0]))
    
    def is_coordinate_usable(self, x: int, y: int) -> bool:
        """
        Vérifie si une coordonnée est utilisable
        
        Args:
            x, y: Coordonnées à vérifier
            
        Returns:
            True si la coordonnée est utilisable
        """
        if self.current_mask is None:
            return True  # Pas de masque = tout utilisable
        
        return not self.current_mask.should_exclude_pixel(x, y)
    
    def update_ui_config(self, custom_config: List[Dict[str, Any]]) -> None:
        """
        Met à jour la configuration des éléments UI
        
        Args:
            custom_config: Configuration personnalisée
        """
        self.ui_config = custom_config
        self._invalidate_cache()
    
    def _get_default_ui_config(self) -> List[Dict[str, Any]]:
        """Retourne la configuration par défaut des éléments UI"""
        return [
            {
                'type': UIElementType.ESCAPE_LINK,
                'selector': 'a#escape',
                'expected_size': (21, 95),
                'position_hint': 'top_left',
                'is_obstructive': True,
                'color_range': [(100, 150, 200), (150, 200, 250)],  # Bleu
                'detection_method': 'template_color'
            },
            {
                'type': UIElementType.STATUS_BAR,
                'selector': 'div#status',
                'expected_size': (200, 30),
                'position_hint': 'top',
                'is_obstructive': True,
                'detection_method': 'template_text'
            },
            {
                'type': UIElementType.GAME_CONTROLS,
                'selector': 'div.game-controls',
                'expected_size': (300, 50),
                'position_hint': 'bottom',
                'is_obstructive': True,
                'detection_method': 'template_layout'
            },
            {
                'type': UIElementType.TIMER,
                'selector': 'div.timer',
                'expected_size': (80, 30),
                'position_hint': 'top_right',
                'is_obstructive': False,
                'detection_method': 'template_ocr'
            },
            {
                'type': UIElementType.MINE_COUNTER,
                'selector': 'div.mines',
                'expected_size': (80, 30),
                'position_hint': 'top_left',
                'is_obstructive': False,
                'detection_method': 'template_ocr'
            }
        ]
    
    def _detect_element_type(self, screenshot: np.ndarray,
                            element_config: Dict[str, Any],
                            canvas_offset: Tuple[int, int]) -> List[UIElement]:
        """Détecte un type spécifique d'élément"""
        method = element_config.get('detection_method', 'template_color')
        
        if method == 'template_color':
            return self._detect_by_color(screenshot, element_config, canvas_offset)
        elif method == 'template_text':
            return self._detect_by_text(screenshot, element_config, canvas_offset)
        elif method == 'template_layout':
            return self._detect_by_layout(screenshot, element_config, canvas_offset)
        elif method == 'template_ocr':
            return self._detect_by_ocr(screenshot, element_config, canvas_offset)
        else:
            return []
    
    def _detect_by_color(self, screenshot: np.ndarray,
                        element_config: Dict[str, Any],
                        canvas_offset: Tuple[int, int]) -> List[UIElement]:
        """Détection par analyse de couleur"""
        elements = []
        
        # Extraire les canaux de couleur
        if len(screenshot.shape) == 3:
            blue_channel = screenshot[:, :, 2]  # Canal bleu
            
            # Appliquer les seuils de couleur
            color_range = element_config.get('color_range', [(0, 0, 0), (255, 255, 255)])
            min_color, max_color = color_range
            
            # Créer un masque pour la plage de couleurs
            color_mask = (
                (screenshot[:, :, 0] >= min_color[0]) & 
                (screenshot[:, :, 0] <= max_color[0]) &
                (screenshot[:, :, 1] >= min_color[1]) & 
                (screenshot[:, :, 1] <= max_color[1]) &
                (screenshot[:, :, 2] >= min_color[2]) & 
                (screenshot[:, :, 2] <= max_color[2])
            )
            
            # Trouver les composants connexes
            try:
                from scipy import ndimage
                # Utiliser scipy pour une meilleure détection
                labeled_array, num_features = ndimage.label(color_mask)
            except ImportError:
                # Fallback sans scipy
                import numpy as np
                # Détection simple avec numpy
                labeled_array = np.zeros_like(color_mask, dtype=int)
                current_label = 1
                for y in range(color_mask.shape[0]):
                    for x in range(color_mask.shape[1]):
                        if color_mask[y, x] and labeled_array[y, x] == 0:
                            # Simple flood fill
                            self._flood_fill(color_mask, labeled_array, x, y, current_label)
                            current_label += 1
                num_features = current_label - 1
            
            # Traiter chaque composant détecté
            for feature_id in range(1, num_features + 1):
                coords = np.where(labeled_array == feature_id)
                
                if len(coords[0]) > 0:  # Vérifier que le composant n'est pas vide
                    y_min, y_max = coords[0].min(), coords[0].max()
                    x_min, x_max = coords[1].min(), coords[1].max()
                    
                    # Calculer la confiance basée sur la taille attendue
                    expected_w, expected_h = element_config.get('expected_size', (100, 100))
                    actual_w, actual_h = x_max - x_min + 1, y_max - y_min + 1
                    
                    size_confidence = min(
                        actual_w / expected_w, expected_w / actual_w
                    ) * min(
                        actual_h / expected_h, expected_h / actual_h
                    )
                    
                    element = UIElement(
                        element_type=element_config['type'],
                        selector=element_config['selector'],
                        bounds=(x_min, y_min, actual_w, actual_h),
                        position=(x_min, y_min),
                        size=(actual_w, actual_h),
                        is_obstructive=element_config.get('is_obstructive', True),
                        confidence=min(1.0, size_confidence),
                        timestamp=time.time()
                    )
                    
                    elements.append(element)
        
        return elements
    
    def _detect_by_text(self, screenshot: np.ndarray,
                       element_config: Dict[str, Any],
                       canvas_offset: Tuple[int, int]) -> List[UIElement]:
        """Détection par reconnaissance de texte (placeholder)"""
        # Placeholder: implémentation future avec OCR
        return []
    
    def _detect_by_layout(self, screenshot: np.ndarray,
                         element_config: Dict[str, Any],
                         canvas_offset: Tuple[int, int]) -> List[UIElement]:
        """Détection par analyse de layout (placeholder)"""
        # Placeholder: implémentation future avec analyse structurelle
        return []
    
    def _detect_by_ocr(self, screenshot: np.ndarray,
                      element_config: Dict[str, Any],
                      canvas_offset: Tuple[int, int]) -> List[UIElement]:
        """Détection par OCR (placeholder)"""
        # Placeholder: implémentation future avec Tesseract
        return []
    
    def _generate_cache_key(self, shape: Tuple[int, ...], 
                           offset: Tuple[int, int]) -> str:
        """Génère une clé de cache"""
        return f"{shape[0]}x{shape[1]}_{offset[0]}_{offset[1]}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Vérifie si le cache est valide"""
        if cache_key not in self._detection_cache:
            return False
        
        cache_time = self._detection_cache[cache_key].get('timestamp', 0)
        return time.time() - cache_time < self._cache_validity
    
    def _update_cache(self, cache_key: str, shape: Tuple[int, ...],
                     offset: Tuple[int, int]) -> None:
        """Met à jour le cache"""
        self._detection_cache[cache_key] = {
            'shape': shape,
            'offset': offset,
            'timestamp': time.time(),
            'elements_count': len(self.detected_elements)
        }
    
    def _invalidate_cache(self) -> None:
        """Invalide le cache"""
        self._detection_cache.clear()
    
    def _update_stats(self, elements_count: int, detection_time: float) -> None:
        """Met à jour les statistiques"""
        self._stats['detections_performed'] += 1
        self._stats['elements_detected'] += elements_count
        
        total_detections = self._stats['detections_performed']
        current_avg = self._stats['average_detection_time']
        self._stats['average_detection_time'] = (
            (current_avg * (total_detections - 1) + detection_time) / total_detections
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du détecteur"""
        stats = self._stats.copy()
        stats.update({
            'current_elements_count': len(self.detected_elements),
            'has_mask': self.current_mask is not None,
            'cache_size': len(self._detection_cache),
            'last_detection_age': time.time() - self.last_detection_time
        })
        return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        self._stats = {
            'detections_performed': 0,
            'elements_detected': 0,
            'mask_regenerations': 0,
            'average_detection_time': 0.0
        }
    
    def clear_detection(self) -> None:
        """Efface la détection actuelle"""
        self.detected_elements.clear()
        self.current_mask = None
        self._invalidate_cache()
    
    def _flood_fill(self, mask: np.ndarray, labeled: np.ndarray, 
                   start_x: int, start_y: int, label: int) -> None:
        """
        Remplissage par diffusion simple (flood fill)
        
        Args:
            mask: Masque binaire à remplir
            labeled: Array de labels à mettre à jour
            start_x, start_y: Point de départ
            label: Label à assigner
        """
        height, width = mask.shape
        stack = [(start_x, start_y)]
        
        while stack:
            x, y = stack.pop()
            
            # Vérifier les limites
            if x < 0 or x >= width or y < 0 or y >= height:
                continue
            
            # Vérifier si le pixel est valide et non labellé
            if not mask[y, x] or labeled[y, x] != 0:
                continue
            
            # Assigner le label
            labeled[y, x] = label
            
            # Ajouter les voisins
            stack.extend([
                (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                (x + 1, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1)
            ])
