"""
Module d'initialisation du package Logs
"""

from .logger import GameLogger, get_logger, save_extraction_log, save_bot_log

__all__ = ['GameLogger', 'get_logger', 'save_extraction_log', 'save_bot_log']
