"""Exécuteur d'actions via JavaScript."""

import time
from typing import Optional, Dict, Any

from selenium.webdriver.remote.webdriver import WebDriver

from src.lib.s4_solver.types import ActionType
from src.lib.s5_planner.types import PlannedAction
from .types import ExecutorInput, ExecutionResult


class Executor:
    """Exécuteur d'actions via le navigateur."""

    # Script JS pour les clics
    CLICK_SCRIPT = """
    const x = arguments[0];
    const y = arguments[1];
    const button = arguments[2];
    
    const element = document.elementFromPoint(x, y);
    if (!element) return { success: false, error: 'No element at point' };
    
    const event = new MouseEvent(button === 2 ? 'contextmenu' : 'click', {
        bubbles: true,
        cancelable: true,
        view: window,
        clientX: x,
        clientY: y,
        button: button
    });
    element.dispatchEvent(event);
    return { success: true };
    """

    def __init__(self, driver: WebDriver = None):
        self.driver = driver
        self.click_delay = 0.01  # 10ms entre les clics

    def set_driver(self, driver: WebDriver) -> None:
        """Configure le driver."""
        self.driver = driver

    def execute(self, input: ExecutorInput) -> ExecutionResult:
        """Exécute un plan d'actions."""
        if not input.plan.has_actions:
            return ExecutionResult(success=True, executed_count=0, duration=0.0)

        driver = input.driver or self.driver
        if not driver:
            return ExecutionResult(
                success=False,
                executed_count=0,
                errors=["Driver non configuré"],
            )

        start_time = time.time()
        executed = 0
        errors = []

        for action in input.plan.actions:
            try:
                success = self._execute_action(driver, action)
                if success:
                    executed += 1
                else:
                    errors.append(f"Action failed at {action.coord}")
                
                if self.click_delay > 0:
                    time.sleep(self.click_delay)
                    
            except Exception as e:
                errors.append(f"Error at {action.coord}: {str(e)}")

        duration = time.time() - start_time

        return ExecutionResult(
            success=len(errors) == 0,
            executed_count=executed,
            errors=errors,
            duration=duration,
            metadata={
                "total_planned": input.plan.action_count,
                "click_delay": self.click_delay,
            },
        )

    def _execute_action(self, driver: WebDriver, action: PlannedAction) -> bool:
        """Exécute une action individuelle."""
        x = action.screen_point.x
        y = action.screen_point.y
        
        # Bouton: 0=gauche (click), 2=droit (flag)
        button = 2 if action.action == ActionType.FLAG else 0

        result = driver.execute_script(self.CLICK_SCRIPT, x, y, button)
        
        if isinstance(result, dict):
            return result.get("success", False)
        return False


# === API fonctionnelle ===

_default_executor: Optional[Executor] = None


def _get_executor() -> Executor:
    global _default_executor
    if _default_executor is None:
        _default_executor = Executor()
    return _default_executor


def set_executor_driver(driver: WebDriver) -> None:
    """Configure le driver pour l'exécuteur par défaut."""
    _get_executor().set_driver(driver)


def execute(input: ExecutorInput) -> ExecutionResult:
    """Exécute un plan d'actions."""
    return _get_executor().execute(input)
