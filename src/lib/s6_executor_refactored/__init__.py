"""Module s6_executor : Exécution des actions via le navigateur."""

from .types import ExecutorInput, ExecutionResult
from .executor import execute, Executor

__all__ = [
    "ExecutorInput",
    "ExecutionResult",
    "execute",
    "Executor",
]
