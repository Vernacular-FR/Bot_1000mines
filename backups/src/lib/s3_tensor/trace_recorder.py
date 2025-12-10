"""
TraceRecorder - Enregistrement de traces et snapshots pour replays/tests (S3)

Gère les snapshots .npz, versioning et identifiants de ticks pour:
- Debug et analyse post-mortem
- Replays déterministes
- Datasets ML futurs
- Traçabilité complète des décisions
"""

import numpy as np
import time
import threading
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import gzip
import pickle

from .tensor_grid import TensorGrid, GridBounds, CellSymbol


class TraceType(Enum):
    """Types de traces enregistrées"""
    TICK_SNAPSHOT = "tick_snapshot"
    ACTION_EXECUTED = "action_executed"
    SOLVER_STATE = "solver_state"
    VIEWPORT_CHANGE = "viewport_change"
    ERROR_EVENT = "error_event"
    SYSTEM_EVENT = "system_event"


@dataclass
class TraceEvent:
    """Événement de trace avec métadonnées complètes"""
    tick_id: int
    timestamp: float
    trace_type: TraceType
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire sérialisable"""
        return {
            'tick_id': self.tick_id,
            'timestamp': self.timestamp,
            'trace_type': self.trace_type.value,
            'data': self.data,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceEvent':
        """Crée depuis un dictionnaire"""
        return cls(
            tick_id=data['tick_id'],
            timestamp=data['timestamp'],
            trace_type=TraceType(data['trace_type']),
            data=data['data'],
            metadata=data['metadata']
        )


@dataclass
class TickSnapshot:
    """Snapshot complet de l'état à un tick donné"""
    tick_id: int
    timestamp: float
    tensor_snapshot: Dict[str, np.ndarray]  # symbols, confidence, age, frontier
    solver_state: Optional[Dict[str, Any]]
    viewport_bounds: GridBounds
    actions_pending: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class TraceRecorder:
    """
    Enregistreur de traces avec snapshots .npz compressés
    
    Fonctionnalités:
    - Snapshots automatiques à chaque tick
    - Événements de trace pour toutes les actions
    - Compression et versioning
    - Relecture et analyse
    """
    
    def __init__(self, output_dir: Path, session_id: Optional[str] = None,
                 snapshot_interval: int = 1, max_snapshots: int = 1000):
        """
        Initialise l'enregistreur de traces
        
        Args:
            output_dir: Répertoire de sortie pour les traces
            session_id: ID de session (généré si None)
            snapshot_interval: Intervale entre snapshots (en ticks)
            max_snapshots: Nombre maximum de snapshots en mémoire
        """
        self._lock = threading.RLock()
        
        # Configuration
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_interval = snapshot_interval
        self.max_snapshots = max_snapshots
        
        # Génération de l'ID de session
        if session_id is None:
            session_id = f"session_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        self.session_id = session_id
        
        # Fichiers de trace
        self.trace_file = self.output_dir / f"{self.session_id}_trace.jsonl.gz"
        self.snapshots_dir = self.output_dir / f"{self.session_id}_snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        
        # État interne
        self.current_tick = 0
        self.snapshots: Dict[int, TickSnapshot] = {}
        self.events: List[TraceEvent] = []
        self.start_time = time.time()
        
        # Statistiques
        self.stats = {
            'ticks_recorded': 0,
            'snapshots_saved': 0,
            'events_recorded': 0,
            'bytes_written': 0,
            'last_save': time.time()
        }
        
        # Fichier de métadonnées de session
        self.session_file = self.output_dir / f"{self.session_id}_session.json"
        self._save_session_metadata()
    
    def capture_tick(self, tensor_grid: TensorGrid, 
                    solver_state: Optional[Dict[str, Any]] = None,
                    viewport_bounds: Optional[GridBounds] = None,
                    actions_pending: Optional[List[Dict[str, Any]]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Capture un snapshot complet à un tick donné
        
        Args:
            tensor_grid: Grille tensorielle à capturer
            solver_state: État du solver (optionnel)
            viewport_bounds: Bornes du viewport actuel
            actions_pending: Actions en attente
            metadata: Métadonnées additionnelles
        """
        with self._lock:
            self.current_tick += 1
            current_time = time.time()
            
            # Capturer la vue solver de TensorGrid
            solver_view = tensor_grid.get_solver_view()
            
            # Créer le snapshot
            snapshot = TickSnapshot(
                tick_id=self.current_tick,
                timestamp=current_time,
                tensor_snapshot={
                    'symbols': solver_view['symbols'],
                    'confidence': solver_view['confidence'],
                    'age': solver_view['age'],
                    'frontier_mask': solver_view['frontier_mask'],
                    'global_offset': solver_view['global_offset']
                },
                solver_state=solver_state,
                viewport_bounds=viewport_bounds or tensor_grid.get_bounds(),
                actions_pending=actions_pending or [],
                metadata=metadata or {}
            )
            
            # Stocker en mémoire
            self.snapshots[self.current_tick] = snapshot
            
            # Limiter le nombre de snapshots en mémoire
            if len(self.snapshots) > self.max_snapshots:
                # Supprimer les plus anciens
                oldest_ticks = sorted(self.snapshots.keys())[:len(self.snapshots) - self.max_snapshots]
                for tick in oldest_ticks:
                    del self.snapshots[tick]
            
            # Sauvegarder si nécessaire
            if self.current_tick % self.snapshot_interval == 0:
                self._save_snapshot(snapshot)
            
            # Enregistrer l'événement de tick
            self.record_event(
                trace_type=TraceType.TICK_SNAPSHOT,
                data={
                    'tick_id': self.current_tick,
                    'grid_stats': tensor_grid.get_stats(),
                    'snapshot_saved': self.current_tick % self.snapshot_interval == 0
                },
                metadata=metadata or {}
            )
            
            self.stats['ticks_recorded'] += 1
    
    def record_event(self, trace_type: TraceType, data: Dict[str, Any],
                    metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Enregistre un événement de trace
        
        Args:
            trace_type: Type de l'événement
            data: Données de l'événement
            metadata: Métadonnées additionnelles
        """
        with self._lock:
            event = TraceEvent(
                tick_id=self.current_tick,
                timestamp=time.time(),
                trace_type=trace_type,
                data=data,
                metadata=metadata or {}
            )
            
            self.events.append(event)
            self.stats['events_recorded'] += 1
            
            # Sauvegarder périodiquement les événements
            if len(self.events) >= 100:  # Batch de 100 événements
                self._save_events()
    
    def record_action(self, action_type: str, coordinates: Tuple[int, int],
                     confidence: float, reasoning: str,
                     success: Optional[bool] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Enregistre une action exécutée
        
        Args:
            action_type: Type d'action ('reveal', 'flag', 'guess')
            coordinates: Coordonnées (x, y)
            confidence: Confiance de la décision
            reasoning: Raison de la décision
            success: Résultat (None si en attente)
            metadata: Métadonnées additionnelles
        """
        self.record_event(
            trace_type=TraceType.ACTION_EXECUTED,
            data={
                'action_type': action_type,
                'coordinates': coordinates,
                'confidence': confidence,
                'reasoning': reasoning,
                'success': success
            },
            metadata=metadata or {}
        )
    
    def record_solver_state(self, solver_type: str, components_count: int,
                           safe_cells: List[Tuple[int, int]],
                           flag_cells: List[Tuple[int, int]],
                           processing_time: float,
                           metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Enregistre l'état du solver
        
        Args:
            solver_type: Type de solver utilisé
            components_count: Nombre de composants traités
            safe_cells: Cellules identifiées comme sûres
            flag_cells: Cellules identifiées comme mines
            processing_time: Temps de traitement
            metadata: Métadonnées additionnelles
        """
        self.record_event(
            trace_type=TraceType.SOLVER_STATE,
            data={
                'solver_type': solver_type,
                'components_count': components_count,
                'safe_cells_count': len(safe_cells),
                'flag_cells_count': len(flag_cells),
                'safe_cells': safe_cells,
                'flag_cells': flag_cells,
                'processing_time': processing_time
            },
            metadata=metadata or {}
        )
    
    def record_viewport_change(self, old_bounds: GridBounds, new_bounds: GridBounds,
                              movement_vector: Tuple[int, int],
                              metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Enregistre un changement de viewport
        
        Args:
            old_bounds: Anciennes bornes du viewport
            new_bounds: Nouvelles bornes du viewport
            movement_vector: Vecteur de mouvement (dx, dy)
            metadata: Métadonnées additionnelles
        """
        self.record_event(
            trace_type=TraceType.VIEWPORT_CHANGE,
            data={
                'old_bounds': asdict(old_bounds),
                'new_bounds': asdict(new_bounds),
                'movement_vector': movement_vector
            },
            metadata=metadata or {}
        )
    
    def record_error(self, error_type: str, error_message: str,
                    context: Dict[str, Any],
                    metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Enregistre une erreur
        
        Args:
            error_type: Type d'erreur
            error_message: Message d'erreur
            context: Contexte de l'erreur
            metadata: Métadonnées additionnelles
        """
        self.record_event(
            trace_type=TraceType.ERROR_EVENT,
            data={
                'error_type': error_type,
                'error_message': error_message,
                'context': context
            },
            metadata=metadata or {}
        )
    
    def _save_snapshot(self, snapshot: TickSnapshot) -> None:
        """Sauvegarde un snapshot sur disque"""
        try:
            snapshot_file = self.snapshots_dir / f"tick_{snapshot.tick_id:06d}.npz"
            
            # Préparer les données pour NPZ
            npz_data = {}
            for key, value in snapshot.tensor_snapshot.items():
                if isinstance(value, np.ndarray):
                    npz_data[key] = value
                else:
                    # Pour les métadonnées non-array
                    npz_data[f"meta_{key}"] = str(value)
            
            # Ajouter les métadonnées du snapshot
            metadata_dict = {
                'tick_id': snapshot.tick_id,
                'timestamp': snapshot.timestamp,
                'solver_state': snapshot.solver_state,
                'viewport_bounds': asdict(snapshot.viewport_bounds),
                'actions_pending': snapshot.actions_pending,
                'metadata': snapshot.metadata
            }
            npz_data['snapshot_metadata'] = json.dumps(metadata_dict)
            
            # Sauvegarder en NPZ compressé
            np.savez_compressed(snapshot_file, **npz_data)
            
            self.stats['snapshots_saved'] += 1
            self.stats['bytes_written'] += snapshot_file.stat().st_size
            
        except Exception as e:
            # Logger l'erreur mais ne pas interrompre le flux
            print(f"Erreur sauvegarde snapshot {snapshot.tick_id}: {e}")
    
    def _save_events(self) -> None:
        """Sauvegarde les événements en attente sur disque"""
        if not self.events:
            return
        
        try:
            with gzip.open(self.trace_file, 'at', encoding='utf-8') as f:
                for event in self.events:
                    f.write(json.dumps(event.to_dict()) + '\n')
            
            self.stats['bytes_written'] += self.trace_file.stat().st_size
            self.events.clear()
            self.stats['last_save'] = time.time()
            
        except Exception as e:
            print(f"Erreur sauvegarde événements: {e}")
    
    def _save_session_metadata(self) -> None:
        """Sauvegarde les métadonnées de la session"""
        metadata = {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'snapshot_interval': self.snapshot_interval,
            'max_snapshots': self.max_snapshots,
            'output_dir': str(self.output_dir),
            'trace_file': str(self.trace_file),
            'snapshots_dir': str(self.snapshots_dir)
        }
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
    
    def finalize(self) -> None:
        """Finalise l'enregistrement et sauvegarde tout"""
        with self._lock:
            # Sauvegarder les événements restants
            self._save_events()
            
            # Sauvegarder tous les snapshots en mémoire
            for snapshot in self.snapshots.values():
                self._save_snapshot(snapshot)
            
            # Mettre à jour les métadonnées finales
            final_metadata = {
                'session_id': self.session_id,
                'start_time': self.start_time,
                'end_time': time.time(),
                'total_ticks': self.current_tick,
                'stats': self.stats
            }
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(final_metadata, f, indent=2)
    
    def load_snapshot(self, tick_id: int) -> Optional[TickSnapshot]:
        """
        Charge un snapshot depuis le disque
        
        Args:
            tick_id: ID du tick à charger
            
        Returns:
            Snapshot chargé ou None si introuvable
        """
        try:
            snapshot_file = self.snapshots_dir / f"tick_{tick_id:06d}.npz"
            if not snapshot_file.exists():
                return None
            
            # Charger NPZ
            npz_data = np.load(snapshot_file, allow_pickle=True)
            
            # Reconstruire les données
            tensor_snapshot = {}
            for key in npz_data.files:
                if key.startswith('meta_'):
                    continue
                if key == 'snapshot_metadata':
                    continue
                tensor_snapshot[key] = npz_data[key]
            
            # Extraire les métadonnées
            metadata_dict = json.loads(npz_data['snapshot_metadata'].item())
            
            return TickSnapshot(
                tick_id=metadata_dict['tick_id'],
                timestamp=metadata_dict['timestamp'],
                tensor_snapshot=tensor_snapshot,
                solver_state=metadata_dict['solver_state'],
                viewport_bounds=GridBounds(**metadata_dict['viewport_bounds']),
                actions_pending=metadata_dict['actions_pending'],
                metadata=metadata_dict['metadata']
            )
            
        except Exception as e:
            print(f"Erreur chargement snapshot {tick_id}: {e}")
            return None
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Retourne un résumé complet de la session"""
        with self._lock:
            duration = time.time() - self.start_time
            
            return {
                'session_id': self.session_id,
                'duration_seconds': duration,
                'current_tick': self.current_tick,
                'ticks_per_second': self.current_tick / duration if duration > 0 else 0,
                'snapshots_in_memory': len(self.snapshots),
                'events_pending': len(self.events),
                'stats': self.stats,
                'files': {
                    'trace_file': str(self.trace_file),
                    'snapshots_dir': str(self.snapshots_dir),
                    'session_file': str(self.session_file)
                }
            }
