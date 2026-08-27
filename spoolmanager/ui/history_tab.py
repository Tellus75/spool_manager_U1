"""Historique des tranchages : détail par bobine, vérification et annulation."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..inventory import Inventory
from ..models import (
    JOB_APPLIED,
    JOB_REVERTED,
    JOB_REVIEW,
    JOB_STATUS_LABELS,
    format_timestamp,
)
from . import theme
from .review_dialog import ReviewDialog

FILTERS = {
    "Tous les tranchages": None,
    "À vérifier": (JOB_REVIEW,),
    "Décomptés": (JOB_APPLIED,),
    "Annulés": (JOB_REVERTED,),
}

STATUS_COLORS = {
    JOB_APPLIED: theme.SUCCESS,
    JOB_REVIEW: theme.WARNING,
    JOB_REVERTED: theme.MUTED,
}


class HistoryTab(QWidget):
    changed = Signal()
    message = Signal(str)

    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(13)

        root.addLayout(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail())
        splitter.setSizes([620, 380])
        root.addWidget(splitter, 1)

        self.refresh()

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)

        title = QLabel("Historique des tranchages")
        title.setProperty("role", "title")
        self._subtitle = QLabel()
        self._subtitle.setProperty("role", "subtitle")
        titles.addWidget(title)
        titles.addWidget(self._subtitle)
        layout.addLayout(titles, 1)

        self._filter = QComboBox()
        self._filter.addItems(FILTERS.keys())
        self._filter.currentTextChanged.connect(self.refresh)
        layout.addWidget(self._filter, 0, Qt.AlignTop)

        self._review_button = QPushButton("Vérifier…")
        self._review_button.setProperty("variant", "primary")
        self._review_button.clicked.connect(self._review_selected)
        layout.addWidget(self._review_button, 0, Qt.AlignTop)

        self._undo_button = QPushButton("Annuler le décompte")
        self._undo_button.clicked.connect(self._undo_selected)
        layout.addWidget(self._undo_button, 0, Qt.AlignTop)
        return layout

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Date", "Projet", "Filament", "Coût", "Statut"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setColumnWidth(0, 140)
        table.setColumnWidth(2, 88)
        table.setColumnWidth(3, 74)
        table.setColumnWidth(4, 96)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.itemSelectionChanged.connect(self._refresh_detail)
        table.itemDoubleClicked.connect(lambda _: self._open_selected())

        self._table = table
        return table

    def _build_detail(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(8)

        self._detail_title = QLabel("Détail")
        self._detail_title.setProperty("role", "section")
        layout.addWidget(self._detail_title)

        self._detail_summary = QLabel()
        self._detail_summary.setProperty("role", "subtitle")
        self._detail_summary.setWordWrap(True)
        layout.addWidget(self._detail_summary)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Filament du tranchage", "Bobine décomptée", "Quantité"])
        tree.setRootIsDecorated(False)
        tree.setColumnWidth(0, 170)
        tree.setColumnWidth(1, 190)
        layout.addWidget(tree, 1)

        self._detail_tree = tree
        return panel

    # ------------------------------------------------------------------ données

    def _selected_job_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        return item.data(Qt.UserRole) if item else None

    def refresh(self) -> None:
        statuses = FILTERS.get(self._filter.currentText())
        jobs = self.inventory.list_jobs(statuses)
        previous = self._selected_job_id()

        self._table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            stamp = format_timestamp(job["sliced_at"] or job["created_at"])
            self._table.setItem(row, 0, QTableWidgetItem(stamp))

            name = QTableWidgetItem(job["project_name"] or "Sans nom")
            name.setData(Qt.UserRole, job["id"])
            self._table.setItem(row, 1, name)

            self._table.setItem(row, 2, QTableWidgetItem(f"{job['total_g']:.1f} g"))
            cost = f"{job['total_cost']:.2f} EUR" if job["total_cost"] else ""
            self._table.setItem(row, 3, QTableWidgetItem(cost))

            status = QTableWidgetItem(JOB_STATUS_LABELS.get(job["status"], job["status"]))
            status.setForeground(QColor(STATUS_COLORS.get(job["status"], theme.TEXT)))
            self._table.setItem(row, 4, status)

            if previous == job["id"]:
                self._table.selectRow(row)

        pending = self.inventory.pending_review_count()
        printed = self.inventory.stats()["total_printed_g"]
        detail = f"{len(jobs)} tranchage{'s' if len(jobs) > 1 else ''} · "
        detail += f"{printed / 1000:.2f} kg décomptés au total"
        if pending:
            detail += f" · {pending} en attente de vérification"
        self._subtitle.setText(detail)

        if self._table.currentRow() < 0 and jobs:
            self._table.selectRow(0)
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        job_id = self._selected_job_id()
        self._detail_tree.clear()

        if job_id is None:
            self._detail_title.setText("Détail")
            self._detail_summary.setText("Sélectionnez un tranchage.")
            self._review_button.setEnabled(False)
            self._undo_button.setEnabled(False)
            return

        job = self.inventory.get_job(job_id)
        if job is None:
            return

        self._detail_title.setText(job["project_name"] or "Sans nom")
        parts = [
            f"{job['total_g']:.1f} g",
            job["printer"] or "",
            job["print_time"] or "",
            f"détecté par {'le hook Orca' if job['source'] == 'hook' else 'la surveillance de dossier'}",
        ]
        summary = " · ".join(p for p in parts if p)
        if job["note"]:
            summary += f"\n{job['note']}"
        self._detail_summary.setText(summary)

        for usage in self.inventory.job_usages(job_id):
            spool = (
                self.inventory.get_spool(usage["spool_id"]) if usage["spool_id"] else None
            )
            slot = usage["extruder_index"]
            source = f"Emplacement {slot}" if slot is not None else "Filament"
            if usage["material"]:
                source += f" · {usage['material']}"

            if spool is not None:
                target = spool.display_name
            elif usage["grams"] <= 0:
                target = "—"
            else:
                target = "Non attribué"

            item = QTreeWidgetItem([source, target, f"{usage['grams']:.2f} g"])
            if usage["color_hex"]:
                item.setForeground(0, QColor(theme.safe_color(usage["color_hex"])))
            if spool is None and usage["grams"] > 0:
                item.setForeground(1, QColor(theme.WARNING))
            if usage["match_reason"]:
                item.setToolTip(1, usage["match_reason"])
            self._detail_tree.addTopLevelItem(item)

        self._review_button.setEnabled(job["status"] == JOB_REVIEW)
        self._undo_button.setEnabled(job["status"] == JOB_APPLIED)

    def _open_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        job = self.inventory.get_job(job_id)
        if job and job["status"] == JOB_REVIEW:
            self._review_selected()

    def _review_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        dialog = ReviewDialog(self.inventory, job_id, self)
        result = dialog.exec()
        if result or dialog.discarded:
            self.changed.emit()
            self.message.emit(
                "Tranchage ignoré" if dialog.discarded else "Décompte appliqué"
            )
        self.refresh()

    def _undo_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        job = self.inventory.get_job(job_id)
        self.inventory.revert_job(job_id)
        self.changed.emit()
        self.message.emit(
            f"Décompte de « {job['project_name']} » annulé, le filament a été restitué"
        )
        self.refresh()

    def show_pending(self) -> None:
        """Bascule sur la file d'attente et ouvre le premier tranchage à vérifier."""
        self._filter.setCurrentText("À vérifier")
        self.refresh()
        if self._table.rowCount():
            self._table.selectRow(0)
            self._review_selected()
