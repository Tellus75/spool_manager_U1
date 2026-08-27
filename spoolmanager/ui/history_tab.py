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

from .. import printers
from ..i18n import job_status_label, plural, t
from ..inventory import Inventory
from ..models import (
    JOB_APPLIED,
    JOB_REVERTED,
    JOB_REVIEW,
    format_timestamp,
)
from . import theme
from .dialogs import PartialPrintDialog
from .review_dialog import ReviewDialog

FILTERS = [
    ("history.filter.all", None),
    ("history.filter.review", (JOB_REVIEW,)),
    ("history.filter.applied", (JOB_APPLIED,)),
    ("history.filter.reverted", (JOB_REVERTED,)),
]

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

        title = QLabel(t("history.title"))
        title.setProperty("role", "title")
        self._subtitle = QLabel()
        self._subtitle.setProperty("role", "subtitle")
        titles.addWidget(title)
        titles.addWidget(self._subtitle)
        layout.addLayout(titles, 1)

        self._filter = QComboBox()
        for key, statuses in FILTERS:
            self._filter.addItem(t(key), statuses)
        self._filter.currentIndexChanged.connect(lambda _index: self.refresh())
        layout.addWidget(self._filter, 0, Qt.AlignTop)

        self._review_button = QPushButton(t("history.verify"))
        self._review_button.setProperty("variant", "primary")
        self._review_button.clicked.connect(self._review_selected)
        layout.addWidget(self._review_button, 0, Qt.AlignTop)

        self._undo_button = QPushButton(t("history.undo"))
        self._undo_button.clicked.connect(self._undo_selected)
        layout.addWidget(self._undo_button, 0, Qt.AlignTop)

        self._partial_button = QPushButton(t("history.partial"))
        self._partial_button.clicked.connect(self._partial_selected)
        layout.addWidget(self._partial_button, 0, Qt.AlignTop)

        self._reassign_button = QPushButton(t("history.reassign"))
        self._reassign_button.clicked.connect(self._reassign_selected)
        layout.addWidget(self._reassign_button, 0, Qt.AlignTop)
        return layout

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            [
                t("history.col.date"),
                t("history.col.project"),
                t("history.col.filament"),
                t("history.col.cost"),
                t("history.col.status"),
            ]
        )
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

        self._detail_title = QLabel(t("history.detail"))
        self._detail_title.setProperty("role", "section")
        layout.addWidget(self._detail_title)

        self._detail_summary = QLabel()
        self._detail_summary.setProperty("role", "subtitle")
        self._detail_summary.setWordWrap(True)
        layout.addWidget(self._detail_summary)

        tree = QTreeWidget()
        tree.setHeaderLabels(
            [t("history.tree.filament"), t("history.tree.spool"), t("history.tree.qty")]
        )
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
        statuses = self._filter.currentData()
        jobs = self.inventory.list_jobs(statuses)
        previous = self._selected_job_id()

        self._table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            stamp = format_timestamp(job["sliced_at"] or job["created_at"])
            self._table.setItem(row, 0, QTableWidgetItem(stamp))

            name = QTableWidgetItem(job["project_name"] or t("history.unnamed"))
            name.setData(Qt.UserRole, job["id"])
            self._table.setItem(row, 1, name)

            self._table.setItem(row, 2, QTableWidgetItem(f"{job['total_g']:.1f} g"))
            cost = f"{job['total_cost']:.2f} EUR" if job["total_cost"] else ""
            self._table.setItem(row, 3, QTableWidgetItem(cost))

            status = QTableWidgetItem(job_status_label(job["status"]))
            status.setForeground(QColor(STATUS_COLORS.get(job["status"], theme.TEXT)))
            self._table.setItem(row, 4, status)

            if previous == job["id"]:
                self._table.selectRow(row)

        pending = self.inventory.pending_review_count()
        printed = self.inventory.stats()["total_printed_g"]
        detail = t(
            "history.subtitle",
            count=len(jobs),
            plural=plural(len(jobs)),
            kg=printed / 1000,
        )
        if pending:
            detail += t("history.pending", count=pending)
        self._subtitle.setText(detail)

        if self._table.currentRow() < 0 and jobs:
            self._table.selectRow(0)
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        job_id = self._selected_job_id()
        self._detail_tree.clear()

        if job_id is None:
            self._detail_title.setText(t("history.detail"))
            self._detail_summary.setText(t("history.select"))
            self._review_button.setEnabled(False)
            self._undo_button.setEnabled(False)
            self._partial_button.setEnabled(False)
            self._reassign_button.setEnabled(False)
            return

        job = self.inventory.get_job(job_id)
        if job is None:
            return

        self._detail_title.setText(job["project_name"] or t("history.unnamed"))
        source = t("history.source.hook") if job["source"] == "hook" else t("history.source.watch")
        parts = [
            f"{job['total_g']:.1f} g",
            job["printer"] or "",
            job["print_time"] or "",
            t("history.detected", source=source),
        ]
        summary = " · ".join(p for p in parts if p)
        if self.inventory.job_was_shortened(job_id):
            summary += f" · {t('history.partial.mark')}"
        if job["note"]:
            summary += f"\n{job['note']}"
        self._detail_summary.setText(summary)

        sliced_map = self.inventory.sliced_grams_map(job_id)
        for usage in self.inventory.job_usages(job_id):
            spool = (
                self.inventory.get_spool(usage["spool_id"]) if usage["spool_id"] else None
            )
            slot = usage["extruder_index"]
            kind = printers.kind_for_gcode_printer(job["printer"] or "")
            source = (
                printers.slot_caption(slot, kind) if slot is not None else t("history.filament")
            )
            if usage["material"]:
                source += f" · {usage['material']}"

            if spool is not None:
                target = spool.display_name
            elif usage["grams"] <= 0:
                target = "—"
            else:
                target = t("history.unassigned")

            qty = f"{usage['grams']:.2f} g"
            sliced = sliced_map.get(int(usage["id"]), float(usage["grams"]))
            if abs(sliced - float(usage["grams"])) >= 0.01:
                qty = t("history.qty.revised", actual=usage["grams"], sliced=sliced)
            item = QTreeWidgetItem([source, target, qty])
            if usage["color_hex"]:
                item.setForeground(0, QColor(theme.safe_color(usage["color_hex"])))
            if spool is None and usage["grams"] > 0:
                item.setForeground(1, QColor(theme.WARNING))
            if usage["match_reason"]:
                item.setToolTip(1, usage["match_reason"])
            self._detail_tree.addTopLevelItem(item)

        self._review_button.setEnabled(job["status"] == JOB_REVIEW)
        self._undo_button.setEnabled(job["status"] == JOB_APPLIED)
        self._partial_button.setEnabled(job["status"] == JOB_APPLIED)
        self._reassign_button.setEnabled(job["status"] == JOB_APPLIED)

    def _open_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        job = self.inventory.get_job(job_id)
        if job and job["status"] == JOB_REVIEW:
            self._review_selected()
        elif job and job["status"] == JOB_APPLIED:
            self._reassign_selected()

    def _review_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        dialog = ReviewDialog(self.inventory, job_id, self)
        result = dialog.exec()
        if result or dialog.discarded:
            self.changed.emit()
            self.message.emit(
                t("history.ignored") if dialog.discarded else t("history.applied")
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
            t("history.undone", name=job["project_name"])
        )
        self.refresh()

    def _partial_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        dialog = PartialPrintDialog(self.inventory, job_id, self)
        if not dialog.exec():
            return

        self.inventory.revise_job(job_id, dialog.actual_by_usage())
        job = self.inventory.get_job(job_id)
        grams = float(job["total_g"]) if job else 0.0
        name = job["project_name"] if job else ""
        self.changed.emit()
        self.message.emit(t("history.partial.done", name=name, grams=grams))
        self.refresh()

    def _reassign_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        dialog = ReviewDialog(self.inventory, job_id, self, reassign=True)
        if not dialog.exec():
            return

        job = self.inventory.get_job(job_id)
        name = job["project_name"] if job else ""
        self.changed.emit()
        self.message.emit(t("history.reassigned", name=name))
        self.refresh()

    def show_pending(self) -> None:
        """Bascule sur la file d'attente et ouvre le premier tranchage à vérifier."""
        for index, (_key, statuses) in enumerate(FILTERS):
            if statuses == (JOB_REVIEW,):
                self._filter.setCurrentIndex(index)
                break
        self.refresh()
        if self._table.rowCount():
            self._table.selectRow(0)
            self._review_selected()
