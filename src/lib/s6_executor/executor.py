"""Exécution des actions via JavaScript."""

from __future__ import annotations

import time
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

from src.lib.s0_coordinates import CoordinateConverter
from src.lib.s4_solver.types import ActionType
from src.lib.s5_planner.types import ExecutionPlan, PlannedAction
from .types import ExecutorInput, ExecutionResult


class Executor:
    """Exécute les actions planifiées via JavaScript."""

    def __init__(self, driver: WebDriver, converter: Optional[CoordinateConverter] = None):
        self.driver = driver
        self.converter = converter or CoordinateConverter()
        self.converter.set_driver(driver)

    def execute_action(self, action: PlannedAction) -> bool:
        """Exécute une action unique."""
        try:
            col, row = action.coord  # coord est (col, row) comme dans le legacy

            screen_x, screen_y = self.converter.grid_to_screen_centered(row, col)

            if action.action == ActionType.FLAG:
                result = self._click_right(screen_x, screen_y)
            else:
                result = self._click_left(screen_x, screen_y)

            print(f"[EXECUTOR] {action.action.name} at (col={col}, row={row}) -> {result}")
            return result
        except Exception as e:
            print(f"[EXECUTOR] Erreur action {action.coord}: {e}")
            return False

    def _click_left(self, screen_x: float, screen_y: float) -> bool:
        """Clic gauche simulé en double-clic (2x mousedown/up + dblclick)."""
        script = """
        const x = Math.round(arguments[0]);
        const y = Math.round(arguments[1]);
        
        // Essayer de trouver le canvas dans div#control d'abord, puis div#control
        let target = null;
        try {
            target = document.querySelector('div#control canvas');
        } catch(e) {}
        
        if (!target) {
            target = document.querySelector('div#control');
        }
        
        if (!target) {
            console.log('Target non trouvé!');
            return false;
        }
        
        function makeMouse(type, x, y, button=0) {
            return new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: x,
                clientY: y,
                button: button
            });
        }
        
        // Séquence double-clic : move + (down/up/click) x2 + dblclick
        target.dispatchEvent(makeMouse('mousemove', x, y));
        target.dispatchEvent(makeMouse('mousedown', x, y));
        target.dispatchEvent(makeMouse('mouseup', x, y));
        target.dispatchEvent(makeMouse('click', x, y));
        target.dispatchEvent(makeMouse('mousedown', x, y));
        target.dispatchEvent(makeMouse('mouseup', x, y));
        target.dispatchEvent(makeMouse('click', x, y));
        target.dispatchEvent(makeMouse('dblclick', x, y));
        
        return true;
        """
        result = self.driver.execute_script(script, screen_x, screen_y)
        return bool(result)

    def _click_right(self, screen_x: float, screen_y: float) -> bool:
        """Clic droit via JavaScript."""
        script = """
        const x = arguments[0];
        const y = arguments[1];
        const element = document.elementFromPoint(x, y);
        if (element) {
            const event = new MouseEvent('contextmenu', {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: x,
                clientY: y,
                button: 2
            });
            element.dispatchEvent(event);
            return true;
        }
        return false;
        """
        return bool(self.driver.execute_script(script, screen_x, screen_y))

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """Exécute un plan complet."""
        start_time = time.time()
        executed = 0
        errors = []

        for action in plan.actions:
            if self.execute_action(action):
                executed += 1
            else:
                errors.append(f"Failed: {action.coord}")

        return ExecutionResult(
            success=len(errors) == 0,
            executed_count=executed,
            errors=errors,
            duration=time.time() - start_time,
        )


def execute(input: ExecutorInput) -> ExecutionResult:
    """Point d'entrée principal pour l'exécution."""
    executor = Executor(input.driver)
    return executor.execute_plan(input.plan)
