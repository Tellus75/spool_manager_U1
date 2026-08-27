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

from .. import matching, printers
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

    def __init__(self, row, spools, parent=None, *, slot_kind: str = "tool", credit_g: float = 0.0):
        super().__init__(parent)
        self.usage_id = row["id"]
        self.grams = float(row["grams"])
        self._credit_g = credit_g
        self._current_spool_id = row["spool_id"]
        self.setProperty("role", "card")

        usage = usage_from_row(row)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        layout.addWidget(ColorDot(usage.color_hex or "#9E9E9E", 24))

        description = QVBoxLayout()
        description.setSpacing(1)

        slot_text = (
            printers.slot_caption(usage.slot, slot_kind)
            if usage.slot is not None
            else t("history.filament")
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
            remaining = self._shown_remaining(spool)
            label = f"{spool.display_name} — {remaining:.0f} g"
            if spool.loaded_slot:
                label += t("review.in_slot", slot=spool.loaded_slot)
            if remaining < self.grams:
                label += t("review.insufficient")
            self.combo.addItem(label, spool.id)

        others = [s for s in spools if s.id not in {c.spool.id for c in scored}]
        if others:
            self.combo.insertSeparator(self.combo.count())
            for spool in others:
                remaining = self._shown_remaining(spool)
                self.combo.addItem(
                    f"{spool.display_name} — {remaining:.0f} g "
                    f"{t('review.other_material', material=spool.material)}",
                    spool.id,
                )

        target = preselected if preselected else (scored[0].spool.id if scored else None)
        if target is not None:
            index = self.combo.findData(target)
            if index >= 0:
                self.combo.setCurrentIndex(index)

    def _shown_remaining(self, spool) -> float:
        if self._current_spool_id is not None and spool.id == self._current_spool_id:
            return spool.remaining_g + self._credit_g
        return spool.remaining_g

    def selection(self):
        return self.combo.currentData()


class ReviewDialog(QDialog):
    """Fait choisir les bobines d'un tranchage, puis applique le décompte."""

    def __init__(self, inventory: Inventory, job_id: int, parent=None, *, reassign: bool = False):
        super().__init__(parent)
        self.inventory = inventory
        self.job_id = job_id
        self.discarded = False
        self.reassign = reassign

        job = inventory.get_job(job_id)
        self.setWindowTitle(t("reassign.title") if reassign else t("review.title"))
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

        explanation = QLabel(t("reassign.explain") if reassign else t("review.explain"))
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        if job["note"]:
            warning = QLabel(job["note"])
            warning.setStyleSheet(f"color: {theme.WARNING};")
            warning.setWordWrap(True)
            layout.addWidget(warning)

        spools = inventory.list_spools()
        if reassign:
            known = {s.id for s in spools}
            for usage in inventory.job_usages(job_id):
                if usage["spool_id"] and usage["spool_id"] not in known:
                    extra = inventory.get_spool(usage["spool_id"])
                    if extra is not None:
                        spools.append(extra)
                        known.add(extra.id)
        kind = printers.kind_for_gcode_printer(job["printer"] or "")
        self._rows: list[UsageRow] = []
        for usage in inventory.job_usages(job_id):
            credit = float(usage["grams"]) if reassign else 0.0
            row = UsageRow(usage, spools, self, slot_kind=kind, credit_g=credit)
            self._rows.append(row)
            layout.addWidget(row)

        layout.addStretch(1)

        footer = QHBoxLayout()
        if not reassign:
            discard = QPushButton(t("review.discard"))
            discard.setProperty("variant", "danger")
            discard.setToolTip(t("review.discard_tip"))
            discard.clicked.connect(self._discard)
            footer.addWidget(discard)
        footer.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(
            t("reassign.apply") if reassign else t("review.deduct")
        )
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(
            t("cancel") if reassign else t("review.later")
        )
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
        if self.reassign:
            self.inventory.reassign_job(self.job_id, assignments)
        else:
            self.inventory.resolve_job(self.job_id, assignments)
        super().accept()


def separator() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {theme.BORDER};")
    return line
