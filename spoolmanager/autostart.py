"""Démarrage automatique avec Windows, via la clé Run du registre utilisateur."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
ENTRY_NAME = "SpoolManager"


def _winreg():
    try:
        import winreg

        return winreg
    except ImportError:
        return None


def launch_command() -> str:
    """Commande de démarrage, en mode réduit dans la zone de notification."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --tray'

    # pythonw.exe évite qu'une console noire s'ouvre à chaque démarrage de session.
    interpreter = Path(sys.executable)
    windowless = interpreter.with_name("pythonw.exe")
    if windowless.exists():
        interpreter = windowless

    root = Path(__file__).resolve().parent.parent
    return f'"{interpreter}" "{root / "run.py"}" --tray'


def is_enabled() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, ENTRY_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, ENTRY_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, ENTRY_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
