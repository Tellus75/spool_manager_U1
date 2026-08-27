"""Vue des emplacements filament de la Snapmaker U1.

Déclarer quelle bobine occupe quel emplacement est ce qui permet à l'appariement
automatique d'être fiable : le G-code indique l'emplacement consommé, l'application
sait immédiatement de quelle bobine il s'agit.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..inventory import Inventory
from ..models import Spool
from . import theme
from .actions import SpoolActions, spool_sort_key
from .widgets import ColorDot, FlowLayout, Gauge, SpoolCard, spool_id_from_mime


class SlotCard(QFrame):
    """Un emplacement de l'imprimante, cible de dépôt d'une bobine."""

    spool_dropped = Signal(int, int)
    clear_requested = Signal(int)
    pick_requested = Signal(int)

    def __init__(self, slot: int, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.spool: Spool | None = None
        self.setAcceptDrops(True)
        self.setMinimumHeight(158)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        number = QLabel(t("printer.slot", slot=slot))
        number.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; font-weight: 700;")
        header.addWidget(number)
        header.addStretch(1)
        self._dot = ColorDot("#2A2E36", 18)
        header.addWidget(self._dot)
        layout.addLayout(header)

        self._name = QLabel()
        self._name.setWordWrap(True)
        self._name.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self._name)

        self._details = QLabel()
        self._details.setProperty("role", "subtitle")
        self._details.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        layout.addWidget(self._details)

        self._gauge = Gauge()
        layout.addWidget(self._gauge)

        self._remaining = QLabel()
        self._remaining.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(self._remaining)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        self._pick = QPushButton(t("printer.pick"))
        self._pick.setProperty("variant", "ghost")
        self._pick.clicked.connect(lambda: self.pick_requested.emit(self.slot))
        buttons.addWidget(self._pick)

        self._clear = QPushButton(t("printer.remove"))
        self._clear.setProperty("variant", "ghost")
        self._clear.clicked.connect(lambda: self.clear_requested.emit(self.slot))
        buttons.addWidget(self._clear)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.set_spool(None, 150)

    def set_spool(self, spool: Spool | None, low_threshold: float) -> None:
        self.spool = spool
        self._clear.setVisible(spool is not None)

        if spool is None:
            self._apply_role("slot")
            self._dot.set_color("#2A2E36")
            self._name.setText(t("printer.empty"))
            self._name.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {theme.MUTED};")
            self._details.setText(t("printer.drop"))
            self._gauge.set_value(0, theme.BORDER)
            self._remaining.setText("")
            return

        self._apply_role("slotFilled")
        self._dot.set_color(spool.color_hex)
        self._name.setText(spool.display_name)
        self._name.setStyleSheet("font-size: 14px; font-weight: 600;")
        self._details.setText(
            " · ".join(p for p in (spool.material, spool.color_name, spool.vendor) if p)
        )

        color = theme.level_color(spool.ratio, spool.remaining_g, low_threshold)
        self._gauge.set_value(spool.ratio, color)
        self._remaining.setText(f"{spool.remaining_g:.0f} g")
        self._remaining.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color};")

    def _apply_role(self, role: str) -> None:
        self.setProperty("role", role)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if spool_id_from_mime(event.mimeData()) is not None:
            event.acceptProposedAction()
            self._apply_role("slotDrop")

    def dragLeaveEvent(self, event):
        self._apply_role("slotFilled" if self.spool else "slot")

    def dropEvent(self, event):
        spool_id = spool_id_from_mime(event.mimeData())
        self._apply_role("slotFilled" if self.spool else "slot")
        if spool_id is not None:
            event.acceptProposedAction()
            self.spool_dropped.emit(spool_id, self.slot)


class PrinterTab(QWidget):
    """Les emplacements de la U1 en haut, les bobines disponibles en dessous."""

    def __init__(self, inventory: Inventory, actions: SpoolActions, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.actions = actions
        self._slot_cards: dict[int, SlotCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(15)

        title = QLabel(t("printer.title"))
        title.setProperty("role", "title")
        root.addWidget(title)

        subtitle = QLabel(t("printer.subtitle"))
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._slots_layout = QGridLayout()
        self._slots_layout.setSpacing(12)
        root.addLayout(self._slots_layout)

        shelf_title = QLabel(t("printer.available"))
        shelf_title.setProperty("role", "section")
        root.addWidget(shelf_title)

        hint = QLabel(t("printer.hint"))
        hint.setProperty("role", "subtitle")
        root.addWidget(hint)

        area = QScrollArea()
        area.setWidgetResizable(True)
        container = QWidget()
        self._flow = FlowLayout(container, margin=2, spacing=12)
        area.setWidget(container)
        root.addWidget(area, 1)

        self._build_slots()
        self.refresh()

    def _build_slots(self) -> None:
        for index in reversed(range(self._slots_layout.count())):
            widget = self._slots_layout.itemAt(index).widget()
            if widget:
                widget.setParent(None)
        self._slot_cards.clear()

        for slot in range(1, self.inventory.slot_count() + 1):
            card = SlotCard(slot)
            card.spool_dropped.connect(self.actions.load_into_slot)
            card.clear_requested.connect(self._on_clear)
            card.pick_requested.connect(self._on_pick)
            self._slots_layout.addWidget(card, 0, slot - 1)
            self._slot_cards[slot] = card

    def _on_clear(self, slot: int) -> None:
        self.inventory.unload_slot(slot)
        self.actions.changed.emit()
        self.actions.message.emit(t("printer.freed", slot=slot))

    def _on_pick(self, slot: int) -> None:
        menu = QMenu(self)
        candidates = sorted(
            (s for s in self.inventory.list_spools() if s.loaded_slot != slot),
            key=spool_sort_key,
        )
        if not candidates:
            menu.addAction(t("printer.none")).setEnabled(False)
        for spool in candidates:
            label = f"{spool.display_name} — {spool.remaining_g:.0f} g"
            if spool.loaded_slot:
                label += t("printer.currently", slot=spool.loaded_slot)
            action = menu.addAction(label)
            action.triggered.connect(
                lambda _=False, sid=spool.id: self.actions.load_into_slot(sid, slot)
            )
        menu.exec(self._slot_cards[slot].mapToGlobal(self._slot_cards[slot].rect().center()))

    def refresh(self) -> None:
        if len(self._slot_cards) != self.inventory.slot_count():
            self._build_slots()

        threshold = self.inventory.low_threshold()
        slots = self.inventory.slots()
        for slot, card in self._slot_cards.items():
            card.set_spool(slots.get(slot), threshold)

        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        available = sorted(
            (s for s in self.inventory.list_spools() if not s.is_loaded), key=spool_sort_key
        )
        for spool in available:
            card = SpoolCard(spool, threshold)
            card.activated.connect(self.actions.edit)
            card.menu_requested.connect(self.actions.show_menu)
            self._flow.addWidget(card)
