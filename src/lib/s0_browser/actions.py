"""Actions de bas niveau via JavaScript."""

from __future__ import annotations
from selenium.webdriver.remote.webdriver import WebDriver

def click_left(driver: WebDriver, rel_x: float, rel_y: float) -> bool:
    """Simule un clic gauche (double-clic) via JS à une position relative à l'anchor."""
    script = """
    const relX = arguments[0];
    const relY = arguments[1];
    const anchor = document.querySelector('#anchor');
    if (!anchor) return false;
    
    const rect = anchor.getBoundingClientRect();
    const x = rect.left + relX;
    const y = rect.top + relY;
    
    const target = document.elementFromPoint(x, y) || document.querySelector('div#control');
    
    function makeMouse(type, x, y) {
        return new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
            button: 0
        });
    }

    target.dispatchEvent(makeMouse('mousedown', x, y));
    target.dispatchEvent(makeMouse('mouseup', x, y));
    target.dispatchEvent(makeMouse('click', x, y));
    target.dispatchEvent(makeMouse('mousedown', x, y));
    target.dispatchEvent(makeMouse('mouseup', x, y));
    target.dispatchEvent(makeMouse('click', x, y));
    target.dispatchEvent(makeMouse('dblclick', x, y));
    return true;
    """
    try:
        return driver.execute_script(script, rel_x, rel_y)
    except Exception as e:
        print(f"[BROWSER] Erreur click_left: {e}")
        return False


def click_right(driver: WebDriver, rel_x: float, rel_y: float) -> bool:
    """Simule un clic droit (drapeau) via JS à une position relative à l'anchor."""
    script = """
    const relX = arguments[0];
    const relY = arguments[1];
    const anchor = document.querySelector('#anchor');
    if (!anchor) return false;
    
    const rect = anchor.getBoundingClientRect();
    const x = rect.left + relX;
    const y = rect.top + relY;
    
    const target = document.elementFromPoint(x, y) || document.querySelector('div#control');
    
    function makeMouse(type, x, y) {
        return new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
            button: 2
        });
    }

    target.dispatchEvent(makeMouse('mousedown', x, y));
    target.dispatchEvent(makeMouse('mouseup', x, y));
    target.dispatchEvent(makeMouse('contextmenu', x, y));
    return true;
    """
    try:
        return driver.execute_script(script, rel_x, rel_y)
    except Exception as e:
        print(f"[BROWSER] Erreur click_right: {e}")
        return False
