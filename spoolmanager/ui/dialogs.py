"""Boîtes de dialogue : création et édition d'une bobine, pesée, correction."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import orca
from ..inventory import Inventory
from ..models import STATE_LABELS, STATE_NEW, Spool
from . import theme
from .widgets import ColorDot

COMMON_MATERIALS = [
    "PLA", "PETG", "ABS", "ASA", "TPU", "PA", "PA-CF", "PC", "PVA", "HIPS",
    "PLA-CF", "PETG-CF", "PAHT-CF", "PLA-AERO",
]

# Tares usuelles, à titre indicatif : une bobine plastique de 1 kg pèse ~220 g à vide.
DEFAULT_TARE_G = 220.0


class ColorField(QWidget):
    """Sélecteur de couleur : pastille cliquable et saisie hexadécimale."""

    def __init__(self, color: str = "#FF6A13", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._dot = ColorDot(color, size=28)
        self._edit = QLineEdit(theme.safe_color(color))
        self._edit.setMaxLength(7)
        self._edit.setFixedWidth(92)
        self._edit.textChanged.connect(self._on_text_changed)

        button = QPushButton("Choisir…")
        button.clicked.connect(self._pick)

        layout.addWidget(self._dot)
        layout.addWidget(self._edit)
        layout.addWidget(button)
        layout.addStretch(1)

    def _on_text_changed(self, text: str) -> None:
        if QColor(text).isValid():
            self._dot.set_color(text)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.value()), self, "Couleur du filament")
        if chosen.isValid():
            self.set_value(chosen.name().upper())

    def value(self) -> str:
        return theme.safe_color(self._edit.text())

    def set_value(self, color: str) -> None:
        self._edit.setText(theme.safe_color(color))


class SpoolDialog(QDialog):
    """Formulaire d'une bobine.

    Chaque bobine porte sa propre description de filament : modifier une bobine
    ne peut donc jamais altérer une autre, ce qui rend l'édition prévisible.
    """

    def __init__(self, inventory: Inventory, spool: Spool | None = None, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.spool = spool
        self.setWindowTitle("Modifier la bobine" if spool else "Nouvelle bobine")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel("Modifier la bobine" if spool else "Ajouter une bobine à l'étagère")
        title.setProperty("role", "title")
        root.addWidget(title)

        if not spool:
            root.addWidget(self._build_prefill_row())

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.vendor = QLineEdit()
        self.vendor.setPlaceholderText("Snapmaker, Prusament, Sunlu…")
        form.addRow("Marque", self.vendor)

        self.material = QComboBox()
        self.material.setEditable(True)
        self.material.addItems(COMMON_MATERIALS)
        form.addRow("Matière", self.material)

        self.name = QLineEdit()
        self.name.setPlaceholderText("PLA Matte, PETG HF…")
        form.addRow("Gamme", self.name)

        self.color = ColorField()
        form.addRow("Couleur", self.color)

        self.color_name = QLineEdit()
        self.color_name.setPlaceholderText("Orange lave, Noir mat…")
        form.addRow("Nom de la couleur", self.color_name)

        self.preset = QComboBox()
        self.preset.setEditable(True)
        self.preset.setInsertPolicy(QComboBox.NoInsert)
        self._fill_presets()
        form.addRow("Profil Orca associé", self.preset)

        self.density = self._spin(0.5, 3.0, 2, " g/cm³", 1.24)
        form.addRow("Densité", self.density)

        self.diameter = self._spin(1.0, 4.0, 2, " mm", 1.75)
        form.addRow("Diamètre", self.diameter)

        root.addLayout(form)
        root.addWidget(self._separator())

        stock = QFormLayout()
        stock.setSpacing(10)
        stock.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.initial_net = self._spin(0, 20000, 0, " g", 1000)
        stock.addRow("Poids net à l'achat", self.initial_net)

        self.remaining = self._spin(0, 20000, 0, " g", 1000)
        self.remaining.setToolTip(
            "Ce qu'il reste aujourd'hui. Laisser égal au poids d'achat pour une bobine neuve."
        )
        if spool:
            self.remaining.setEnabled(False)
            self.remaining.setToolTip(
                "Le restant se modifie par une pesée ou une correction, "
                "afin de conserver l'historique."
            )
        stock.addRow("Restant actuel", self.remaining)

        self.tare = self._spin(0, 2000, 0, " g", DEFAULT_TARE_G)
        self.tare.setToolTip("Poids de la bobine vide, utilisé lors des pesées de recalage.")
        stock.addRow("Tare (bobine vide)", self.tare)

        self.price = self._spin(0, 999, 2, " EUR", 0)
        stock.addRow("Prix payé", self.price)

        self.shelf = QLineEdit()
        self.shelf.setPlaceholderText("A3, étagère haut…")
        stock.addRow("Case sur l'étagère", self.shelf)

        self.label = QLineEdit()
        self.label.setPlaceholderText("Facultatif, remplace le nom affiché")
        stock.addRow("Étiquette", self.label)

        self.purchase = QDateEdit(QDate.currentDate())
        self.purchase.setCalendarPopup(True)
        self.purchase.setDisplayFormat("dd/MM/yyyy")
        stock.addRow("Date d'achat", self.purchase)

        root.addLayout(stock)

        self._hint = QLabel()
        self._hint.setProperty("role", "subtitle")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.initial_net.valueChanged.connect(self._sync_remaining)
        self.tare.valueChanged.connect(self._update_hint)
        self.remaining.valueChanged.connect(self._update_hint)

        if spool:
            self._load(spool)
        self._update_hint()

    # ------------------------------------------------------------------ mise en page

    def _spin(self, minimum, maximum, decimals, suffix, value) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setValue(value)
        spin.setSingleStep(1 if decimals == 0 else 0.01)
        return spin

    def _separator(self) -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {theme.BORDER};")
        return line

    def _build_prefill_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        hint = QLabel("Préremplir depuis un profil filament de Snapmaker Orca")
        hint.setProperty("role", "subtitle")
        button = QPushButton("Importer un profil…")
        button.clicked.connect(self._prefill_from_preset)

        layout.addWidget(hint, 1)
        layout.addWidget(button)
        return row

    def _fill_presets(self) -> None:
        self.preset.addItem("", "")
        self._presets = orca.load_filament_presets() if orca.is_installed() else []
        for preset in self._presets:
            self.preset.addItem(preset.name, preset.name)

        completer = QCompleter([p.name for p in self._presets], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.preset.setCompleter(completer)

    def _prefill_from_preset(self) -> None:
        chooser = PresetChooser(self._presets, self)
        if chooser.exec() != QDialog.Accepted or chooser.selected is None:
            return

        preset = chooser.selected
        self.vendor.setText(preset.vendor)
        self.material.setCurrentText(preset.material or "PLA")
        self.name.setText(preset.name)
        self.density.setValue(preset.density or 1.24)
        self.diameter.setValue(preset.diameter or 1.75)
        if preset.cost:
            self.price.setValue(preset.cost)
        if preset.color_hex:
            self.color.set_value(preset.color_hex)
        self.preset.setCurrentText(preset.name)

    def _sync_remaining(self, value: float) -> None:
        if self.spool is None:
            self.remaining.setValue(value)

    def _update_hint(self) -> None:
        gross = self.remaining.value() + self.tare.value()
        self._hint.setText(
            f"Sur une balance, cette bobine devrait afficher environ {gross:.0f} g."
        )

    # ------------------------------------------------------------------ données

    def _load(self, spool: Spool) -> None:
        self.vendor.setText(spool.vendor)
        self.material.setCurrentText(spool.material)
        self.name.setText(spool.filament_name)
        self.color.set_value(spool.color_hex)
        self.color_name.setText(spool.color_name)
        self.preset.setCurrentText(spool.orca_preset)
        self.density.setValue(spool.density)
        self.diameter.setValue(spool.diameter)
        self.initial_net.setValue(spool.initial_net_g)
        self.remaining.setValue(spool.remaining_g)
        self.tare.setValue(spool.empty_spool_g)
        self.price.setValue(spool.price)
        self.shelf.setText(spool.shelf_location)
        self.label.setText(spool.label)
        if spool.purchase_date:
            self.purchase.setDate(QDate.fromString(spool.purchase_date, "yyyy-MM-dd"))

    def _filament_fields(self) -> dict:
        return {
            "vendor": self.vendor.text().strip(),
            "material": (self.material.currentText().strip() or "PLA").upper(),
            "name": self.name.text().strip() or self.material.currentText().strip(),
            "color_name": self.color_name.text().strip(),
            "color_hex": self.color.value(),
            "density": self.density.value(),
            "diameter": self.diameter.value(),
            "empty_spool_g": self.tare.value(),
            "price": self.price.value(),
            "nominal_net_g": self.initial_net.value() or 1000,
            "orca_preset": self.preset.currentText().strip(),
        }

    def accept(self) -> None:
        fields = self._filament_fields()
        purchase = self.purchase.date().toString("yyyy-MM-dd")

        if self.spool is None:
            filament_id = self.inventory.create_filament(**fields)
            self.inventory.create_spool(
                filament_id,
                self.initial_net.value(),
                label=self.label.text().strip(),
                shelf_location=self.shelf.text().strip(),
                purchase_date=purchase,
                state=STATE_NEW,
                remaining_g=self.remaining.value(),
            )
        else:
            self.inventory.update_filament(self.spool.filament_id, **fields)
            self.inventory.update_spool(
                self.spool.id,
                label=self.label.text().strip(),
                shelf_location=self.shelf.text().strip(),
                purchase_date=purchase,
                initial_net_g=self.initial_net.value(),
            )
        super().accept()


class PresetChooser(QDialog):
    """Recherche dans les centaines de profils filament d'Orca."""

    def __init__(self, presets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profils filament de Snapmaker Orca")
        self.setMinimumSize(560, 480)
        self.selected = None
        self._presets = presets

        from PySide6.QtWidgets import QListWidget, QListWidgetItem

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher : PLA, Snapmaker, U1…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self._list, 1)

        self._item_class = QListWidgetItem
        self._populate(presets)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Utiliser ce profil")
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._search.setFocus()

    def _populate(self, presets) -> None:
        self._list.clear()
        for preset in presets[:400]:
            details = " · ".join(
                part
                for part in (
                    preset.material,
                    f"{preset.density:g} g/cm³" if preset.density else "",
                    f"{preset.cost:g} EUR" if preset.cost else "",
                )
                if part
            )
            item = self._item_class(f"{preset.name}\n{details}")
            item.setData(Qt.UserRole, preset)
            self._list.addItem(item)

    def _filter(self, text: str) -> None:
        needle = text.strip().casefold()
        if not needle:
            self._populate(self._presets)
            return
        matches = [
            p
            for p in self._presets
            if needle in p.name.casefold() or needle in p.material.casefold()
        ]
        self._populate(matches)

    def accept(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self.selected = item.data(Qt.UserRole)
        super().accept()


class WeighDialog(QDialog):
    """Recalage du restant par pesée : la balance fait foi sur le comptage théorique."""

    def __init__(self, spool: Spool, parent=None):
        super().__init__(parent)
        self.spool = spool
        self.setWindowTitle("Peser la bobine")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(f"Peser « {spool.display_name} »")
        title.setProperty("role", "title")
        layout.addWidget(title)

        explanation = QLabel(
            "Posez la bobine entière sur la balance et saisissez le poids affiché. "
            "La tare enregistrée sera retirée pour recalculer le filament restant."
        )
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        form.setSpacing(10)

        self.gross = QDoubleSpinBox()
        self.gross.setRange(0, 20000)
        self.gross.setDecimals(0)
        self.gross.setSuffix(" g")
        self.gross.setValue(spool.gross_g)
        self.gross.valueChanged.connect(self._update_preview)
        form.addRow("Poids total mesuré", self.gross)

        tare = QLabel(f"{spool.empty_spool_g:.0f} g")
        tare.setProperty("role", "muted")
        form.addRow("Tare enregistrée", tare)

        layout.addLayout(form)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Appliquer la pesée")
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _update_preview(self) -> None:
        net = max(0.0, self.gross.value() - self.spool.empty_spool_g)
        delta = net - self.spool.remaining_g
        if abs(delta) < 0.5:
            self._preview.setText("Le comptage est conforme à la pesée, rien ne changera.")
            self._preview.setStyleSheet(f"color: {theme.MUTED};")
            return

        direction = "de moins" if delta < 0 else "de plus"
        color = theme.WARNING if abs(delta) > 50 else theme.MUTED
        self._preview.setText(
            f"Restant recalculé : {net:.0f} g, soit {abs(delta):.0f} g {direction} "
            f"que les {self.spool.remaining_g:.0f} g comptés."
        )
        self._preview.setStyleSheet(f"color: {color};")

    def gross_value(self) -> float:
        return self.gross.value()


class AdjustDialog(QDialog):
    """Correction manuelle du stock, positive ou négative."""

    def __init__(self, spool: Spool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Corriger le stock")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(f"Corriger « {spool.display_name} »")
        title.setProperty("role", "title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.delta = QDoubleSpinBox()
        self.delta.setRange(-20000, 20000)
        self.delta.setDecimals(1)
        self.delta.setSuffix(" g")
        self.delta.setToolTip("Négatif pour retirer du filament, positif pour en ajouter.")
        form.addRow("Variation", self.delta)

        self.note = QLineEdit()
        self.note.setPlaceholderText("Impression ratée, purge, chute réutilisée…")
        form.addRow("Motif", self.note)

        layout.addLayout(form)

        current = QLabel(f"Restant actuel : {spool.remaining_g:.0f} g")
        current.setProperty("role", "subtitle")
        layout.addWidget(current)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Appliquer")
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def state_label(state: str) -> str:
    return STATE_LABELS.get(state, state)
