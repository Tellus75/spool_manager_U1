"""Réglages : pose du hook dans Orca, surveillance de secours et préférences."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, config, db, orca
from ..inventory import Inventory
from . import theme


class SettingsTab(QWidget):
    changed = Signal()
    message = Signal(str)

    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.conn = inventory.conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        area = QScrollArea()
        area.setWidgetResizable(True)
        outer.addWidget(area)

        content = QWidget()
        area.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)

        title = QLabel("Réglages")
        title.setProperty("role", "title")
        root.addWidget(title)

        root.addWidget(self._build_hook_group())
        root.addWidget(self._build_watch_group())
        root.addWidget(self._build_preferences_group())
        root.addWidget(self._build_data_group())
        root.addStretch(1)

        self.refresh()

    # ------------------------------------------------------- intégration Orca

    def _build_hook_group(self) -> QGroupBox:
        group = QGroupBox("Intégration Snapmaker Orca")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._orca_status = QLabel()
        self._orca_status.setWordWrap(True)
        layout.addWidget(self._orca_status)

        explanation = QLabel(
            "Le hook est un script que Snapmaker Orca exécute au moment où il écrit le "
            "fichier G-code. Il en lit le grammage et le transmet à cette application, "
            "qui décompte alors le filament sur les bonnes bobines.\n\n"
            "Trancher pour voir l'aperçu ne suffit pas : le décompte a lieu quand vous "
            "exportez le G-code ou l'envoyez à l'imprimante.\n\n"
            "Ce réglage appartient au profil d'impression : il doit être posé sur chaque "
            "profil que vous utilisez. Seuls vos profils personnels peuvent être modifiés, "
            "car les profils système sont réécrits à chaque mise à jour d'Orca."
        )
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        command_row = QHBoxLayout()
        self._command = QLineEdit(orca.hook_command())
        self._command.setReadOnly(True)
        command_row.addWidget(self._command, 1)

        copy = QPushButton("Copier")
        copy.setToolTip(
            "À coller dans Orca sous Réglages d'impression > Autres > "
            "Scripts de post-traitement, pour un profil système."
        )
        copy.clicked.connect(self._copy_command)
        command_row.addWidget(copy)
        layout.addLayout(command_row)

        self._presets = QListWidget()
        self._presets.setSelectionMode(QAbstractItemView.NoSelection)
        self._presets.setMaximumHeight(150)
        layout.addWidget(self._presets)

        buttons = QHBoxLayout()
        install = QPushButton("Installer le hook sur tous mes profils")
        install.setProperty("variant", "primary")
        install.clicked.connect(self._install_hook)
        buttons.addWidget(install)

        remove = QPushButton("Retirer le hook")
        remove.clicked.connect(self._uninstall_hook)
        buttons.addWidget(remove)

        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._hook_warning = QLabel()
        self._hook_warning.setWordWrap(True)
        self._hook_warning.setStyleSheet(f"color: {theme.WARNING};")
        layout.addWidget(self._hook_warning)
        return group

    def _copy_command(self) -> None:
        QGuiApplication.clipboard().setText(orca.hook_command())
        self.message.emit("Commande du hook copiée dans le presse-papiers")

    def _install_hook(self) -> None:
        presets = orca.user_process_presets()
        if not presets:
            QMessageBox.information(
                self,
                "Aucun profil personnel",
                "Snapmaker Orca ne contient aucun profil d'impression personnel.\n\n"
                "Dans Orca, dupliquez le profil que vous utilisez (icône d'enregistrement "
                "à côté du nom du profil), puis revenez ici.",
            )
            return

        if orca.is_orca_running() and not self._confirm_orca_running():
            return

        installed = sum(1 for path in presets if orca.install_hook(path))
        self.refresh()
        self.changed.emit()
        self.message.emit(f"Hook installé sur {installed} profil(s) d'impression")

    def _uninstall_hook(self) -> None:
        if orca.is_orca_running() and not self._confirm_orca_running():
            return

        removed = sum(1 for path in orca.user_process_presets() if orca.uninstall_hook(path))
        self.refresh()
        self.message.emit(f"Hook retiré de {removed} profil(s)")

    def _confirm_orca_running(self) -> bool:
        answer = QMessageBox.warning(
            self,
            "Snapmaker Orca est ouvert",
            "Orca réécrit ses profils en se fermant et annulerait la modification.\n\n"
            "Fermez Orca, puis réessayez. Continuer quand même ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    # ----------------------------------------------------- surveillance dossier

    def _build_watch_group(self) -> QGroupBox:
        group = QGroupBox("Surveillance d'un dossier (secours)")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        explanation = QLabel(
            "Pour une imprimante Bambu (A1 Mini, X1, P1…), Orca exécute le hook dès le "
            "tranchage. Pour la Snapmaker U1, Orca ne l'exécute qu'à l'export du G-code.\n\n"
            "Spool Manager surveille aussi le dossier temporaire d'Orca : un tranchage U1 "
            "est donc décompté dès que l'aperçu est prêt, sans export.\n\n"
            "Le dossier ci-dessous reste un filet de sécurité si vous exportez ailleurs. "
            "Un même fichier n'est jamais compté deux fois."
        )
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._watch_enabled = QCheckBox("Surveiller un dossier d'export")
        self._watch_enabled.toggled.connect(self._save_watch)
        layout.addWidget(self._watch_enabled)

        row = QHBoxLayout()
        self._watch_dir = QLineEdit()
        self._watch_dir.setPlaceholderText("Dossier où Orca exporte vos G-code")
        self._watch_dir.editingFinished.connect(self._save_watch)
        row.addWidget(self._watch_dir, 1)

        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._pick_watch_dir)
        row.addWidget(browse)
        layout.addLayout(row)
        return group

    def _pick_watch_dir(self) -> None:
        start = self._watch_dir.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Dossier à surveiller", start)
        if chosen:
            self._watch_dir.setText(chosen)
            self._save_watch()

    def _save_watch(self) -> None:
        db.set_setting(self.conn, "watch_enabled", "1" if self._watch_enabled.isChecked() else "0")
        db.set_setting(self.conn, "watch_dir", self._watch_dir.text().strip())
        self.changed.emit()

    # ----------------------------------------------------------- préférences

    def _build_preferences_group(self) -> QGroupBox:
        group = QGroupBox("Préférences")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0, 5000)
        self._threshold.setDecimals(0)
        self._threshold.setSuffix(" g")
        self._threshold.setToolTip("En dessous de ce restant, une bobine est signalée.")
        self._threshold.valueChanged.connect(self._save_preferences)
        form.addRow("Seuil d'alerte de stock bas", self._threshold)

        self._slots = QSpinBox()
        self._slots.setRange(1, 16)
        self._slots.setToolTip("La Snapmaker U1 dispose de 4 emplacements filament.")
        self._slots.valueChanged.connect(self._save_preferences)
        form.addRow("Emplacements de l'imprimante", self._slots)

        self._notifications = QCheckBox("Afficher une notification à chaque décompte")
        self._notifications.toggled.connect(self._save_preferences)
        form.addRow("", self._notifications)

        self._tray = QCheckBox("Réduire dans la zone de notification au lieu de quitter")
        self._tray.setToolTip(
            "L'application doit rester active pour décompter les tranchages en direct."
        )
        self._tray.toggled.connect(self._save_preferences)
        form.addRow("", self._tray)

        self._autostart = QCheckBox("Démarrer automatiquement avec Windows")
        self._autostart.toggled.connect(self._save_autostart)
        form.addRow("", self._autostart)
        return group

    def _save_preferences(self) -> None:
        db.set_setting(self.conn, "low_threshold_g", str(int(self._threshold.value())))
        db.set_setting(self.conn, "slot_count", str(self._slots.value()))
        db.set_setting(
            self.conn, "notifications", "1" if self._notifications.isChecked() else "0"
        )
        db.set_setting(self.conn, "minimize_to_tray", "1" if self._tray.isChecked() else "0")
        self.changed.emit()

    def _save_autostart(self, enabled: bool) -> None:
        if not autostart.set_enabled(enabled):
            self.message.emit("Impossible de modifier le démarrage automatique")
            return
        self.message.emit(
            "Démarrage avec Windows activé" if enabled else "Démarrage avec Windows désactivé"
        )

    # --------------------------------------------------------------- données

    def _build_data_group(self) -> QGroupBox:
        group = QGroupBox("Données et diagnostic")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._data_path = QLabel()
        self._data_path.setProperty("role", "subtitle")
        self._data_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._data_path.setWordWrap(True)
        layout.addWidget(self._data_path)

        buttons = QHBoxLayout()
        for text, target in (
            ("Ouvrir le dossier de données", config.data_dir),
            ("Ouvrir le journal du hook", config.log_dir),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, t=target: self._open(t()))
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return group

    def _open(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except OSError:
            self.message.emit(f"Impossible d'ouvrir {path}")

    # --------------------------------------------------------------- refresh

    def refresh(self) -> None:
        self._command.setText(orca.hook_command())

        if not orca.is_installed():
            self._orca_status.setText(
                "Snapmaker Orca n'a pas été trouvé sur cet ordinateur."
            )
            self._orca_status.setStyleSheet(f"color: {theme.DANGER};")
        else:
            running = " (actuellement ouvert)" if orca.is_orca_running() else ""
            self._orca_status.setText(f"Orca détecté : {orca.orca_dir()}{running}")
            self._orca_status.setStyleSheet(f"color: {theme.MUTED};")

        status = orca.hook_status()
        self._presets.clear()
        for path, hooked in status:
            item = QListWidgetItem(
                f"{'✓' if hooked else '○'}   {path.stem}"
            )
            item.setForeground(
                Qt.GlobalColor.white if hooked else Qt.GlobalColor.gray
            )
            item.setToolTip(str(path))
            self._presets.addItem(item)

        if not status:
            self._presets.addItem(
                QListWidgetItem("Aucun profil d'impression personnel dans Orca")
            )
            self._hook_warning.setText(
                "Dupliquez dans Orca le profil d'impression que vous utilisez pour pouvoir "
                "y poser le hook, ou activez la surveillance de dossier ci-dessous."
            )
        elif not any(hooked for _, hooked in status):
            self._hook_warning.setText(
                "Le hook n'est posé sur aucun profil : aucun tranchage ne sera décompté "
                "automatiquement."
            )
        else:
            self._hook_warning.setText("")

        self._threshold.blockSignals(True)
        self._slots.blockSignals(True)
        self._notifications.blockSignals(True)
        self._tray.blockSignals(True)
        self._watch_enabled.blockSignals(True)
        self._autostart.blockSignals(True)

        self._threshold.setValue(self.inventory.low_threshold())
        self._slots.setValue(self.inventory.slot_count())
        self._notifications.setChecked(db.get_setting(self.conn, "notifications", "1") == "1")
        self._tray.setChecked(db.get_setting(self.conn, "minimize_to_tray", "1") == "1")
        self._watch_enabled.setChecked(db.get_setting(self.conn, "watch_enabled", "0") == "1")
        self._watch_dir.setText(db.get_setting(self.conn, "watch_dir", ""))
        self._autostart.setChecked(autostart.is_enabled())

        self._threshold.blockSignals(False)
        self._slots.blockSignals(False)
        self._notifications.blockSignals(False)
        self._tray.blockSignals(False)
        self._watch_enabled.blockSignals(False)
        self._autostart.blockSignals(False)

        self._data_path.setText(
            f"Base de données et journaux : {config.data_dir()}\n"
            f"Boîte de réception des tranchages : {config.inbox_dir()}"
        )
