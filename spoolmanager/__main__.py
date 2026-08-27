"""Point d'entrée de l'application.

Deux modes :

    python -m spoolmanager              lance l'interface
    python -m spoolmanager --hook FILE  se comporte en script de post-traitement Orca

Le second mode existe pour l'exécutable packagé : Snapmaker Orca peut alors appeler
directement SpoolManager.exe, sans qu'un interpréteur Python soit installé.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--hook" in argv:
        from .hook_runner import run

        return run([a for a in argv if a != "--hook"])

    from PySide6.QtWidgets import QApplication

    from . import config, db, i18n
    from .ui import theme
    from .ui.main_window import MainWindow, build_icon

    config.ensure_dirs()

    app = QApplication(sys.argv)
    app.setApplicationName("Spool Manager")
    app.setOrganizationName("SpoolManager")
    app.setWindowIcon(build_icon())
    app.setStyleSheet(theme.STYLESHEET)
    # L'application vit dans la zone de notification : fermer la fenêtre ne quitte pas.
    app.setQuitOnLastWindowClosed(False)

    connection = db.connect()
    i18n.set_language(db.get_setting(connection, "language", i18n.DEFAULT_LANGUAGE))
    window = MainWindow(connection, start_hidden="--tray" in argv)

    exit_code = app.exec()
    connection.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
