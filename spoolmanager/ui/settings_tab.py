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
    QComboBox,
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

from .. import autostart, config, db, i18n, orca, printers, slicers
from ..i18n import t
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

        title = QLabel(t("settings.title"))
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
        group = QGroupBox(t("settings.hook"))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._orca_status = QLabel()
        self._orca_status.setWordWrap(True)
        layout.addWidget(self._orca_status)

        explanation = QLabel(t("settings.hook.explain"))
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._slicer_boxes: dict[str, QCheckBox] = {}
        slicers_label = QLabel(t("settings.slicers"))
        slicers_label.setProperty("role", "muted")
        layout.addWidget(slicers_label)
        for slicer in slicers.SLICERS:
            box = QCheckBox(slicer.name)
            box.toggled.connect(self._save_slicers)
            self._slicer_boxes[slicer.id] = box
            layout.addWidget(box)

        command_row = QHBoxLayout()
        self._command = QLineEdit(orca.hook_command())
        self._command.setReadOnly(True)
        command_row.addWidget(self._command, 1)

        copy = QPushButton(t("settings.copy"))
        copy.setToolTip(t("settings.copy_tip"))
        copy.clicked.connect(self._copy_command)
        command_row.addWidget(copy)
        layout.addLayout(command_row)

        self._presets = QListWidget()
        self._presets.setSelectionMode(QAbstractItemView.NoSelection)
        self._presets.setMaximumHeight(150)
        layout.addWidget(self._presets)

        buttons = QHBoxLayout()
        install = QPushButton(t("settings.install"))
        install.setProperty("variant", "primary")
        install.clicked.connect(self._install_hook)
        buttons.addWidget(install)

        remove = QPushButton(t("settings.remove"))
        remove.clicked.connect(self._uninstall_hook)
        buttons.addWidget(remove)

        refresh = QPushButton(t("settings.refresh"))
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
        self.message.emit(t("settings.copied"))

    def _install_hook(self) -> None:
        presets = orca.user_process_presets(self.inventory.enabled_slicers_raw())
        if not presets:
            QMessageBox.information(
                self,
                t("settings.no_preset_title"),
                t("settings.no_preset_body"),
            )
            return

        if orca.is_orca_running() and not self._confirm_orca_running():
            return

        installed = sum(1 for path in presets if orca.install_hook(path))
        self.refresh()
        self.changed.emit()
        self.message.emit(t("settings.installed", count=installed))

    def _uninstall_hook(self) -> None:
        if orca.is_orca_running() and not self._confirm_orca_running():
            return

        removed = sum(
            1
            for path in orca.user_process_presets(self.inventory.enabled_slicers_raw())
            if orca.uninstall_hook(path)
        )
        self.refresh()
        self.message.emit(t("settings.removed", count=removed))

    def _confirm_orca_running(self) -> bool:
        answer = QMessageBox.warning(
            self,
            t("settings.orca_open_title"),
            t("settings.orca_open_body"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    # ----------------------------------------------------- surveillance dossier

    def _build_watch_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.watch"))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        explanation = QLabel(t("settings.watch.explain"))
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._watch_enabled = QCheckBox(t("settings.watch.enable"))
        self._watch_enabled.toggled.connect(self._save_watch)
        layout.addWidget(self._watch_enabled)

        row = QHBoxLayout()
        self._watch_dir = QLineEdit()
        self._watch_dir.setPlaceholderText(t("settings.watch.ph"))
        self._watch_dir.editingFinished.connect(self._save_watch)
        row.addWidget(self._watch_dir, 1)

        browse = QPushButton(t("browse"))
        browse.clicked.connect(self._pick_watch_dir)
        row.addWidget(browse)
        layout.addLayout(row)
        return group

    def _pick_watch_dir(self) -> None:
        start = self._watch_dir.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, t("settings.watch.pick"), start)
        if chosen:
            self._watch_dir.setText(chosen)
            self._save_watch()

    def _save_watch(self) -> None:
        db.set_setting(self.conn, "watch_enabled", "1" if self._watch_enabled.isChecked() else "0")
        db.set_setting(self.conn, "watch_dir", self._watch_dir.text().strip())
        self.changed.emit()

    # ----------------------------------------------------------- préférences

    def _build_preferences_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.prefs"))
        form = QFormLayout(group)
        form.setSpacing(10)

        self._language = QComboBox()
        for code, name in i18n.LANGUAGES:
            self._language.addItem(name, code)
        self._language.setToolTip(t("settings.language_tip"))
        self._language.currentIndexChanged.connect(self._save_language)
        form.addRow(t("settings.language"), self._language)

        self._printer = QComboBox()
        self._printer.setToolTip(t("settings.printer_tip"))
        for profile in printers.selectable():
            label = printers.display_name(profile)
            self._printer.addItem(label, profile.id)
        self._printer.currentIndexChanged.connect(self._save_printer)
        form.addRow(t("settings.printer"), self._printer)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0, 5000)
        self._threshold.setDecimals(0)
        self._threshold.setSuffix(" g")
        self._threshold.setToolTip(t("settings.threshold_tip"))
        self._threshold.valueChanged.connect(self._save_preferences)
        form.addRow(t("settings.threshold"), self._threshold)

        self._slots = QSpinBox()
        self._slots.setRange(1, 16)
        self._slots.setToolTip(t("settings.slots_tip"))
        self._slots.valueChanged.connect(self._save_preferences)
        form.addRow(t("settings.slots"), self._slots)

        self._notifications = QCheckBox(t("settings.notifications"))
        self._notifications.toggled.connect(self._save_preferences)
        form.addRow("", self._notifications)

        self._tray = QCheckBox(t("settings.tray"))
        self._tray.setToolTip(t("settings.tray_tip"))
        self._tray.toggled.connect(self._save_preferences)
        form.addRow("", self._tray)

        self._autostart = QCheckBox(t("settings.autostart"))
        self._autostart.toggled.connect(self._save_autostart)
        form.addRow("", self._autostart)
        return group

    def _save_language(self, _index: int = 0) -> None:
        code = self._language.currentData()
        if not code or code == i18n.current_language():
            return
        db.set_setting(self.conn, "language", code)
        i18n.set_language(code)
        self.changed.emit()

    def _save_printer(self, _index: int = 0) -> None:
        printer_id = self._printer.currentData()
        if not printer_id:
            return
        db.set_setting(self.conn, "printer_id", printer_id)
        profile = printers.get(printer_id)
        custom = profile.id == printers.CUSTOM_PRINTER_ID
        self._slots.setEnabled(custom)
        if not custom:
            self._slots.blockSignals(True)
            self._slots.setValue(profile.slot_count)
            self._slots.blockSignals(False)
            db.set_setting(self.conn, "slot_count", str(profile.slot_count))
        self.changed.emit()

    def _save_slicers(self) -> None:
        checked = [
            slicer_id
            for slicer_id, box in self._slicer_boxes.items()
            if box.isChecked()
        ]
        if not checked:
            raw = "none"
        elif len(checked) == len(self._slicer_boxes):
            raw = ""
        else:
            raw = slicers.encode_enabled_ids(checked)
        db.set_setting(self.conn, "enabled_slicers", raw)
        self.changed.emit()

    def _save_preferences(self) -> None:
        db.set_setting(self.conn, "low_threshold_g", str(int(self._threshold.value())))
        if printers.get(self._printer.currentData()).id == printers.CUSTOM_PRINTER_ID:
            db.set_setting(self.conn, "slot_count", str(self._slots.value()))
        db.set_setting(
            self.conn, "notifications", "1" if self._notifications.isChecked() else "0"
        )
        db.set_setting(self.conn, "minimize_to_tray", "1" if self._tray.isChecked() else "0")
        self.changed.emit()

    def _save_autostart(self, enabled: bool) -> None:
        if not autostart.set_enabled(enabled):
            self.message.emit(t("settings.autostart.fail"))
            return
        self.message.emit(
            t("settings.autostart.on") if enabled else t("settings.autostart.off")
        )

    # --------------------------------------------------------------- données

    def _build_data_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.data"))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._data_path = QLabel()
        self._data_path.setProperty("role", "subtitle")
        self._data_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._data_path.setWordWrap(True)
        layout.addWidget(self._data_path)

        buttons = QHBoxLayout()
        for text, target in (
            (t("settings.open_data"), config.data_dir),
            (t("settings.open_log"), config.log_dir),
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
            self.message.emit(t("settings.open_fail", path=path))

    # --------------------------------------------------------------- refresh

    def refresh(self) -> None:
        self._command.setText(orca.hook_command())
        enabled_raw = self.inventory.enabled_slicers_raw()

        installed = slicers.installed()
        if not installed:
            self._orca_status.setText(t("settings.orca_missing"))
            self._orca_status.setStyleSheet(f"color: {theme.DANGER};")
        else:
            running = t("settings.orca_running") if orca.is_orca_running() else ""
            names = ", ".join(slicer.name for slicer in installed)
            self._orca_status.setText(
                t("settings.orca_found", names=names, running=running)
            )
            self._orca_status.setStyleSheet(f"color: {theme.MUTED};")

        status = orca.hook_status(enabled_raw)
        self._presets.clear()
        several = len({slicers.slicer_for_path(path) for path, _ in status}) > 1
        for path, hooked in status:
            label = path.stem
            slicer = slicers.slicer_for_path(path)
            if several and slicer is not None:
                label = f"{slicer.name} · {label}"
            item = QListWidgetItem(f"{'✓' if hooked else '○'}   {label}")
            item.setForeground(
                Qt.GlobalColor.white if hooked else Qt.GlobalColor.gray
            )
            item.setToolTip(str(path))
            self._presets.addItem(item)

        if not status:
            self._presets.addItem(
                QListWidgetItem(t("settings.no_user_preset"))
            )
            self._hook_warning.setText(t("settings.warn_duplicate"))
        elif not any(hooked for _, hooked in status):
            self._hook_warning.setText(t("settings.warn_none"))
        else:
            self._hook_warning.setText("")

        self._language.blockSignals(True)
        self._printer.blockSignals(True)
        self._threshold.blockSignals(True)
        self._slots.blockSignals(True)
        self._notifications.blockSignals(True)
        self._tray.blockSignals(True)
        self._watch_enabled.blockSignals(True)
        self._autostart.blockSignals(True)
        for box in self._slicer_boxes.values():
            box.blockSignals(True)

        current = db.get_setting(self.conn, "language", i18n.DEFAULT_LANGUAGE)
        index = self._language.findData(current)
        if index >= 0:
            self._language.setCurrentIndex(index)

        printer_index = self._printer.findData(self.inventory.printer_id())
        if printer_index >= 0:
            self._printer.setCurrentIndex(printer_index)
        profile = self.inventory.printer()
        self._slots.setEnabled(profile.id == printers.CUSTOM_PRINTER_ID)
        self._threshold.setValue(self.inventory.low_threshold())
        self._slots.setValue(self.inventory.slot_count())
        self._notifications.setChecked(db.get_setting(self.conn, "notifications", "1") == "1")
        self._tray.setChecked(db.get_setting(self.conn, "minimize_to_tray", "1") == "1")
        self._watch_enabled.setChecked(db.get_setting(self.conn, "watch_enabled", "0") == "1")
        self._watch_dir.setText(db.get_setting(self.conn, "watch_dir", ""))
        self._autostart.setChecked(autostart.is_enabled())

        enabled_ids = set(slicers.parse_enabled_ids(enabled_raw))
        for slicer in slicers.SLICERS:
            box = self._slicer_boxes[slicer.id]
            key = "settings.slicer_found" if slicer.is_installed() else "settings.slicer_missing"
            box.setText(t(key, name=slicer.name))
            box.setChecked(slicer.id in enabled_ids)

        self._language.blockSignals(False)
        self._printer.blockSignals(False)
        self._threshold.blockSignals(False)
        self._slots.blockSignals(False)
        self._notifications.blockSignals(False)
        self._tray.blockSignals(False)
        self._watch_enabled.blockSignals(False)
        self._autostart.blockSignals(False)
        for box in self._slicer_boxes.values():
            box.blockSignals(False)

        from .. import __version__

        self._data_path.setText(
            f"{t('settings.version', version=__version__)}\n"
            + t("settings.data_path", data=config.data_dir(), inbox=config.inbox_dir())
        )
