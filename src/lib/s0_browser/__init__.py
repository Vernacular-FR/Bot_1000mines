"""Module s0_browser : Gestion du navigateur Selenium."""

from .browser import BrowserManager, start_browser, stop_browser, navigate_to
from .types import BrowserConfig, BrowserHandle

__all__ = [
    "BrowserManager",
    "BrowserConfig", 
    "BrowserHandle",
    "start_browser",
    "stop_browser",
    "navigate_to",
]
