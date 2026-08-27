"""Détection des tranchages : boîte de réception du hook et surveillance de dossier.

Un simple sondage périodique suffit largement ici (quelques fichiers, toutes les deux
secondes) et évite une dépendance supplémentaire tout en restant fiable sur les
dossiers synchronisés, où les notifications du système sont capricieuses.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from . import config, gcode_parser
from .i18n import t
from .models import ParsedJob

POLL_INTERVAL_MS = 2000

GCODE_SUFFIXES = (".gcode", ".gcode.3mf")

# Au premier démarrage, les fichiers déjà présents dans le dossier surveillé sont
# considérés comme connus : on ne décompte pas rétroactivement des mois d'impressions.
IGNORE_OLDER_THAN_S = 24 * 3600


class Watcher(QObject):
    """Surveille la boîte de réception, le G-code temporaire d'Orca, et un dossier d'export."""

    job_detected = Signal(ParsedJob)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watch_dir: Path | None = None
        self._slice_temp_dir: Path | None = config.orca_slice_temp_dir()
        # Dernière signature observée par fichier, pour détecter une écriture en cours.
        self._signatures: dict[str, tuple[int, int]] = {}
        # Signatures déjà traitées, pour ne jamais rejouer un fichier.
        self._processed: set[str] = set()
        self._primed = False

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)

    def start(self) -> None:
        config.ensure_dirs()
        self._timer.start()
        self.poll()

    def stop(self) -> None:
        self._timer.stop()

    def set_watch_dir(self, path: str | None) -> None:
        target = Path(path) if path else None
        if target == self._watch_dir:
            return
        self._watch_dir = target if target and target.is_dir() else None
        self._forget_missing_files()
        self._primed = False

    def set_slice_temp_dir(self, path: str | Path | None) -> None:
        """Surcharge le dossier de G-code temporaire (tests, ou désactivation)."""
        self._slice_temp_dir = Path(path) if path else None
        self._forget_missing_files()
        self._primed = False

    def _forget_missing_files(self) -> None:
        """Évite de rejouer un fichier déjà vu si le dossier surveillé change."""
        self._signatures.clear()
        self._processed.clear()

    # ------------------------------------------------------------------ sondage

    def poll(self) -> None:
        self._poll_inbox()
        self._poll_gcode_dir(self._slice_temp_dir, recursive=True, source="slice")
        self._poll_gcode_dir(self._watch_dir, recursive=False, source="watch")
        self._primed = True

    def _poll_inbox(self) -> None:
        inbox = config.inbox_dir()
        if not inbox.is_dir():
            return

        for path in sorted(inbox.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                job = ParsedJob.from_dict(payload)
            except (OSError, json.JSONDecodeError, TypeError) as error:
                self.failed.emit(t("watch.unreadable", name=path.name, error=error))
                self._archive(path, prefix="illisible-")
                continue

            self.job_detected.emit(job)
            self._archive(path)

    def _archive(self, path: Path, prefix: str = "") -> None:
        """Déplace le fichier traité pour ne jamais le rejouer."""
        try:
            target = config.archive_dir() / f"{prefix}{path.name}"
            if target.exists():
                target.unlink()
            path.replace(target)
        except OSError:
            try:
                path.unlink()
            except OSError:
                pass

    def _list_gcode(self, root: Path, recursive: bool) -> list[Path]:
        try:
            iterator = root.rglob("*") if recursive else root.iterdir()
            return [
                path
                for path in iterator
                if path.is_file() and path.name.lower().endswith(GCODE_SUFFIXES)
            ]
        except OSError:
            return []

    def _poll_gcode_dir(self, root: Path | None, recursive: bool, source: str) -> None:
        if root is None or not root.is_dir():
            return

        now = time.time()
        for path in self._list_gcode(root, recursive):
            try:
                stat = path.stat()
            except OSError:
                continue

            key = str(path)
            signature = (stat.st_size, int(stat.st_mtime))
            token = f"{key}|{signature[0]}|{signature[1]}"
            previous = self._signatures.get(key)
            self._signatures[key] = signature

            if not self._primed:
                # Premier balayage : on recense l'existant sans rien décompter.
                self._processed.add(token)
                continue

            if token in self._processed:
                continue
            if previous != signature:
                # La taille a bougé depuis le dernier sondage : écriture en cours.
                continue
            if now - stat.st_mtime > IGNORE_OLDER_THAN_S:
                self._processed.add(token)
                continue

            self._processed.add(token)
            try:
                job = gcode_parser.parse_file(path, source=source)
            except gcode_parser.GcodeParseError:
                continue
            except OSError as error:
                self.failed.emit(t("watch.read_fail", name=path.name, error=error))
                continue

            self.job_detected.emit(job)
