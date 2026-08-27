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
from ..i18n import state_label as translated_state, t
from ..inventory import Inventory
from ..models import STATE_NEW, Spool
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

        button = QPushButton(t("choose"))
        button.clicked.connect(self._pick)

        layout.addWidget(self._dot)
        layout.addWidget(self._edit)
        layout.addWidget(button)
        layout.addStretch(1)

    def _on_text_changed(self, text: str) -> None:
        if QColor(text).isValid():
            self._dot.set_color(text)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.value()), self, t("spool.color_dialog"))
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
        self.setWindowTitle(t("spool.edit_title") if spool else t("spool.new_title"))
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel(t("spool.edit_heading") if spool else t("spool.new_heading"))
        title.setProperty("role", "title")
        root.addWidget(title)

        if not spool:
            root.addWidget(self._build_prefill_row())

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.vendor = QLineEdit()
        self.vendor.setPlaceholderText(t("spool.vendor_ph"))
        form.addRow(t("spool.vendor"), self.vendor)

        self.material = QComboBox()
        self.material.setEditable(True)
        self.material.addItems(COMMON_MATERIALS)
        form.addRow(t("spool.material"), self.material)

        self.name = QLineEdit()
        self.name.setPlaceholderText(t("spool.range_ph"))
        form.addRow(t("spool.range"), self.name)

        self.color = ColorField()
        form.addRow(t("spool.colour"), self.color)

        self.color_name = QLineEdit()
        self.color_name.setPlaceholderText(t("spool.colour_ph"))
        form.addRow(t("spool.colour_name"), self.color_name)

        self.preset = QComboBox()
        self.preset.setEditable(True)
        self.preset.setInsertPolicy(QComboBox.NoInsert)
        self._fill_presets()
        form.addRow(t("spool.preset"), self.preset)

        self.density = self._spin(0.5, 3.0, 2, " g/cm³", 1.24)
        form.addRow(t("spool.density"), self.density)

        self.diameter = self._spin(1.0, 4.0, 2, " mm", 1.75)
        form.addRow(t("spool.diameter"), self.diameter)

        root.addLayout(form)
        root.addWidget(self._separator())

        stock = QFormLayout()
        stock.setSpacing(10)
        stock.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.initial_net = self._spin(0, 20000, 0, " g", 1000)
        stock.addRow(t("spool.net"), self.initial_net)

        self.remaining = self._spin(0, 20000, 0, " g", 1000)
        self.remaining.setToolTip(t("spool.remaining_tip_new"))
        if spool:
            self.remaining.setEnabled(False)
            self.remaining.setToolTip(t("spool.remaining_tip_edit"))
        stock.addRow(t("spool.remaining"), self.remaining)

        self.tare = self._spin(0, 2000, 0, " g", DEFAULT_TARE_G)
        self.tare.setToolTip(t("spool.tare_tip"))
        stock.addRow(t("spool.tare"), self.tare)

        self.price = self._spin(0, 999, 2, " EUR", 0)
        stock.addRow(t("spool.price"), self.price)

        self.shelf = QLineEdit()
        self.shelf.setPlaceholderText(t("spool.bin_ph"))
        stock.addRow(t("spool.bin"), self.shelf)

        self.label = QLineEdit()
        self.label.setPlaceholderText(t("spool.label_ph"))
        stock.addRow(t("spool.label"), self.label)

        self.purchase = QDateEdit(QDate.currentDate())
        self.purchase.setCalendarPopup(True)
        self.purchase.setDisplayFormat(t("date.display"))
        stock.addRow(t("spool.purchase"), self.purchase)

        root.addLayout(stock)

        self._hint = QLabel()
        self._hint.setProperty("role", "subtitle")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(t("save"))
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("cancel"))
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

        hint = QLabel(t("spool.prefill"))
        hint.setProperty("role", "subtitle")
        button = QPushButton(t("spool.import"))
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
            t("spool.hint_gross", g=gross)
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
        self.setWindowTitle(t("preset.title"))
        self.setMinimumSize(560, 480)
        self.selected = None
        self._presets = presets

        from PySide6.QtWidgets import QListWidget, QListWidgetItem

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("preset.search"))
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self._list, 1)

        self._item_class = QListWidgetItem
        self._populate(presets)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("preset.use"))
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("cancel"))
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
        self.setWindowTitle(t("weigh.title"))
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(t("weigh.heading", name=spool.display_name))
        title.setProperty("role", "title")
        layout.addWidget(title)

        explanation = QLabel(t("weigh.explain"))
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
        form.addRow(t("weigh.gross"), self.gross)

        tare = QLabel(f"{spool.empty_spool_g:.0f} g")
        tare.setProperty("role", "muted")
        form.addRow(t("weigh.tare"), tare)

        layout.addLayout(form)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("weigh.apply"))
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _update_preview(self) -> None:
        net = max(0.0, self.gross.value() - self.spool.empty_spool_g)
        delta = net - self.spool.remaining_g
        if abs(delta) < 0.5:
            self._preview.setText(t("weigh.match"))
            self._preview.setStyleSheet(f"color: {theme.MUTED};")
            return

        direction = t("weigh.less") if delta < 0 else t("weigh.more")
        color = theme.WARNING if abs(delta) > 50 else theme.MUTED
        self._preview.setText(
            t(
                "weigh.preview",
                net=net,
                delta=abs(delta),
                direction=direction,
                counted=self.spool.remaining_g,
            )
        )
        self._preview.setStyleSheet(f"color: {color};")

    def gross_value(self) -> float:
        return self.gross.value()


class AdjustDialog(QDialog):
    """Correction manuelle du stock, positive ou négative."""

    def __init__(self, spool: Spool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("adjust.title"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(t("adjust.heading", name=spool.display_name))
        title.setProperty("role", "title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.delta = QDoubleSpinBox()
        self.delta.setRange(-20000, 20000)
        self.delta.setDecimals(1)
        self.delta.setSuffix(" g")
        self.delta.setToolTip(t("adjust.delta_tip"))
        form.addRow(t("adjust.delta"), self.delta)

        self.note = QLineEdit()
        self.note.setPlaceholderText(t("adjust.note_ph"))
        form.addRow(t("adjust.note"), self.note)

        layout.addLayout(form)

        current = QLabel(t("adjust.current", g=spool.remaining_g))
        current.setProperty("role", "subtitle")
        layout.addWidget(current)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("apply"))
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class PartialPrintDialog(QDialog):
    """Corrige le poids réellement consommé d'une impression arrêtée avant la fin."""

    def __init__(self, inventory: Inventory, job_id: int, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self.job_id = job_id
        self._spins: dict[int, QDoubleSpinBox] = {}
        self._currents: dict[int, float] = {}
        self._sliced: dict[int, float] = {}
        self._updating = False

        job = inventory.get_job(job_id)
        name = (job["project_name"] if job else "") or t("history.unnamed")
        self.setWindowTitle(t("partial.title"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(t("partial.heading", name=name))
        title.setProperty("role", "title")
        layout.addWidget(title)

        explanation = QLabel(t("partial.explain"))
        explanation.setProperty("role", "subtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        form.setSpacing(10)

        self._progress = QDoubleSpinBox()
        self._progress.setRange(0, 100)
        self._progress.setDecimals(0)
        self._progress.setSuffix(" %")
        self._progress.setToolTip(t("partial.progress_tip"))
        self._progress.valueChanged.connect(self._apply_progress)
        form.addRow(t("partial.progress"), self._progress)

        sliced_map = inventory.sliced_grams_map(job_id)
        for usage in inventory.job_usages(job_id):
            sliced = sliced_map.get(int(usage["id"]), float(usage["grams"]))
            if sliced <= 0:
                continue
            uid = int(usage["id"])
            spool = (
                inventory.get_spool(usage["spool_id"]) if usage["spool_id"] else None
            )
            label = spool.display_name if spool else (usage["material"] or t("history.filament"))
            slot = usage["extruder_index"]
            if slot is not None:
                label = f"{t('history.slot', slot=slot)} · {label}"

            spin = QDoubleSpinBox()
            spin.setRange(0, sliced)
            spin.setDecimals(2)
            spin.setSuffix(" g")
            spin.setValue(float(usage["grams"]))
            spin.setToolTip(t("partial.sliced", grams=sliced))
            spin.valueChanged.connect(lambda _value: self._on_grams_changed())

            caption = QLabel(f"{label}\n{t('partial.sliced', grams=sliced)}")
            caption.setProperty("role", "muted")
            form.addRow(caption, spin)

            self._spins[uid] = spin
            self._currents[uid] = float(usage["grams"])
            self._sliced[uid] = sliced

        layout.addLayout(form)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("partial.apply"))
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText(t("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._sync_progress_from_grams()
        self._update_preview()

    def _apply_progress(self, percent: float) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            for uid, spin in self._spins.items():
                spin.setValue(round(self._sliced[uid] * percent / 100.0, 2))
        finally:
            self._updating = False
        self._update_preview()

    def _on_grams_changed(self) -> None:
        if self._updating:
            return
        self._sync_progress_from_grams()
        self._update_preview()

    def _sync_progress_from_grams(self) -> None:
        sliced_total = sum(self._sliced.values())
        if sliced_total <= 0:
            return
        actual_total = sum(spin.value() for spin in self._spins.values())
        percent = round(100.0 * actual_total / sliced_total)
        self._updating = True
        try:
            self._progress.setValue(max(0, min(100, percent)))
        finally:
            self._updating = False

    def _update_preview(self) -> None:
        net = sum(
            self._currents[uid] - spin.value() for uid, spin in self._spins.items()
        )
        if abs(net) < 0.05:
            self._preview.setText(t("partial.preview_none"))
            self._preview.setStyleSheet(f"color: {theme.MUTED};")
        elif net > 0:
            self._preview.setText(t("partial.preview_restore", grams=net))
            self._preview.setStyleSheet(f"color: {theme.SUCCESS};")
        else:
            self._preview.setText(t("partial.preview_deduct", grams=abs(net)))
            self._preview.setStyleSheet(f"color: {theme.WARNING};")

    def actual_by_usage(self) -> dict[int, float]:
        return {uid: spin.value() for uid, spin in self._spins.items()}


def state_label(state: str) -> str:
    return translated_state(state)
