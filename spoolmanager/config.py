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


def appdata_dir() -> Path:
    """APPDATA des trancheurs, surchargeable par SPOOLMANAGER_APPDATA (tests)."""
    override = os.environ.get("SPOOLMANAGER_APPDATA")
    if override:
        return Path(override)
    return Path(os.environ.get("APPDATA") or os.path.expanduser("~"))


def temp_dir() -> Path:
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")


def orca_config_dir() -> Path:
    return appdata_dir() / "Snapmaker_Orca"


def orca_slice_temp_dir() -> Path:
    """Dossier temporaire de Snapmaker Orca (conservé pour les tests existants)."""
    from . import slicers

    dirs = slicers.slice_temp_dirs()
    return dirs[0] if dirs else temp_dir() / "snapmaker_orca_model"


def slice_temp_dirs() -> list[Path]:
    from . import slicers

    return slicers.slice_temp_dirs()
