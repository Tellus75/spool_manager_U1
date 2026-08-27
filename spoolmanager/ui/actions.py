"""Actions sur une bobine, partagées par le tableau de bord et l'onglet Bobines."""

from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox

from ..inventory import Inventory
from ..models import Spool
from .dialogs import AdjustDialog, SpoolDialog, WeighDialog


class SpoolActions(QObject):
    """Regroupe les opérations sur une bobine et signale les changements."""

    changed = Signal()
    message = Signal(str)

    def __init__(self, inventory: Inventory, parent=None):
        super().__init__(parent)
        self.inventory = inventory
        self._parent_widget = parent

    def create(self) -> None:
        dialog = SpoolDialog(self.inventory, parent=self._parent_widget)
        if dialog.exec():
            self.changed.emit()
            self.message.emit("Bobine ajoutée à l'étagère")

    def edit(self, spool_id: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        dialog = SpoolDialog(self.inventory, spool, parent=self._parent_widget)
        if dialog.exec():
            self.changed.emit()
            self.message.emit(f"« {spool.display_name} » mise à jour")

    def weigh(self, spool_id: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        dialog = WeighDialog(spool, parent=self._parent_widget)
        if not dialog.exec():
            return

        delta = self.inventory.weigh(spool_id, dialog.gross_value())
        self.changed.emit()
        if delta == 0:
            self.message.emit("Pesée conforme au comptage, aucun changement")
        else:
            self.message.emit(
                f"« {spool.display_name} » recalée de {delta:+.0f} g d'après la pesée"
            )

    def adjust(self, spool_id: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        dialog = AdjustDialog(spool, parent=self._parent_widget)
        if not dialog.exec() or dialog.delta.value() == 0:
            return

        self.inventory.adjust(spool_id, dialog.delta.value(), dialog.note.text().strip())
        self.changed.emit()
        self.message.emit(f"Correction de {dialog.delta.value():+.0f} g appliquée")

    def load_into_slot(self, spool_id: int, slot: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        self.inventory.load_into_slot(spool_id, slot)
        self.changed.emit()
        self.message.emit(f"« {spool.display_name} » chargée dans l'emplacement {slot}")

    def unload(self, spool_id: int) -> None:
        self.inventory.unload_spool(spool_id)
        self.changed.emit()
        self.message.emit("Bobine retirée de l'imprimante")

    def archive(self, spool_id: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        confirm = QMessageBox.question(
            self._parent_widget,
            "Archiver la bobine",
            f"Archiver « {spool.display_name} » ?\n\n"
            "Elle disparaîtra de l'étagère et ne sera plus proposée lors des tranchages, "
            "mais son historique de consommation sera conservé.",
        )
        if confirm == QMessageBox.Yes:
            self.inventory.archive_spool(spool_id)
            self.changed.emit()
            self.message.emit(f"« {spool.display_name} » archivée")

    def delete(self, spool_id: int) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return
        confirm = QMessageBox.warning(
            self._parent_widget,
            "Supprimer définitivement",
            f"Supprimer « {spool.display_name} » et tout son historique ?\n\n"
            "Cette action est irréversible. Préférez l'archivage pour conserver "
            "les statistiques de consommation.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.inventory.delete_spool(spool_id)
            self.changed.emit()
            self.message.emit("Bobine supprimée")

    def show_menu(self, spool_id: int, position: QPoint) -> None:
        spool = self.inventory.get_spool(spool_id)
        if spool is None:
            return

        menu = QMenu(self._parent_widget)
        self._add(menu, "Peser…", lambda: self.weigh(spool_id))
        self._add(menu, "Corriger le stock…", lambda: self.adjust(spool_id))
        menu.addSeparator()

        load_menu = menu.addMenu("Charger dans l'emplacement")
        for slot in range(1, self.inventory.slot_count() + 1):
            occupant = self.inventory.slots().get(slot)
            suffix = f" (remplace {occupant.display_name})" if occupant else ""
            action = QAction(f"Emplacement {slot}{suffix}", menu)
            action.setEnabled(spool.loaded_slot != slot)
            action.triggered.connect(lambda _=False, s=slot: self.load_into_slot(spool_id, s))
            load_menu.addAction(action)

        if spool.is_loaded:
            self._add(menu, "Retirer de l'imprimante", lambda: self.unload(spool_id))

        menu.addSeparator()
        self._add(menu, "Modifier…", lambda: self.edit(spool_id))
        self._add(menu, "Archiver", lambda: self.archive(spool_id))
        self._add(menu, "Supprimer définitivement", lambda: self.delete(spool_id))

        menu.exec(position)

    def _add(self, menu: QMenu, text: str, slot) -> QAction:
        action = QAction(text, menu)
        action.triggered.connect(lambda _=False: slot())
        menu.addAction(action)
        return action


def spool_sort_key(spool: Spool):
    """Bobines chargées d'abord, puis par matière et par nom."""
    return (
        spool.loaded_slot is None,
        spool.loaded_slot or 0,
        spool.material.casefold(),
        spool.display_name.casefold(),
    )
