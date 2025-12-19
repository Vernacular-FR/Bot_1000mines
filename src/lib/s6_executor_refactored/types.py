"""Types pour le module s6_executor."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from selenium.webdriver.remote.webdriver import WebDriver

from src.lib.s5_planner.types import ExecutionPlan


@dataclass
class ExecutorInput:
    """Input pour l'exécuteur."""
    plan: ExecutionPlan
    driver: WebDriver
    config: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionResult:
    """Résultat de l'exécution."""
    success: bool
    executed_count: int
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def actions_per_second(self) -> float:
        if self.duration <= 0:
            return 0.0
        return self.executed_count / self.duration
