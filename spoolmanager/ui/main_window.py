"""Fenêtre principale : onglets, icône de zone de notification et décompte en direct."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QTabWidget,
)

from .. import db
from ..inventory import DuplicateJobError, Inventory
from ..models import JOB_REVIEW, ParsedJob
from ..watcher import Watcher
from . import theme
from .actions import SpoolActions
from .dashboard import Dashboard
from .history_tab import HistoryTab
from .printer_tab import PrinterTab
from .settings_tab import SettingsTab
from .spools_tab import SpoolsTab

TAB_DASHBOARD, TAB_SPOOLS, TAB_PRINTER, TAB_HISTORY, TAB_SETTINGS = range(5)


def build_icon(size: int = 64) -> QIcon:
    """Icône dessinée à la volée : une bobine vue de face, aux couleurs de l'app."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = size * 0.08
    outer = QPainterPath()
    outer.addEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.fillPath(outer, QColor(theme.ACCENT))

    inner_margin = size * 0.34
    inner = QPainterPath()
    inner.addEllipse(
        inner_margin, inner_margin, size - 2 * inner_margin, size - 2 * inner_margin
    )
    painter.fillPath(inner, QColor(theme.BG))
    painter.end()

    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, connection, start_hidden: bool = False):
        super().__init__()
        self.conn = connection
        self.inventory = Inventory(connection)

        self.setWindowTitle("Spool Manager — bobines Snapmaker")
        self.setMinimumSize(QSize(1100, 720))
        self.resize(1320, 850)
        self.setWindowIcon(build_icon())

        self.actions_controller = SpoolActions(self.inventory, self)
        self.actions_controller.changed.connect(self.refresh_all)
        self.actions_controller.message.connect(self.notify_status)

        self._build_tabs()
        self._build_tray()

        self.watcher = Watcher(self)
        self.watcher.job_detected.connect(self._on_job_detected)
        self.watcher.failed.connect(self.notify_status)
        self._apply_watch_settings()
        self.watcher.start()

        self.statusBar().showMessage("Prêt · en attente d'un tranchage depuis Snapmaker Orca")

        if not start_hidden:
            self.show()

    # ------------------------------------------------------------------ montage

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.dashboard = Dashboard(self.inventory, self.actions_controller)
        self.spools = SpoolsTab(self.inventory, self.actions_controller)
        self.printer = PrinterTab(self.inventory, self.actions_controller)
        self.history = HistoryTab(self.inventory)
        self.settings = SettingsTab(self.inventory)

        self.tabs.addTab(self.dashboard, "Tableau de bord")
        self.tabs.addTab(self.spools, "Bobines")
        self.tabs.addTab(self.printer, "Imprimante U1")
        self.tabs.addTab(self.history, "Historique")
        self.tabs.addTab(self.settings, "Réglages")

        self.dashboard.review_requested.connect(self._open_pending)
        self.history.changed.connect(self.refresh_all)
        self.history.message.connect(self.notify_status)
        self.settings.changed.connect(self._on_settings_changed)
        self.settings.message.connect(self.notify_status)

        self.setCentralWidget(self.tabs)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(build_icon(), self)
        self.tray.setToolTip("Spool Manager")

        menu = QMenu()
        show = QAction("Ouvrir Spool Manager", self)
        show.triggered.connect(self._restore)
        menu.addAction(show)

        add = QAction("Ajouter une bobine…", self)
        add.triggered.connect(lambda: (self._restore(), self.actions_controller.create()))
        menu.addAction(add)

        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ---------------------------------------------------------------- réactions

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore()

    def _restore(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """Fermer la fenêtre met l'application en veille : elle doit rester à l'écoute."""
        if db.get_setting(self.conn, "minimize_to_tray", "1") == "1":
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Spool Manager continue de tourner",
                "Les tranchages restent décomptés automatiquement. "
                "Clic droit sur l'icône pour quitter.",
                build_icon(),
                4000,
            )
        else:
            self.tray.hide()
            event.accept()

    def _on_settings_changed(self) -> None:
        self._apply_watch_settings()
        self.refresh_all()

    def _apply_watch_settings(self) -> None:
        enabled = db.get_setting(self.conn, "watch_enabled", "0") == "1"
        directory = db.get_setting(self.conn, "watch_dir", "")
        self.watcher.set_watch_dir(directory if enabled else None)

    def _open_pending(self) -> None:
        self.tabs.setCurrentIndex(TAB_HISTORY)
        self.history.show_pending()

    # ------------------------------------------------------------- tranchages

    def _on_job_detected(self, job: ParsedJob) -> None:
        """Décompte un tranchage tout juste détecté et en informe l'utilisateur."""
        try:
            job_id, status, matches = self.inventory.ingest(job)
        except DuplicateJobError:
            self.notify_status(f"« {job.project_name} » a déjà été décompté, ignoré")
            return
        except Exception as error:
            self.notify_status(f"Échec du décompte : {error}")
            return

        self.refresh_all()

        if status == JOB_REVIEW:
            self._notify(
                "Tranchage à vérifier",
                f"« {job.project_name} » : {job.total_g:.0f} g. "
                "La bobine à décompter n'a pas pu être déterminée.",
            )
            self.notify_status(f"« {job.project_name} » en attente de vérification")
            return

        details = []
        for match in matches:
            if match.spool_id is None or match.usage.grams <= 0:
                continue
            spool = self.inventory.get_spool(match.spool_id)
            if spool:
                details.append(
                    f"{match.usage.grams:.0f} g sur {spool.display_name} "
                    f"({spool.remaining_g:.0f} g restants)"
                )

        summary = "\n".join(details) or f"{job.total_g:.0f} g décomptés"
        self._notify(f"{job.project_name} : {job.total_g:.0f} g décomptés", summary)
        self.notify_status(f"« {job.project_name} » décompté · {job.total_g:.0f} g")

        self._warn_if_low(matches)

    def _warn_if_low(self, matches) -> None:
        threshold = self.inventory.low_threshold()
        for match in matches:
            if match.spool_id is None:
                continue
            spool = self.inventory.get_spool(match.spool_id)
            if spool and 0 < spool.remaining_g <= threshold:
                self._notify(
                    "Stock bas",
                    f"Il ne reste que {spool.remaining_g:.0f} g sur "
                    f"« {spool.display_name} ».",
                )

    def _notify(self, title: str, body: str) -> None:
        if db.get_setting(self.conn, "notifications", "1") != "1":
            return
        if self.tray.isSystemTrayAvailable() and self.tray.supportsMessages():
            self.tray.showMessage(title, body, build_icon(), 6000)

    def notify_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    # ------------------------------------------------------------ rafraîchissement

    def refresh_all(self) -> None:
        self.dashboard.refresh()
        self.spools.refresh()
        self.printer.refresh()
        self.history.refresh()

        pending = self.inventory.pending_review_count()
        self.tabs.setTabText(
            TAB_HISTORY, f"Historique ({pending})" if pending else "Historique"
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "À propos",
            "Spool Manager\n\n"
            "Suivi des bobines de filament couplé à Snapmaker Orca.",
        )
