"""Module s0_browser : Gestion du navigateur Selenium."""

from .browser import BrowserManager, start_browser, stop_browser, navigate_to
from .types import BrowserConfig, BrowserHandle
from .export_context import (
    ExportContext,
    set_export_context,
    get_export_context,
    clear_export_context,
)

__all__ = [
    "BrowserManager",
    "BrowserConfig", 
    "BrowserHandle",
    "start_browser",
    "stop_browser",
    "navigate_to",
    "ExportContext",
    "set_export_context",
    "get_export_context",
    "clear_export_context",
]
