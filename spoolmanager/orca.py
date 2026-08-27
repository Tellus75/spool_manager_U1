"""Passerelle vers Snapmaker Orca : lecture des profils filament et pose du hook.

Deux précautions ont dicté cette implémentation :

- `Snapmaker_Orca.conf` se termine par une somme de contrôle MD5 : on ne l'écrit jamais.
- Les profils système sont réécrits à chaque mise à jour d'Orca : le hook n'est posé
  que dans les profils de process appartenant à l'utilisateur.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config

# Profils de base, jamais sélectionnables directement dans Orca.
_NON_SELECTABLE = {"false", "0"}


@dataclass
class FilamentPreset:
    """Profil filament d'Orca, ramené aux champs utiles à l'inventaire."""

    name: str
    vendor: str = ""
    material: str = ""
    density: float = 0.0
    cost: float = 0.0
    color_hex: str = ""
    diameter: float = 1.75
    is_user: bool = False

    @property
    def label(self) -> str:
        origin = "Perso" if self.is_user else self.vendor or "Système"
        return f"{self.name}  ({origin})"


def orca_dir() -> Path:
    return config.orca_config_dir()


def is_installed() -> bool:
    return orca_dir().is_dir()


def _first(value) -> str:
    """Les valeurs des profils Orca sont des listes d'une seule chaîne."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return "" if value is None else str(value)


def _to_float(value: str, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _filament_files() -> list[Path]:
    root = orca_dir()
    if not root.is_dir():
        return []
    files: list[Path] = []
    for base in (root / "user", root / "system"):
        if base.is_dir():
            files.extend(p for p in base.rglob("*.json") if p.parent.name == "filament")
    # OrcaFilamentLibrary range ses profils dans des sous-dossiers par marque.
    library = root / "system" / "OrcaFilamentLibrary" / "filament"
    if library.is_dir():
        files.extend(library.rglob("*.json"))
    return sorted(set(files))


def load_filament_presets() -> list[FilamentPreset]:
    """Charge les profils filament d'Orca en résolvant leur chaîne d'héritage."""
    raw: dict[str, dict] = {}
    user_names: set[str] = set()

    for path in _filament_files():
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        name = data.get("name") or path.stem
        # Un profil utilisateur porte le même nom qu'un profil système : il gagne.
        is_user = "user" in path.parts
        if name in raw and not is_user:
            continue
        raw[name] = data
        if is_user:
            user_names.add(name)

    def resolve(name: str, seen: set[str] | None = None) -> dict:
        """Fusionne un profil avec ses parents, l'enfant ayant priorité."""
        seen = seen or set()
        if name in seen or name not in raw:
            return {}
        seen.add(name)
        data = raw[name]
        parent = data.get("inherits")
        merged = resolve(_first(parent), seen) if parent else {}
        merged.update(data)
        return merged

    presets: list[FilamentPreset] = []
    for name, data in raw.items():
        if _first(data.get("instantiation", "true")).lower() in _NON_SELECTABLE:
            continue
        merged = resolve(name)
        presets.append(
            FilamentPreset(
                name=name,
                vendor=_first(merged.get("filament_vendor")),
                material=_first(merged.get("filament_type")).upper(),
                density=_to_float(_first(merged.get("filament_density")), 1.24),
                cost=_to_float(_first(merged.get("filament_cost"))),
                color_hex=_first(merged.get("default_filament_colour")),
                diameter=_to_float(_first(merged.get("filament_diameter")), 1.75),
                is_user=name in user_names,
            )
        )

    presets.sort(key=lambda p: (not p.is_user, p.name.casefold()))
    return presets


# --------------------------------------------------------------- pose du hook


def hook_command() -> str:
    """Ligne à écrire dans le champ « Scripts de post-traitement » d'Orca."""
    if getattr(sys, "frozen", False):
        # L'exécutable packagé sait se comporter en script de post-traitement.
        return f'"{Path(sys.executable)}" --hook'
    return f'"{Path(sys.executable)}" "{config.hook_script_path()}"'


def user_process_presets() -> list[Path]:
    base = orca_dir() / "user"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.json") if p.parent.name == "process")


def read_post_process(path: Path) -> list[str]:
    data = _load_json(path) or {}
    value = data.get("post_process", [])
    if isinstance(value, str):
        return [value] if value else []
    return [str(v) for v in value if str(v).strip()]


def is_hooked(path: Path, command: str | None = None) -> bool:
    command = command or hook_command()
    return any(is_our_hook(entry) or entry == command for entry in read_post_process(path))


def is_our_hook(entry: str) -> bool:
    """Reconnaît notre hook sous ses deux formes : script Python ou exécutable packagé.

    Un profil équipé depuis l'exécutable (`SpoolManager.exe --hook`) puis relu depuis
    les sources doit rester reconnu, sans quoi l'application le croirait dépourvu de
    hook et lui en ajouterait un second.
    """
    lowered = entry.lower()
    return "orca_hook.py" in lowered or ("--hook" in lowered and "spoolmanager" in lowered)


def install_hook(path: Path) -> bool:
    """Ajoute le hook au profil, en préservant les scripts déjà présents."""
    data = _load_json(path)
    if data is None:
        return False

    scripts = [s for s in read_post_process(path) if not is_our_hook(s)]
    scripts.append(hook_command())

    data["post_process"] = scripts
    return _write_preset(path, data)


def uninstall_hook(path: Path) -> bool:
    data = _load_json(path)
    if data is None:
        return False

    scripts = [s for s in read_post_process(path) if not is_our_hook(s)]
    if scripts:
        data["post_process"] = scripts
    else:
        data["post_process"] = ""
    return _write_preset(path, data)


def _write_preset(path: Path, data: dict) -> bool:
    """Écrit un profil de manière atomique, après sauvegarde de l'original."""
    try:
        backup = path.with_suffix(path.suffix + ".spoolmanager.bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())

        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
        )
        temporary.replace(path)
        return True
    except OSError:
        return False


def hook_status() -> list[tuple[Path, bool]]:
    return [(path, is_hooked(path)) for path in user_process_presets()]


def is_orca_running() -> bool:
    """Orca réécrit ses profils en quittant : mieux vaut le fermer avant d'y toucher."""
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq snapmaker-orca.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=creation_flags,
        ).stdout
        return "snapmaker-orca.exe" in output.lower()
    except (OSError, subprocess.SubprocessError):
        return False
