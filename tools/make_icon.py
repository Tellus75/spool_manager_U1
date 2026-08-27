"""Génère l'icône .ico utilisée par l'exécutable packagé."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager.ui.main_window import build_icon  # noqa: E402


def main() -> None:
    QApplication(sys.argv)

    target = Path(__file__).resolve().parent.parent / "docs" / "spoolmanager.ico"
    target.parent.mkdir(parents=True, exist_ok=True)

    # Windows pioche la taille adaptée au contexte : barre des tâches, zone de
    # notification, explorateur. On les fournit toutes dans un seul fichier.
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(build_icon(size).pixmap(size, size))

    if icon.pixmap(256, 256).save(str(target), "ICO"):
        print(f"écrit : {target}")
    else:
        raise SystemExit("échec de l'écriture de l'icône")


if __name__ == "__main__":
    main()
