"""Script de post-traitement appelé par Snapmaker Orca à chaque tranchage.

À déclarer dans Orca sous Réglages d'impression > Autres > Scripts de post-traitement :

    "C:\\Program Files\\Python313\\python.exe" "<projet>\\hook\\orca_hook.py"

Orca ajoute le chemin du G-code produit en dernier argument. Ce fichier n'est qu'une
enveloppe : le travail réel est fait par spoolmanager.hook_runner, partagé avec
l'exécutable packagé.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager.hook_runner import find_gcode_path, log, run, write_job  # noqa: E402,F401


def main(argv: list[str]) -> int:
    return run(list(argv[1:]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
