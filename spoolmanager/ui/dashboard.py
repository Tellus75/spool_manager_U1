"""Tableau de bord : chiffres clés, alertes et vue de l'étagère en cartes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..inventory import Inventory
from . import theme
from .actions import SpoolActions, spool_sort_key
from .widgets import FlowLayout, SpoolCard, StatCard

ALL_MATERIALS = "Toutes les matières"


class Dashboard(QWidget):
    """Vue principale : ce qu'il reste sur l'étagère, d'un coup d'œil."""

    review_requested = Signal()

    def __init__(self, inventory: Inventory, actions: SpoolActions, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.actions = actions
        self._cards: dict[int, SpoolCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(16)

        root.addLayout(self._build_header())
        root.addLayout(self._build_stats())

        self._banner = self._build_banner()
        root.addWidget(self._banner)

        root.addLayout(self._build_filters())
        root.addWidget(self._build_shelf(), 1)

        self.refresh()

    # ------------------------------------------------------------------ montage

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)

        title = QLabel("Mon étagère")
        title.setProperty("role", "title")
        self._subtitle = QLabel()
        self._subtitle.setProperty("role", "subtitle")
        titles.addWidget(title)
        titles.addWidget(self._subtitle)

        layout.addLayout(titles, 1)

        add = QPushButton("Ajouter une bobine")
        add.setProperty("variant", "primary")
        add.clicked.connect(self.actions.create)
        layout.addWidget(add, 0, Qt.AlignTop)
        return layout

    def _build_stats(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self._stat_stock = StatCard("Filament en stock", "-", theme.TEXT)
        self._stat_spools = StatCard("Bobines actives", "-", theme.TEXT)
        self._stat_value = StatCard("Valeur du stock", "-", theme.INFO)
        self._stat_printed = StatCard("Filament imprimé", "-", theme.ACCENT)

        for card in (self._stat_stock, self._stat_spools, self._stat_value, self._stat_printed):
            layout.addWidget(card, 1)
        return layout

    def _build_banner(self) -> QFrame:
        banner = QFrame()
        banner.setProperty("role", "banner")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(15, 11, 15, 11)

        self._banner_text = QLabel()
        self._banner_text.setWordWrap(True)
        layout.addWidget(self._banner_text, 1)

        self._banner_button = QPushButton("Voir")
        self._banner_button.clicked.connect(self.review_requested.emit)
        layout.addWidget(self._banner_button)

        banner.hide()
        return banner

    def _build_filters(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(9)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher une bobine, une couleur, une case…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh_cards)
        layout.addWidget(self._search, 1)

        self._material_filter = QComboBox()
        self._material_filter.setMinimumWidth(170)
        self._material_filter.currentTextChanged.connect(self.refresh_cards)
        layout.addWidget(self._material_filter)

        self._only_low = QPushButton("Stock bas")
        self._only_low.setCheckable(True)
        self._only_low.toggled.connect(self.refresh_cards)
        layout.addWidget(self._only_low)

        self._only_loaded = QPushButton("Dans l'imprimante")
        self._only_loaded.setCheckable(True)
        self._only_loaded.toggled.connect(self.refresh_cards)
        layout.addWidget(self._only_loaded)
        return layout

    def _build_shelf(self) -> QScrollArea:
        self._empty_state = QLabel(
            "Aucune bobine ne correspond.\n\n"
            "Ajoutez vos bobines pour que Snapmaker Orca puisse décompter "
            "automatiquement le filament à chaque tranchage."
        )
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setProperty("role", "subtitle")

        self._shelf = QWidget()
        self._flow = FlowLayout(self._shelf, margin=2, spacing=12)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._empty_state)
        layout.addWidget(self._shelf)
        layout.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(container)
        area.setFrameShape(QFrame.NoFrame)
        return area

    # ------------------------------------------------------------------ données

    def refresh(self) -> None:
        self._refresh_material_filter()
        self.refresh_stats()
        self.refresh_cards()

    def refresh_stats(self) -> None:
        stats = self.inventory.stats()
        kilos = stats["total_remaining_g"] / 1000

        self._stat_stock.set_value(f"{kilos:.2f} kg")
        self._stat_spools.set_value(str(int(stats["spool_count"])))
        self._stat_value.set_value(f"{stats['total_value_eur']:.0f} EUR")
        self._stat_printed.set_value(f"{stats['total_printed_g'] / 1000:.2f} kg")

        loaded = sum(1 for s in self.inventory.slots().values() if s is not None)
        self._subtitle.setText(
            f"{int(stats['spool_count'])} bobines suivies, "
            f"{loaded} chargées dans la Snapmaker U1"
        )
        self._refresh_banner(stats)

    def _refresh_banner(self, stats: dict) -> None:
        pending = self.inventory.pending_review_count()
        low = int(stats["low_count"])
        empty = int(stats["empty_count"])

        if pending:
            plural = "s" if pending > 1 else ""
            self._banner_text.setText(
                f"{pending} tranchage{plural} en attente de vérification : "
                "la bobine à décompter n'a pas pu être déterminée avec certitude."
            )
            self._banner_button.setText("Vérifier")
            self._banner_button.show()
            self._banner.show()
            return

        alerts = []
        if empty:
            alerts.append(f"{empty} bobine{'s' if empty > 1 else ''} vide{'s' if empty > 1 else ''}")
        if low:
            threshold = self.inventory.low_threshold()
            alerts.append(f"{low} sous les {threshold:.0f} g")

        if alerts:
            self._banner_text.setText("Stock à surveiller : " + ", ".join(alerts) + ".")
            self._banner_button.hide()
            self._banner.show()
        else:
            self._banner.hide()

    def _refresh_material_filter(self) -> None:
        materials = sorted({s.material for s in self.inventory.list_spools() if s.material})
        current = self._material_filter.currentText()

        self._material_filter.blockSignals(True)
        self._material_filter.clear()
        self._material_filter.addItem(ALL_MATERIALS)
        self._material_filter.addItems(materials)
        if current in materials:
            self._material_filter.setCurrentText(current)
        self._material_filter.blockSignals(False)

    def _matches(self, spool) -> bool:
        needle = self._search.text().strip().casefold()
        if needle:
            haystack = " ".join(
                (
                    spool.display_name,
                    spool.filament_name,
                    spool.vendor,
                    spool.material,
                    spool.color_name,
                    spool.shelf_location,
                )
            ).casefold()
            if needle not in haystack:
                return False

        material = self._material_filter.currentText()
        if material and material != ALL_MATERIALS and spool.material != material:
            return False

        if self._only_low.isChecked() and spool.remaining_g > self.inventory.low_threshold():
            return False

        if self._only_loaded.isChecked() and not spool.is_loaded:
            return False

        return True

    def refresh_cards(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._cards.clear()

        threshold = self.inventory.low_threshold()
        spools = [s for s in self.inventory.list_spools() if self._matches(s)]
        spools.sort(key=spool_sort_key)

        for spool in spools:
            card = SpoolCard(spool, threshold)
            card.activated.connect(self.actions.edit)
            card.menu_requested.connect(self.actions.show_menu)
            self._flow.addWidget(card)
            self._cards[spool.id] = card

        has_cards = bool(spools)
        self._empty_state.setVisible(not has_cards)
        self._shelf.setVisible(has_cards)
