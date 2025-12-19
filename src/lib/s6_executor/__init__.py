"""Module s6_executor : Exécution des actions."""

from .types import ExecutorInput, ExecutionResult
from .executor import Executor, execute

__all__ = [
    "ExecutorInput",
    "ExecutionResult",
    "Executor",
    "execute",
]
