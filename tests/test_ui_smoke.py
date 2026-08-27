"""Vérifie que chaque écran se construit et se rafraîchit sans erreur.

Les tests tournent avec la plateforme Qt « offscreen » : aucune fenêtre n'apparaît.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager.models import ParsedJob, ParsedUsage  # noqa: E402
from spoolmanager.ui.actions import SpoolActions  # noqa: E402
from spoolmanager.ui.dashboard import Dashboard  # noqa: E402
from spoolmanager.ui.printer_tab import PrinterTab  # noqa: E402
from spoolmanager.ui.spools_tab import SpoolsTab  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def populated(inv, make_filament):
    """Une étagère avec des bobines chargées, entamées et un tranchage décompté."""
    loaded = inv.create_spool(
        make_filament(name="PLA Orange", color_hex="#FF6A13", orca_preset="Snapmaker PLA"),
        1000,
    )
    inv.load_into_slot(loaded, 1)
    inv.create_spool(make_filament(material="PETG", name="PETG Noir",
                                   color_hex="#1A1A1A"), 800)
    almost_empty = inv.create_spool(make_filament(name="PLA Blanc",
                                                  color_hex="#FFFFFF"), 1000)
    inv.adjust(almost_empty, -940, "essais")

    inv.ingest(
        ParsedJob(
            project_name="Support capteur",
            gcode_hash="smoke",
            printer="Snapmaker U1",
            total_g=24.0,
            usages=[ParsedUsage(extruder_index=0, slot=1, grams=24.0, material="PLA")],
        )
    )
    return inv


@pytest.fixture
def actions(app, populated):
    return SpoolActions(populated)


class TestDashboard:
    def test_builds_and_shows_totals(self, app, populated, actions):
        view = Dashboard(populated, actions)
        view.refresh()

        assert view._stat_spools._value.text() == "3"
        assert "kg" in view._stat_stock._value.text()
        assert len(view._cards) == 3

    def test_search_filters_the_shelf(self, app, populated, actions):
        view = Dashboard(populated, actions)
        view._search.setText("PETG")
        assert len(view._cards) == 1

        view._search.setText("")
        assert len(view._cards) == 3

    def test_low_stock_filter(self, app, populated, actions):
        view = Dashboard(populated, actions)
        view._only_low.setChecked(True)
        assert len(view._cards) == 1

    def test_loaded_filter(self, app, populated, actions):
        view = Dashboard(populated, actions)
        view._only_loaded.setChecked(True)
        assert len(view._cards) == 1

    def test_alert_banner_appears_for_low_stock(self, app, populated, actions):
        view = Dashboard(populated, actions)
        assert view._banner.isVisibleTo(view)
        assert "surveiller" in view._banner_text.text()

    def test_empty_shelf_shows_guidance(self, app, inv):
        view = Dashboard(inv, SpoolActions(inv))

        assert view._empty_state.isVisibleTo(view)
        assert not view._shelf.isVisibleTo(view)


class TestSpoolsTab:
    def test_table_lists_every_spool(self, app, populated, actions):
        view = SpoolsTab(populated, actions)
        assert view._table.rowCount() == 3

    def test_selecting_a_row_shows_its_movements(self, app, populated, actions):
        view = SpoolsTab(populated, actions)
        view._table.selectRow(0)

        assert view._movements.rowCount() >= 1
        assert "Mouvements de" in view._movements_title.text()

    def test_material_filter(self, app, populated, actions):
        view = SpoolsTab(populated, actions)
        view._material.setCurrentText("PETG")
        assert view._table.rowCount() == 1

    def test_archived_spools_are_hidden_by_default(self, app, populated, actions):
        first = populated.list_spools()[0]
        populated.archive_spool(first.id)

        view = SpoolsTab(populated, actions)
        assert view._table.rowCount() == 2

        view._show_archived.setChecked(True)
        assert view._table.rowCount() == 3


class TestPrinterTab:
    def test_four_slots_are_shown(self, app, populated, actions):
        view = PrinterTab(populated, actions)
        assert len(view._slot_cards) == 4

    def test_loaded_slot_displays_its_spool(self, app, populated, actions):
        view = PrinterTab(populated, actions)
        assert view._slot_cards[1].spool is not None
        assert view._slot_cards[2].spool is None

    def test_only_unloaded_spools_are_offered(self, app, populated, actions):
        view = PrinterTab(populated, actions)
        assert view._flow.count() == 2

    def test_clearing_a_slot_updates_the_view(self, app, populated, actions):
        view = PrinterTab(populated, actions)
        actions.changed.connect(view.refresh)

        view._on_clear(1)

        assert view._slot_cards[1].spool is None
        assert view._flow.count() == 3
