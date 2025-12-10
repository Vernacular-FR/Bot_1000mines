"""
S1 Capture - Déclenchement et segmentation d'images (S1)

Interface publique pour la couche de capture:
- CaptureTrigger: Déclenchement intelligent des captures
- PatchSegmenter: Segmentation alignée sur viewport_bounds
- MetadataExtractor: Extraction des métadonnées de cellules
"""

from .s11_capture_trigger import (
    CaptureTrigger, TriggerType, CaptureRequest, CaptureResult
)
from .s12_patch_segmenter import (
    PatchSegmenter, PatchType, ImagePatch, SegmentationResult
)
from .s13_metadata_extractor import (
    MetadataExtractor, MetadataType, CellMetadata, ExtractionResult
)

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'CaptureTrigger',
    'PatchSegmenter', 
    'MetadataExtractor',
    
    # Types et énumérations
    'TriggerType',
    'PatchType',
    'MetadataType',
    
    # Structures de données
    'CaptureRequest',
    'CaptureResult',
    'ImagePatch',
    'SegmentationResult',
    'CellMetadata',
    'ExtractionResult',
]
