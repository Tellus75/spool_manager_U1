"""Trancheurs de la famille Orca / Bambu Studio.

Les trois partagent le même format de profils JSON et le champ post_process.
Seuls changent le dossier de configuration, le nom du processus et le dossier
temporaire où le G-code de tranchage est écrit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import config

DEFAULT_SLICER_ID = "snapmaker_orca"


@dataclass(frozen=True)
class Slicer:
    id: str
    name: str
    config_folder: str
    process_names: tuple[str, ...]
    temp_dir_name: str

    def config_path(self) -> Path:
        if self.id == "snapmaker_orca":
            # Laisser orca_config_dir() surchargeable par les tests.
            return config.orca_config_dir()
        return config.appdata_dir() / self.config_folder

    def temp_path(self) -> Path:
        override = os.environ.get("SPOOLMANAGER_SLICE_TEMP")
        if override:
            return Path(override)
        return config.temp_dir() / self.temp_dir_name

    def is_installed(self) -> bool:
        return self.config_path().is_dir()


SLICERS: tuple[Slicer, ...] = (
    Slicer(
        id="snapmaker_orca",
        name="Snapmaker Orca",
        config_folder="Snapmaker_Orca",
        process_names=("snapmaker-orca.exe",),
        temp_dir_name="snapmaker_orca_model",
    ),
    Slicer(
        id="orca_slicer",
        name="Orca Slicer",
        config_folder="OrcaSlicer",
        process_names=("orca-slicer.exe", "OrcaSlicer.exe"),
        temp_dir_name="orcaslicer_model",
    ),
    Slicer(
        id="bambu_studio",
        name="Bambu Studio",
        config_folder="BambuStudio",
        process_names=("bambu-studio.exe", "BambuStudio.exe"),
        temp_dir_name="bambustudio_model",
    ),
)

_BY_ID = {slicer.id: slicer for slicer in SLICERS}


def get(slicer_id: str) -> Slicer | None:
    return _BY_ID.get(slicer_id)


def parse_enabled_ids(raw: str) -> list[str]:
    """Liste d'identifiants. Vide = tous ; `none` = aucun."""
    if raw.strip().lower() == "none":
        return []
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    known = {slicer.id for slicer in SLICERS}
    filtered = [item for item in ids if item in known]
    return filtered or [slicer.id for slicer in SLICERS]


def enabled(raw: str = "") -> list[Slicer]:
    wanted = set(parse_enabled_ids(raw))
    return [slicer for slicer in SLICERS if slicer.id in wanted]


def installed(raw: str = "") -> list[Slicer]:
    return [slicer for slicer in enabled(raw) if slicer.is_installed()]


def installed_config_dirs(raw: str = "") -> list[tuple[Slicer, Path]]:
    found: list[tuple[Slicer, Path]] = []
    for slicer in enabled(raw):
        path = slicer.config_path()
        if path.is_dir():
            found.append((slicer, path))
    return found


def slice_temp_dirs() -> list[Path]:
    """Dossiers temporaires à surveiller, tous les trancheurs connus.

    Un G-code U1 n'apparaît que dans le temp Snapmaker ; un A1 Mini tranché
    depuis Studio irait dans le temp Bambu. Surveiller les trois est bon marché
    et évite de rater un tranchage parce que le mauvais logiciel est coché.
    """
    override = os.environ.get("SPOOLMANAGER_SLICE_TEMP")
    if override:
        return [Path(override)]
    return [config.temp_dir() / slicer.temp_dir_name for slicer in SLICERS]


def encode_enabled_ids(ids: list[str]) -> str:
    known = {slicer.id for slicer in SLICERS}
    return ",".join(item for item in ids if item in known)


def slicer_for_path(path: Path) -> Slicer | None:
    resolved = path.resolve()
    for slicer in SLICERS:
        try:
            resolved.relative_to(slicer.config_path().resolve())
            return slicer
        except ValueError:
            continue
    return None
