"""Crée une copie personnelle d'un profil d'impression système de Snapmaker Orca.

Le hook de post-traitement ne peut être posé que sur un profil personnel : Orca
réécrit ses profils système à chaque mise à jour. Cet outil fabrique une copie qui
hérite de tous les réglages de l'original et ne porte que le hook, si bien qu'une
mise à jour d'Orca continuera de profiter aux réglages hérités.

    python tools/derive_preset.py "0.16 High Quality @Snapmaker U1 (0.4 nozzle)"

Orca doit être fermé : il réécrit ses profils en quittant.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager import orca  # noqa: E402

SUFFIX = " - Spool Manager"


def system_process_presets() -> dict[str, Path]:
    base = Path(r"C:\Program Files\Snapmaker_Orca\resources\profiles")
    return {p.stem: p for p in base.glob("*/process/*.json")}


def vendor_version(parent_preset: Path, default: str = "2.2.53.2") -> str:
    """Version du profil constructeur dont hérite la copie.

    Les profils personnels d'un même dossier portent des versions disparates, chacune
    figée au jour de son enregistrement ou héritée d'un profil importé : aucune n'est
    un repère fiable. Le fichier du constructeur, lui, décrit la version réellement
    installée. Orca l'écrit sur quatre nombres zéro-préfixés, que l'on normalise.
    """
    vendor = parent_preset.parent.parent.with_suffix(".json")
    try:
        raw = json.loads(vendor.read_text(encoding="utf-8")).get("version", "")
    except (OSError, json.JSONDecodeError):
        return default

    parts = [part.lstrip("0") or "0" for part in str(raw).split(".")]
    return ".".join(parts) if len(parts) == 4 else default


def preferred_command() -> str:
    """La commande déjà employée ailleurs, sinon l'exécutable, sinon le script.

    Lancé depuis les sources, cet outil produirait une commande pointant vers
    l'interpréteur Python, alors que le hook doit appeler l'application telle qu'elle
    est réellement installée.
    """
    for preset in orca.user_process_presets():
        for entry in orca.read_post_process(preset):
            if orca.is_our_hook(entry):
                return entry

    packaged = Path(__file__).resolve().parent.parent / "dist" / "SpoolManager" / "SpoolManager.exe"
    if packaged.is_file():
        return f'"{packaged}" --hook'
    return orca.hook_command()


def derive(parent: str, command: str) -> Path:
    presets = system_process_presets()
    if parent not in presets:
        raise SystemExit(f"Profil système introuvable : {parent}")

    name = parent + SUFFIX
    target = orca.orca_dir() / "user" / "default" / "process" / f"{name}.json"
    if target.exists():
        raise SystemExit(f"Ce profil existe déjà : {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "from": "User",
                "inherits": parent,
                "is_custom_defined": "0",
                "name": name,
                "print_settings_id": name,
                "version": vendor_version(presets[parent]),
                "post_process": [command],
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )
    return target


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('Usage : derive_preset.py "<nom du profil système>"')

    if orca.is_orca_running():
        raise SystemExit("Fermez Snapmaker Orca : il réécrit ses profils en quittant.")

    command = preferred_command()
    target = derive(sys.argv[1], command)

    print(f"Profil créé : {target}")
    print(f"  hérite de : {sys.argv[1]}")
    print(f"  hook      : {command}")
    print("\nRedémarrez Orca : le profil apparaîtra dans la liste des profils d'impression.")


if __name__ == "__main__":
    main()
