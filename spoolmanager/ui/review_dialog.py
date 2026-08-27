"""Résolution manuelle d'un tranchage dont la bobine n'a pas pu être déterminée."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import matching
from ..i18n import t
from ..inventory import Inventory
from ..models import ParsedUsage, format_timestamp
from . import theme
from .widgets import ColorDot


def usage_from_row(row) -> ParsedUsage:
    """Reconstruit la consommation lue dans le G-code à partir de la ligne stockée."""
    return ParsedUsage(
        extruder_index=row["extruder_index"],
        slot=row["extruder_index"],
        grams=float(row["grams"]),
        length_mm=float(row["length_mm"]),
        preset=row["preset"],
        material=row["material"],
        color_hex=row["color_hex"],
        vendor=row["vendor"],
    )


class UsageRow(QFrame):
    """Une ligne de choix : ce que demande le G-code, et la bobine à décompter."""

    def __init__(self, row, spools, parent=None):
        super().__init__(parent)
        self.usage_id = row["id"]
        self.grams = float(row["grams"])
        self.setProperty("role", "card")

        usage = usage_from_row(row)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        layout.addWidget(ColorDot(usage.color_hex or "#9E9E9E", 24))

        description = QVBoxLayout()
        description.setSpacing(1)

        slot_text = (
            t("history.slot", slot=usage.slot) if usage.slot is not None else t("history.filament")
        )
        headline = QLabel(
            t(
                "review.line",
                slot=slot_text,
                grams=usage.grams,
                material=usage.material or "?",
            )
        )
        headline.setStyleSheet("font-weight: 600;")
        description.addWidget(headline)

        details = " · ".join(p for p in (usage.preset, usage.vendor, usage.color_hex) if p)
        subtitle = QLabel(details or t("review.no_preset"))
        subtitle.setProperty("role", "subtitle")
        subtitle.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        description.addWidget(subtitle)

        reason = row["match_reason"]
        if reason:
            explanation = QLabel(reason)
            explanation.setStyleSheet(f"color: {theme.WARNING}; font-size: 11px;")
            explanation.setWordWrap(True)
            description.addWidget(explanation)

        layout.addLayout(description, 1)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(290)
        self._fill(usage, spools, row["spool_id"])
        layout.addWidget(self.combo)

    def _fill(self, usage: ParsedUsage, spools, preselected) -> None:
        """Propose les bobines de la plus probable à la moins probable."""
        scored = [c for c in (matching.score_spool(usage, s) for s in spools) if c]
        scored.sort(key=lambda c: -c.score)

        if self.grams <= 0:
            self.combo.addItem(t("review.none_needed"), None)
            self.combo.setEnabled(False)
            return

        self.combo.addItem(t("review.skip"), None)
        for candidate in scored:
            spool = candidate.spool
            label = f"{spool.display_name} — {spool.remaining_g:.0f} g"
            if spool.loaded_slot:
                label += t("review.in_slot", slot=spool.loaded_slot)
            if spool.remaining_g < self.grams:
                label += t("review.insufficient")
            self.combo.addItem(label, spool.id)

        others = [s for s in spools if s.id not in {c.spool.id for c in scored}]
        if others:
            self.combo.insertSeparator(self.combo.count())
            for spool in others:
                self.combo.addItem(
                    f"{spool.display_name} — {spool.remaining_g:.0f} g "
                    f"{t('review.other_material', material=spool.material)}",
                    spool.id,
                )

        target = preselected if preselected else (scored[0].spool.id if scored else None)
        if target is not None:
            index = self.combo.findData(target)
            if index >= 0:
                self.combo.setCurrentIndex(index)

    def selection(self):
        return self.combo.currentData()


class ReviewDialog(QDialog):
    """Fait choisir les bobines d'un tranchage, puis applique le décompte."""

    def __init__(self, inventory: Inventory, job_id: int, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.job_id = job_id
        self.discarded = False

        job = inventory.get_job(job_id)
        self.setWindowTitle(t("review.title"))
        self.setMinimumWidth(720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(13)

        title = QLabel(job["project_name"] or t("review.unnamed"))
        title.setProperty("role", "title")
        layout.addWidget(title)

        summary = QLabel(
            t(
                "review.summary",
                grams=job["total_g"],
                printer=job["printer"] or t("review.unknown_printer"),
                when=format_timestamp(job["sliced_at"] or job["created_at"]),
            )
        )
        summary.setProperty("role", "subtitle")
        layout.addWidget(summary)

        explanation = QLabel(t("review.explain"))
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        if job["note"]:
            warning = QLabel(job["note"])
            warning.setStyleSheet(f"color: {theme.WARNING};")
            warning.setWordWrap(True)
            layout.addWidget(warning)

        spools = inventory.list_spools()
        self._rows: list[UsageRow] = []
        for usage in inventory.job_usages(job_id):
            row = UsageRow(usage, spools, self)
            self._rows.append(row)
            layout.addWidget(row)

        layout.addStretch(1)

        footer = QHBoxLayout()
        discard = QPushButton(t("review.discard"))
        discard.setProperty("variant", "danger")
        discard.setToolTip(t("review.discard_tip"))
        discard.clicked.connect(self._discard)
        footer.addWidget(discard)
        footer.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("review.deduct"))
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("review.later"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    def _discard(self) -> None:
        self.inventory.discard_job(self.job_id)
        self.discarded = True
        self.reject()

    def accept(self) -> None:
        assignments = {row.usage_id: row.selection() for row in self._rows}
        self.inventory.resolve_job(self.job_id, assignments)
        super().accept()


def separator() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {theme.BORDER};")
    return line
