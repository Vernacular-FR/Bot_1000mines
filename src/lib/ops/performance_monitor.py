import time
import psutil
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import os

# Ajout du chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Logs.logger import save_extraction_log

@dataclass
class PerformanceMetric:
    """Métrique de performance individuelle"""
    timestamp: str
    metric_name: str
    value: float
    unit: str
    context: Dict[str, Any]

@dataclass
class SystemMetrics:
    """Métriques système complètes"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    active_threads: int
    timestamp: str

class PerformanceMonitor:
    """Moniteur de performance avancé pour le bot démineur"""
    
    def __init__(self, log_interval: int = 5):
        self.log_interval = log_interval
        self.metrics: List[PerformanceMetric] = []
        self.system_metrics: List[SystemMetrics] = []
        self.start_time = datetime.now()
        self.monitoring = False
        self.monitor_thread = None
        self.performance_data = {}
        
        # Créer le dossier de monitoring
        self.monitoring_dir = Path("monitoring")
        self.monitoring_dir.mkdir(exist_ok=True)
        
    def start_monitoring(self):
        """Démarrer le monitoring en arrière-plan"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"Monitoring démarré - Intervalle: {self.log_interval}s")
        
    def stop_monitoring(self):
        """Arrêter le monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        # Sauvegarder les métriques finales
        self._save_metrics()
        print("Monitoring arrêté et métriques sauvegardées")
        
    def _monitor_loop(self):
        """Boucle de monitoring en arrière-plan"""
        while self.monitoring:
            try:
                # Collecter les métriques système
                system_metrics = self._collect_system_metrics()
                self.system_metrics.append(system_metrics)
                
                # Vérifier l'utilisation mémoire
                if system_metrics.memory_percent > 80:
                    self._log_warning("Mémoire élevée", system_metrics.memory_percent)
                    
                if system_metrics.cpu_percent > 90:
                    self._log_warning("CPU élevé", system_metrics.cpu_percent)
                    
            except Exception as e:
                print(f"Erreur monitoring: {e}")
                
            time.sleep(self.log_interval)
            
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collecter les métriques système"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            memory_available_mb=memory.available / 1024 / 1024,
            disk_usage_percent=disk.percent,
            active_threads=threading.active_count(),
            timestamp=datetime.now().isoformat()
        )
        
    def record_metric(self, name: str, value: float, unit: str, context: Dict[str, Any] = None):
        """Enregistrer une métrique personnalisée"""
        metric = PerformanceMetric(
            timestamp=datetime.now().isoformat(),
            metric_name=name,
            value=value,
            unit=unit,
            context=context or {}
        )
        self.metrics.append(metric)
        
    def measure_function_performance(self, func_name: str):
        """Context manager pour mesurer la performance d'une fonction"""
        return FunctionPerformanceMeasurer(self, func_name)
        
    def _log_warning(self, message: str, value: float):
        """Logger un avertissement de performance"""
        warning_data = {
            "timestamp": datetime.now().isoformat(),
            "type": "performance_warning",
            "message": message,
            "value": value,
            "threshold": "high"
        }
        
        # Sauvegarder dans les logs d'extraction
        save_extraction_log("performance_warning", warning_data, False)
        
    def _save_metrics(self):
        """Sauvegarder toutes les métriques"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder les métriques système
        system_file = self.monitoring_dir / f"system_metrics_{timestamp}.json"
        with open(system_file, 'w', encoding='utf-8') as f:
            json.dump(
                [asdict(metric) for metric in self.system_metrics],
                f, 
                indent=2,
                ensure_ascii=False
            )
            
        # Sauvegarder les métriques personnalisées
        custom_file = self.monitoring_dir / f"custom_metrics_{timestamp}.json"
        with open(custom_file, 'w', encoding='utf-8') as f:
            json.dump(
                [asdict(metric) for metric in self.metrics],
                f,
                indent=2,
                ensure_ascii=False
            )
            
        # Générer le rapport de performance
        self._generate_performance_report(timestamp)
        
    def _generate_performance_report(self, timestamp: str):
        """Générer un rapport de performance détaillé"""
        if not self.system_metrics:
            return
            
        # Calculer les statistiques
        cpu_values = [m.cpu_percent for m in self.system_metrics]
        memory_values = [m.memory_percent for m in self.system_metrics]
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "monitoring_period": {
                "start": self.start_time.isoformat(),
                "end": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.start_time).total_seconds()
            },
            "system_performance": {
                "cpu": {
                    "average": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values)
                },
                "memory": {
                    "average": sum(memory_values) / len(memory_values),
                    "max": max(memory_values),
                    "min": min(memory_values)
                }
            },
            "custom_metrics_count": len(self.metrics),
            "warnings_count": len([m for m in self.system_metrics if m.cpu_percent > 90 or m.memory_percent > 80]),
            "performance_issues": self._detect_performance_issues()
        }
        
        # Sauvegarder le rapport
        report_file = self.monitoring_dir / f"performance_report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        print(f"Rapport de performance généré: {report_file}")
        
    def _detect_performance_issues(self) -> List[str]:
        """Détecter les problèmes de performance"""
        issues = []
        
        if not self.system_metrics:
            return issues
            
        # Vérifier l'utilisation CPU moyenne
        avg_cpu = sum(m.cpu_percent for m in self.system_metrics) / len(self.system_metrics)
        if avg_cpu > 70:
            issues.append("CPU usage consistently high")
            
        # Vérifier l'utilisation mémoire moyenne
        avg_memory = sum(m.memory_percent for m in self.system_metrics) / len(self.system_metrics)
        if avg_memory > 70:
            issues.append("Memory usage consistently high")
            
        # Vérifier les pics
        max_memory = max(m.memory_percent for m in self.system_metrics)
        if max_memory > 90:
            issues.append("Memory spikes detected")
            
        return issues
        
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Obtenir les métriques système actuelles"""
        return self._collect_system_metrics()

class FunctionPerformanceMeasurer:
    """Context manager pour mesurer la performance des fonctions"""
    
    def __init__(self, monitor: PerformanceMonitor, func_name: str):
        self.monitor = monitor
        self.func_name = func_name
        self.start_time = None
        self.end_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        # Enregistrer la métrique
        self.monitor.record_metric(
            name=f"function_duration_{self.func_name}",
            value=duration,
            unit="seconds",
            context={
                "function": self.func_name,
                "success": exc_type is None
            }
        )
        
        # Logger si la fonction est lente
        if duration > 5.0:
            self.monitor._log_warning(f"Fonction lente: {self.func_name}", duration)

# Instance globale du moniteur
_global_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Obtenir l'instance globale du moniteur de performance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor

def start_global_monitoring():
    """Démarrer le monitoring global"""
    monitor = get_performance_monitor()
    monitor.start_monitoring()

def stop_global_monitoring():
    """Arrêter le monitoring global"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring()

def measure_performance(func_name: str):
    """Décorateur pour mesurer la performance d'une fonction"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            with monitor.measure_function_performance(func_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
