"""Lanceur de l'application et point d'entrée de l'exécutable packagé.

    python run.py              lance l'interface
    python run.py --hook FILE  se comporte en script de post-traitement Orca
"""

import sys

from spoolmanager.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
