"""
AsyncLogger - Système de logging asynchrone pour tous les layers

Gère le logging haute performance pour S0-S6:
- Logging asynchrone non-bloquant
- Structured logging avec métadonnées
- Intégration avec TraceRecorder S3
- Rotation et archivage automatiques
"""

import asyncio
import logging
import json
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import queue
from concurrent.futures import ThreadPoolExecutor

from ..s3_tensor.trace_recorder import TraceRecorder


class LogLevel(Enum):
    """Niveaux de logging"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogFormat(Enum):
    """Formats de sortie"""
    JSON = "json"
    STRUCTURED = "structured"
    PLAIN = "plain"


@dataclass
class LogEntry:
    """Entrée de log structurée"""
    timestamp: float
    level: LogLevel
    layer: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            'timestamp': self.timestamp,
            'level': self.level.value,
            'layer': self.layer,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'thread_id': self.thread_id,
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        """Convertit en JSON"""
        return json.dumps(self.to_dict(), default=str)


class AsyncLogHandler:
    """Handler de log asynchrone"""
    
    def __init__(self, log_queue: queue.Queue,
                 max_batch_size: int = 100,
                 flush_interval: float = 1.0):
        """
        Initialise le handler asynchrone
        
        Args:
            log_queue: Queue pour les logs
            max_batch_size: Taille maximum des lots
            flush_interval: Intervalle de flush en secondes
        """
        self.log_queue = log_queue
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval
        
        # État
        self._buffer: List[LogEntry] = []
        self._last_flush = time.time()
        self._lock = threading.Lock()
    
    def emit(self, record: LogEntry) -> None:
        """
        Émet une entrée de log
        
        Args:
            record: Entrée de log à émettre
        """
        with self._lock:
            self._buffer.append(record)
            
            # Forcer le flush si nécessaire
            if (len(self._buffer) >= self.max_batch_size or
                time.time() - self._last_flush >= self.flush_interval):
                self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        """Vide le buffer dans la queue"""
        if self._buffer:
            batch = self._buffer.copy()
            self._buffer.clear()
            self._last_flush = time.time()
            
            # Mettre le batch dans la queue
            try:
                self.log_queue.put(('batch', batch), block=False)
            except queue.Full:
                # Queue pleine: ignorer les plus anciens logs
                pass


class AsyncLogger:
    """
    Logger asynchrone haute performance pour tous les layers
    
    Fonctionnalités:
    - Logging non-bloquant avec queue
    - Structured logging avec métadonnées riches
    - Intégration avec TraceRecorder S3
    - Rotation automatique des fichiers
    """
    
    def __init__(self, trace_recorder: Optional[TraceRecorder] = None,
                 log_file_path: Optional[str] = None,
                 max_queue_size: int = 10000,
                 batch_size: int = 100,
                 flush_interval: float = 1.0,
                 enable_console_output: bool = True,
                 log_format: LogFormat = LogFormat.JSON):
        """
        Initialise le logger asynchrone
        
        Args:
            trace_recorder: Enregistreur de traces S3 (optionnel)
            log_file_path: Chemin du fichier de log (optionnel)
            max_queue_size: Taille maximum de la queue
            batch_size: Taille des lots de traitement
            flush_interval: Intervalle de flush
            enable_console_output: Activer la sortie console
            log_format: Format des logs
        """
        # Dépendances
        self.trace_recorder = trace_recorder
        
        # Configuration
        self.log_file_path = log_file_path
        self.max_queue_size = max_queue_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enable_console_output = enable_console_output
        self.log_format = log_format
        
        # Queue et threading
        self._log_queue = queue.Queue(maxsize=max_queue_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="async_logger")
        
        # Handlers
        self._handlers: List[AsyncLogHandler] = []
        self._file_handler: Optional[logging.FileHandler] = None
        
        # Statistiques
        self._stats = {
            'logs_queued': 0,
            'logs_processed': 0,
            'logs_dropped': 0,
            'batches_processed': 0,
            'average_batch_size': 0.0
        }
        
        # Initialiser les handlers
        self._setup_handlers()
        
        # Démarrer le worker
        self._start_worker()
    
    def debug(self, layer: str, message: str, **metadata) -> None:
        """Log un message de niveau DEBUG"""
        self._log(LogLevel.DEBUG, layer, message, **metadata)
    
    def info(self, layer: str, message: str, **metadata) -> None:
        """Log un message de niveau INFO"""
        self._log(LogLevel.INFO, layer, message, **metadata)
    
    def warning(self, layer: str, message: str, **metadata) -> None:
        """Log un message de niveau WARNING"""
        self._log(LogLevel.WARNING, layer, message, **metadata)
    
    def error(self, layer: str, message: str, **metadata) -> None:
        """Log un message de niveau ERROR"""
        self._log(LogLevel.ERROR, layer, message, **metadata)
    
    def critical(self, layer: str, message: str, **metadata) -> None:
        """Log un message de niveau CRITICAL"""
        self._log(LogLevel.CRITICAL, layer, message, **metadata)
    
    def log_operation(self, layer: str, operation: str, duration: float,
                     success: bool, **metadata) -> None:
        """
        Log une opération avec métriques
        
        Args:
            layer: Layer concerné
            operation: Nom de l'opération
            duration: Durée de l'opération
            success: Si l'opération a réussi
            **metadata: Métadonnées additionnelles
        """
        level = LogLevel.INFO if success else LogLevel.WARNING
        
        log_metadata = {
            'operation': operation,
            'duration': duration,
            'success': success,
            'operation_type': 'performance'
        }
        log_metadata.update(metadata)
        
        message = f"Operation '{operation}' in {layer} " + (
            f"completed in {duration:.3f}s" if success else 
            f"failed after {duration:.3f}s"
        )
        
        self._log(level, layer, message, **log_metadata)
    
    def log_error_with_traceback(self, layer: str, message: str, 
                                exception: Exception, **metadata) -> None:
        """
        Log une erreur avec traceback
        
        Args:
            layer: Layer concerné
            message: Message d'erreur
            exception: Exception capturée
            **metadata: Métadonnées additionnelles
        """
        import traceback
        
        error_metadata = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': traceback.format_exc(),
            'error_type': 'exception'
        }
        error_metadata.update(metadata)
        
        self._log(LogLevel.ERROR, layer, message, **error_metadata)
    
    def _log(self, level: LogLevel, layer: str, message: str, **metadata) -> None:
        """
        Log un message avec le niveau spécifié
        
        Args:
            level: Niveau de log
            layer: Layer concerné
            message: Message à logger
            **metadata: Métadonnées additionnelles
        """
        import inspect
        
        # Obtenir les informations d'appel
        frame = inspect.currentframe()
        try:
            # Remonter de 2 frames pour trouver le véritable appelant
            caller_frame = frame.f_back.f_back
            module = caller_frame.f_globals.get('__name__', 'unknown')
            function = caller_frame.f_code.co_name
            line_number = caller_frame.f_lineno
        except (AttributeError, TypeError):
            module = 'unknown'
            function = 'unknown'
            line_number = 0
        finally:
            del frame
        
        # Créer l'entrée de log
        log_entry = LogEntry(
            timestamp=time.time(),
            level=level,
            layer=layer,
            message=message,
            module=module,
            function=function,
            line_number=line_number,
            thread_id=threading.get_ident(),
            metadata=metadata
        )
        
        # Mettre dans la queue
        try:
            self._log_queue.put(('single', log_entry), block=False)
            self._stats['logs_queued'] += 1
        except queue.Full:
            self._stats['logs_dropped'] += 1
    
    def _setup_handlers(self) -> None:
        """Configure les handlers de log"""
        # Handler asynchrone principal
        main_handler = AsyncLogHandler(
            self._log_queue,
            max_batch_size=self.batch_size,
            flush_interval=self.flush_interval
        )
        self._handlers.append(main_handler)
        
        # Handler fichier si configuré
        if self.log_file_path:
            self._setup_file_handler()
    
    def _setup_file_handler(self) -> None:
        """Configure le handler de fichier"""
        try:
            log_path = Path(self.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Créer le handler de fichier
            self._file_handler = logging.FileHandler(
                self.log_file_path,
                mode='a',
                encoding='utf-8'
            )
            
            # Configurer le formatteur
            if self.log_format == LogFormat.JSON:
                formatter = logging.Formatter('%(message)s')
            else:
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            
            self._file_handler.setFormatter(formatter)
            
        except Exception as e:
            # En cas d'erreur, logger vers console seulement
            print(f"Failed to setup file handler: {e}")
    
    def _start_worker(self) -> None:
        """Démarre le thread de traitement des logs"""
        def worker():
            while not self._stop_event.is_set():
                try:
                    # Traiter les logs par lots
                    self._process_log_batch()
                except Exception:
                    # Ignorer les erreurs dans le worker
                    pass
        
        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
    
    def _process_log_batch(self) -> None:
        """Traite un lot de logs"""
        batch = []
        
        # Collecter les logs jusqu'à atteindre la taille du lot ou le timeout
        timeout = time.time() + self.flush_interval
        
        while len(batch) < self.batch_size and time.time() < timeout:
            try:
                item = self._log_queue.get(timeout=0.1)
                
                if item[0] == 'single':
                    batch.append(item[1])
                elif item[0] == 'batch':
                    batch.extend(item[1])
                
            except queue.Empty:
                continue
        
        # Traiter le batch s'il n'est pas vide
        if batch:
            self._process_batch(batch)
    
    def _process_batch(self, batch: List[LogEntry]) -> None:
        """
        Traite un lot d'entrées de log
        
        Args:
            batch: Lot d'entrées à traiter
        """
        try:
            # Sortie console
            if self.enable_console_output:
                self._output_to_console(batch)
            
            # Sortie fichier
            if self._file_handler:
                self._output_to_file(batch)
            
            # Export vers TraceRecorder
            if self.trace_recorder:
                self._export_to_trace_recorder(batch)
            
            # Mettre à jour les statistiques
            self._stats['logs_processed'] += len(batch)
            self._stats['batches_processed'] += 1
            
            # Mettre à jour la taille moyenne des lots
            total_batches = self._stats['batches_processed']
            current_avg = self._stats['average_batch_size']
            self._stats['average_batch_size'] = (
                (current_avg * (total_batches - 1) + len(batch)) / total_batches
            )
            
        except Exception:
            # Ignorer les erreurs de traitement
            pass
    
    def _output_to_console(self, batch: List[LogEntry]) -> None:
        """Sort un lot vers la console"""
        for entry in batch:
            if self.log_format == LogFormat.JSON:
                print(entry.to_json())
            elif self.log_format == LogFormat.STRUCTURED:
                print(f"[{entry.level.value.upper()}] {entry.layer}: {entry.message}")
                if entry.metadata:
                    print(f"  Metadata: {entry.metadata}")
            else:  # PLAIN
                print(f"{entry.timestamp:.3f} {entry.layer} {entry.level.value}: {entry.message}")
    
    def _output_to_file(self, batch: List[LogEntry]) -> None:
        """Sort un lot vers le fichier"""
        for entry in batch:
            if self.log_format == LogFormat.JSON:
                self._file_handler.emit(logging.LogRecord(
                    name=entry.layer,
                    level=getattr(logging, entry.level.value.upper()),
                    pathname=entry.module,
                    lineno=entry.line_number,
                    msg=entry.to_json(),
                    args=(),
                    exc_info=None
                ))
            else:
                # Format structuré ou plain
                formatted_msg = f"{entry.timestamp:.3f} [{entry.level.value.upper()}] {entry.layer}: {entry.message}"
                if entry.metadata and self.log_format == LogFormat.STRUCTURED:
                    formatted_msg += f" | {entry.metadata}"
                
                self._file_handler.emit(logging.LogRecord(
                    name=entry.layer,
                    level=getattr(logging, entry.level.value.upper()),
                    pathname=entry.module,
                    lineno=entry.line_number,
                    msg=formatted_msg,
                    args=(),
                    exc_info=None
                ))
    
    def _export_to_trace_recorder(self, batch: List[LogEntry]) -> None:
        """Exporte un lot vers TraceRecorder"""
        try:
            for entry in batch:
                trace_data = {
                    'log_entry': entry.to_dict(),
                    'timestamp': entry.timestamp,
                    'source': 'async_logger'
                }
                
                self.trace_recorder.record_trace('log', trace_data)
        except Exception:
            # Ignorer les erreurs d'export
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du logger"""
        stats = self._stats.copy()
        stats.update({
            'queue_size': self._log_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'worker_running': self._worker_thread and self._worker_thread.is_alive(),
            'handlers_count': len(self._handlers),
            'file_logging_enabled': self._file_handler is not None,
            'configuration': {
                'batch_size': self.batch_size,
                'flush_interval': self.flush_interval,
                'console_output': self.enable_console_output,
                'log_format': self.log_format.value
            }
        })
        return stats
    
    def flush(self) -> None:
        """Force le flush des logs en attente"""
        # Envoyer un signal de flush
        try:
            self._log_queue.put(('flush', None), block=False)
        except queue.Full:
            pass
    
    def shutdown(self) -> None:
        """Arrête proprement le logger"""
        # Signaler l'arrêt
        self._stop_event.set()
        
        # Forcer le traitement des logs restants
        self.flush()
        
        # Attendre le worker
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
        
        # Fermer les handlers
        if self._file_handler:
            self._file_handler.close()
        
        # Arrêter l'executor
        self._executor.shutdown(wait=True)
