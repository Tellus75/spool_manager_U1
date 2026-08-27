"""Emplacements sur disque utilisés par l'application et par le hook Orca."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_NAME = "SpoolManager"


def data_dir() -> Path:
    """Dossier de données, surchargeable par SPOOLMANAGER_DATA_DIR (utile pour les tests)."""
    override = os.environ.get("SPOOLMANAGER_DATA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / DATA_DIR_NAME


def db_path() -> Path:
    return data_dir() / "spoolmanager.db"


def inbox_dir() -> Path:
    return data_dir() / "inbox"


def archive_dir() -> Path:
    return data_dir() / "inbox-traites"


def log_dir() -> Path:
    return data_dir() / "logs"


def hook_log_path() -> Path:
    return log_dir() / "orca_hook.log"


def ensure_dirs() -> None:
    for path in (data_dir(), inbox_dir(), archive_dir(), log_dir()):
        path.mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    """Racine du dépôt, d'où sont résolus le script de hook et les ressources."""
    return Path(__file__).resolve().parent.parent


def hook_script_path() -> Path:
    return project_root() / "hook" / "orca_hook.py"


def orca_config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "Snapmaker_Orca"


def orca_slice_temp_dir() -> Path:
    """Dossier où Snapmaker Orca écrit le G-code temporaire au tranchage.

    Pour une imprimante Bambu, Orca exécute les scripts de post-traitement dès
    cette écriture. Pour la U1, il ne le fait qu'à l'export : surveiller ce dossier
    permet de décompter au tranchage, comme pour une A1 Mini.
    """
    override = os.environ.get("SPOOLMANAGER_SLICE_TEMP")
    if override:
        return Path(override)
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / "snapmaker_orca_model"
