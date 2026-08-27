"""Logique du script de post-traitement, appelée depuis Orca.

Vit dans le paquet plutôt que dans le script afin que l'exécutable packagé puisse
lui aussi servir de hook, sans qu'un interpréteur Python soit installé.

Règle absolue : ne jamais faire échouer un tranchage. Toute erreur est journalisée
et l'exécution se termine malgré tout avec le code 0, sans modifier le G-code.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path

from . import config

MAX_LOG_BYTES = 512 * 1024


def log(message: str) -> None:
    try:
        path = config.hook_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            path.write_text("", encoding="utf-8")
        stamp = datetime.now().isoformat(timespec="seconds")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def find_gcode_path(argv: list[str]) -> Path | None:
    """Orca ajoute le chemin du G-code en dernier argument."""
    for candidate in reversed(argv):
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def write_job(job_dict: dict) -> Path:
    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    digest = (job_dict.get("gcode_hash") or "0" * 8)[:8]
    target = config.inbox_dir() / f"{stamp}-{digest}.json"

    # Écriture atomique : l'application ne doit jamais lire un JSON à moitié écrit.
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(job_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def run(argv: list[str]) -> int:
    gcode = find_gcode_path(argv)
    if gcode is None:
        log(f"Aucun fichier G-code dans les arguments : {argv}")
        return 0

    try:
        from . import gcode_parser

        job = gcode_parser.parse_file(gcode, source="hook")

        # Orca connaît le nom de sortie final, plus parlant que le fichier temporaire.
        output_name = os.environ.get("SLIC3R_PP_OUTPUT_NAME", "").strip()
        if output_name:
            job.project_name = gcode_parser.project_name_from_path(output_name)
            job.gcode_path = output_name

        target = write_job(job.to_dict())
        used = sum(1 for u in job.usages if u.grams > 0)
        log(f"{job.project_name} : {job.total_g:.2f} g sur {used} filament(s) -> {target.name}")
    except Exception as error:
        log(f"Échec sur {gcode} : {error}\n{traceback.format_exc()}")

    return 0
