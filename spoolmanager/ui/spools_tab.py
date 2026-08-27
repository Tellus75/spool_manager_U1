"""Onglet Bobines : tableau détaillé, filtres et historique des mouvements."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..inventory import Inventory
from ..models import REASON_LABELS, STATE_ARCHIVED, STATE_LABELS, format_timestamp
from . import theme
from .actions import SpoolActions, spool_sort_key
from .dashboard import ALL_MATERIALS

COLUMNS = [
    ("", 34),
    ("Bobine", 210),
    ("Matière", 82),
    ("Couleur", 118),
    ("Restant", 96),
    ("Remplissage", 132),
    ("Emplacement", 104),
    ("Case", 70),
    ("État", 88),
    ("Valeur", 90),
]


class NumericItem(QTableWidgetItem):
    """Cellule au texte mis en forme, mais triée sur sa valeur numérique.

    Sans cela, « 990 g » se classerait avant « 118 g » puisque Qt comparerait
    les chaînes caractère par caractère.
    """

    def __init__(self, value: float, text: str):
        super().__init__(text)
        self._value = value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._value < other._value
        return super().__lt__(other)


class SpoolsTab(QWidget):
    def __init__(self, inventory: Inventory, actions: SpoolActions, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.actions = actions

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(13)

        root.addLayout(self._build_header())
        root.addLayout(self._build_filters())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_movements())
        splitter.setSizes([460, 200])
        root.addWidget(splitter, 1)

        self.refresh()

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)

        title = QLabel("Bobines")
        title.setProperty("role", "title")
        self._count = QLabel()
        self._count.setProperty("role", "subtitle")
        titles.addWidget(title)
        titles.addWidget(self._count)
        layout.addLayout(titles, 1)

        for text, handler, variant in (
            ("Peser…", self._weigh_selected, None),
            ("Corriger…", self._adjust_selected, None),
            ("Modifier…", self._edit_selected, None),
            ("Ajouter une bobine", self.actions.create, "primary"),
        ):
            button = QPushButton(text)
            if variant:
                button.setProperty("variant", variant)
            button.clicked.connect(handler)
            layout.addWidget(button, 0, Qt.AlignTop)
        return layout

    def _build_filters(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(9)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        layout.addWidget(self._search, 1)

        self._material = QComboBox()
        self._material.setMinimumWidth(160)
        self._material.currentTextChanged.connect(self.refresh)
        layout.addWidget(self._material)

        self._show_archived = QCheckBox("Afficher les archivées")
        self._show_archived.toggled.connect(self.refresh)
        layout.addWidget(self._show_archived)
        return layout

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(COLUMNS))
        table.setHorizontalHeaderLabels([name for name, _ in COLUMNS])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.setSortingEnabled(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_context_menu)
        table.itemDoubleClicked.connect(lambda _: self._edit_selected())
        table.itemSelectionChanged.connect(self._refresh_movements)

        header = table.horizontalHeader()
        for index, (_, width) in enumerate(COLUMNS):
            table.setColumnWidth(index, width)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self._table = table
        return table

    def _build_movements(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(7)

        self._movements_title = QLabel("Mouvements")
        self._movements_title.setProperty("role", "section")
        layout.addWidget(self._movements_title)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Date", "Type", "Variation", "Détail"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setColumnWidth(0, 145)
        table.setColumnWidth(1, 140)
        table.setColumnWidth(2, 100)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        self._movements = table
        return panel

    # ------------------------------------------------------------------ données

    def _selected_spool_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        return item.data(Qt.UserRole) if item else None

    def _edit_selected(self) -> None:
        spool_id = self._selected_spool_id()
        if spool_id is not None:
            self.actions.edit(spool_id)

    def _weigh_selected(self) -> None:
        spool_id = self._selected_spool_id()
        if spool_id is not None:
            self.actions.weigh(spool_id)

    def _adjust_selected(self) -> None:
        spool_id = self._selected_spool_id()
        if spool_id is not None:
            self.actions.adjust(spool_id)

    def _on_context_menu(self, position) -> None:
        spool_id = self._selected_spool_id()
        if spool_id is not None:
            self.actions.show_menu(spool_id, self._table.viewport().mapToGlobal(position))

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
                    spool.orca_preset,
                )
            ).casefold()
            if needle not in haystack:
                return False

        material = self._material.currentText()
        return not (material and material != ALL_MATERIALS and spool.material != material)

    def refresh(self) -> None:
        spools = self.inventory.list_spools(include_archived=self._show_archived.isChecked())

        current = self._material.currentText()
        materials = sorted({s.material for s in spools if s.material})
        self._material.blockSignals(True)
        self._material.clear()
        self._material.addItem(ALL_MATERIALS)
        self._material.addItems(materials)
        if current in materials:
            self._material.setCurrentText(current)
        self._material.blockSignals(False)

        visible = sorted((s for s in spools if self._matches(s)), key=spool_sort_key)
        previous = self._selected_spool_id()

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(visible))
        threshold = self.inventory.low_threshold()

        for row, spool in enumerate(visible):
            dot = QTableWidgetItem()
            dot.setBackground(QColor(theme.safe_color(spool.color_hex)))
            self._table.setItem(row, 0, dot)

            name = QTableWidgetItem(spool.display_name)
            name.setData(Qt.UserRole, spool.id)
            if spool.state == STATE_ARCHIVED:
                name.setForeground(QColor(theme.MUTED))
            self._table.setItem(row, 1, name)

            self._table.setItem(row, 2, QTableWidgetItem(spool.material))
            self._table.setItem(
                row, 3, QTableWidgetItem(spool.color_name or spool.color_hex)
            )

            remaining = NumericItem(spool.remaining_g, f"{spool.remaining_g:.0f} g")
            remaining.setForeground(
                QColor(theme.level_color(spool.ratio, spool.remaining_g, threshold))
            )
            remaining.setToolTip(f"Poids attendu sur la balance : {spool.gross_g:.0f} g")
            self._table.setItem(row, 4, remaining)

            self._table.setItem(
                row,
                5,
                NumericItem(
                    spool.ratio,
                    f"{spool.ratio * 100:.0f} % de {spool.initial_net_g:.0f} g",
                ),
            )
            self._table.setItem(
                row,
                6,
                NumericItem(
                    spool.loaded_slot or 0,
                    str(spool.loaded_slot) if spool.loaded_slot else "",
                ),
            )

            self._table.setItem(row, 7, QTableWidgetItem(spool.shelf_location))
            self._table.setItem(
                row, 8, QTableWidgetItem(STATE_LABELS.get(spool.state, spool.state))
            )
            self._table.setItem(
                row, 9, NumericItem(spool.value_eur, f"{spool.value_eur:.2f} EUR")
            )

            if previous == spool.id:
                self._table.selectRow(row)

        self._table.setSortingEnabled(True)
        if self._table.currentRow() < 0 and visible:
            self._table.selectRow(0)

        total = sum(s.remaining_g for s in visible)
        self._count.setText(
            f"{len(visible)} bobine{'s' if len(visible) > 1 else ''} affichée"
            f"{'s' if len(visible) > 1 else ''} · {total / 1000:.2f} kg au total"
        )
        self._refresh_movements()

    def _refresh_movements(self) -> None:
        spool_id = self._selected_spool_id()
        if spool_id is None:
            self._movements_title.setText("Mouvements")
            self._movements.setRowCount(0)
            return

        spool = self.inventory.get_spool(spool_id)
        self._movements_title.setText(
            f"Mouvements de « {spool.display_name} »" if spool else "Mouvements"
        )

        rows = self.inventory.movements(spool_id)
        self._movements.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._movements.setItem(
                index, 0, QTableWidgetItem(format_timestamp(row["created_at"]))
            )
            self._movements.setItem(
                index, 1, QTableWidgetItem(REASON_LABELS.get(row["reason"], row["reason"]))
            )

            delta = float(row["delta_g"])
            change = QTableWidgetItem(f"{delta:+.1f} g")
            change.setForeground(QColor(theme.SUCCESS if delta > 0 else theme.DANGER))
            self._movements.setItem(index, 2, change)

            detail = row["note"] or row["project_name"] or ""
            self._movements.setItem(index, 3, QTableWidgetItem(detail))
