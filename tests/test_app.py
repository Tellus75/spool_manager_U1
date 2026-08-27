"""Parcours de bout en bout : un tranchage arrive, le stock bouge, l'interface suit."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager import config, db  # noqa: E402
from spoolmanager.inventory import Inventory  # noqa: E402
from spoolmanager.models import JOB_APPLIED, JOB_REVERTED, JOB_REVIEW  # noqa: E402
from spoolmanager.ui.history_tab import HistoryTab  # noqa: E402
from spoolmanager.ui.main_window import MainWindow, TAB_DASHBOARD, TAB_SETTINGS  # noqa: E402
from spoolmanager.ui.settings_tab import SettingsTab  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("SPOOLMANAGER_DATA_DIR", str(tmp_path / "data"))
    config.ensure_dirs()

    connection = db.connect(tmp_path / "app.db")
    inventory = Inventory(connection)

    orange = inventory.create_filament(
        vendor="Snapmaker", material="PLA", name="PLA Orange", color_hex="#FF6A13"
    )
    black = inventory.create_filament(
        vendor="Generic", material="PETG", name="PETG Noir", color_hex="#1A1A1A"
    )
    inventory.load_into_slot(inventory.create_spool(orange, 1000), 1)
    inventory.load_into_slot(inventory.create_spool(black, 1000), 3)

    window = MainWindow(connection, start_hidden=True)
    window.watcher.stop()
    yield window
    window.tray.hide()
    connection.close()


def send_job(window, **overrides):
    payload = {
        "project_name": "Carter moteur",
        "gcode_hash": "hash-carter",
        "printer": "Snapmaker U1",
        "total_g": 18.36,
        "source": "hook",
        "usages": [
            {"extruder_index": 0, "slot": 1, "grams": 14.38, "material": "PLA"},
            {"extruder_index": 2, "slot": 3, "grams": 3.98, "material": "PETG"},
        ],
    }
    payload.update(overrides)
    inbox = config.inbox_dir() / "job.json"
    inbox.write_text(json.dumps(payload), encoding="utf-8")
    window.watcher.poll()


class TestLiveDeduction:
    def test_a_sliced_job_deducts_the_loaded_spools(self, window):
        send_job(window)

        slots = window.inventory.slots()
        assert slots[1].remaining_g == pytest.approx(985.62)
        assert slots[3].remaining_g == pytest.approx(996.02)

    def test_the_dashboard_updates_immediately(self, window):
        send_job(window)

        card = window.dashboard._cards[window.inventory.slots()[1].id]
        assert "986" in card._remaining.text()
        assert "kg" in window.dashboard._stat_printed._value.text()

    def test_the_history_lists_the_job(self, window):
        send_job(window)

        assert window.history._table.rowCount() == 1
        assert window.history._table.item(0, 1).text() == "Carter moteur"

    def test_the_same_file_twice_is_not_counted_twice(self, window):
        send_job(window)
        send_job(window)

        assert window.inventory.slots()[1].remaining_g == pytest.approx(985.62)
        assert window.history._table.rowCount() == 1

    def test_an_unknown_material_goes_to_review(self, window):
        send_job(
            window,
            gcode_hash="hash-asa",
            usages=[{"extruder_index": 0, "slot": 1, "grams": 30.0, "material": "ASA"}],
        )

        assert window.inventory.pending_review_count() == 1
        assert window.inventory.slots()[1].remaining_g == 1000
        assert window.tabs.tabText(3) == "Historique (1)"

    def test_review_badge_disappears_once_resolved(self, window):
        send_job(
            window,
            gcode_hash="hash-asa",
            usages=[{"extruder_index": 0, "slot": 1, "grams": 30.0, "material": "ASA"}],
        )
        job_id = window.inventory.list_jobs()[0]["id"]
        usage_id = window.inventory.job_usages(job_id)[0]["id"]

        window.inventory.resolve_job(job_id, {usage_id: window.inventory.slots()[1].id})
        window.refresh_all()

        assert window.tabs.tabText(3) == "Historique"
        assert window.inventory.slots()[1].remaining_g == pytest.approx(970)


class TestUndo:
    def test_undoing_from_the_history_restores_the_filament(self, window):
        send_job(window)
        window.tabs.setCurrentIndex(3)
        window.history._table.selectRow(0)

        window.history._undo_selected()

        assert window.inventory.slots()[1].remaining_g == pytest.approx(1000)
        assert window.inventory.list_jobs()[0]["status"] == JOB_REVERTED

    def test_undo_button_is_only_active_on_a_deducted_job(self, window):
        send_job(window)
        window.history._table.selectRow(0)
        assert window.history._undo_button.isEnabled()
        assert window.history._partial_button.isEnabled()
        assert not window.history._review_button.isEnabled()

        window.history._undo_selected()
        window.history._table.selectRow(0)
        assert not window.history._undo_button.isEnabled()
        assert not window.history._partial_button.isEnabled()


class TestHistoryFilters:
    def test_pending_filter_shows_only_jobs_to_review(self, window):
        send_job(window)
        send_job(
            window,
            gcode_hash="hash-asa",
            usages=[{"extruder_index": 0, "slot": 1, "grams": 30.0, "material": "ASA"}],
        )

        history = HistoryTab(window.inventory)
        history._filter.setCurrentText("À vérifier")

        assert history._table.rowCount() == 1
        assert history._table.item(0, 4).text() == "À vérifier"

    def test_detail_panel_names_the_deducted_spools(self, window):
        send_job(window)
        window.history._table.selectRow(0)

        tree = window.history._detail_tree
        assert tree.topLevelItemCount() == 2
        assert "PLA Orange" in tree.topLevelItem(0).text(1)
        assert tree.topLevelItem(0).text(2) == "14.38 g"


class TestStoppedPrint:
    def test_revising_from_history_credits_unused_filament(self, window):
        send_job(window)
        job_id = window.inventory.list_jobs()[0]["id"]
        pla_usage = next(
            u for u in window.inventory.job_usages(job_id) if u["material"] == "PLA"
        )

        window.inventory.revise_job(job_id, {int(pla_usage["id"]): 5.0})
        window.refresh_all()
        window.history._table.selectRow(0)

        assert window.inventory.slots()[1].remaining_g == pytest.approx(995.0)
        assert window.inventory.slots()[3].remaining_g == pytest.approx(996.02)
        assert "impression inachevée" in window.history._detail_summary.text()
        assert window.history._detail_tree.topLevelItem(0).text(2) == "5.00 g / 14.38 g"
        assert window.history._partial_button.isEnabled()

    def test_partial_dialog_caps_at_the_sliced_weight(self, window):
        from spoolmanager.ui.dialogs import PartialPrintDialog

        send_job(window)
        job_id = window.inventory.list_jobs()[0]["id"]
        dialog = PartialPrintDialog(window.inventory, job_id)

        assert set(dialog.actual_by_usage()) == {
            int(u["id"]) for u in window.inventory.job_usages(job_id) if u["grams"] > 0
        }
        first = next(iter(dialog._spins.values()))
        first.setValue(first.maximum() + 10)
        assert first.value() == first.maximum()


class TestSettings:
    def test_preferences_are_persisted(self, window):
        settings = window.settings
        settings._threshold.setValue(250)
        custom = settings._printer.findData("custom")
        settings._printer.setCurrentIndex(custom)
        settings._slots.setValue(2)

        assert window.inventory.low_threshold() == 250
        assert window.inventory.slot_count() == 2

    def test_changing_slot_count_rebuilds_the_printer_view(self, window):
        custom = window.settings._printer.findData("custom")
        window.settings._printer.setCurrentIndex(custom)
        window.settings._slots.setValue(2)
        window.printer.refresh()

        assert len(window.printer._slot_cards) == 2

    def test_a1_mini_uses_ams_slot_labels(self, window):
        a1 = window.settings._printer.findData("bambu_a1_mini")
        window.settings._printer.setCurrentIndex(a1)
        window.refresh_all()

        assert window.inventory.slot_count() == 4
        assert not window.settings._slots.isEnabled()
        assert window.printer._title.text() == "Bambu Lab A1 mini"
        assert window.printer._slot_cards[1]._number.text() == "AMS 1"
        assert "Bambu Lab A1 mini" in window.dashboard._subtitle.text()

    def test_watch_folder_setting_reaches_the_watcher(self, window, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()

        window.settings._watch_dir.setText(str(exports))
        window.settings._watch_enabled.setChecked(True)

        assert window.watcher._watch_dir == exports

        window.settings._watch_enabled.setChecked(False)
        assert window.watcher._watch_dir is None

    def test_settings_tab_reports_hook_state(self, window):
        settings = SettingsTab(window.inventory)
        settings.refresh()

        assert settings._command.text().startswith('"')
        assert settings._presets.count() >= 1


class TestLanguage:
    def test_english_is_offered_in_settings(self, window):
        combo = window.settings._language
        codes = [combo.itemData(i) for i in range(combo.count())]
        assert codes == ["fr", "en"]
        assert combo.currentData() == "fr"

    def test_switching_to_english_retranslates_the_ui(self, window):
        combo = window.settings._language
        combo.setCurrentIndex(combo.findData("en"))

        assert db.get_setting(window.conn, "language") == "en"
        assert window.tabs.tabText(TAB_DASHBOARD) == "Dashboard"
        assert window.tabs.tabText(TAB_SETTINGS) == "Settings"
        assert window.settings._language.currentData() == "en"

    def test_language_choice_is_persisted(self, window):
        window.settings._language.setCurrentIndex(
            window.settings._language.findData("en")
        )
        window.settings.refresh()
        assert window.settings._language.currentData() == "en"


class TestNotifications:
    def test_status_bar_reports_the_deduction(self, window):
        send_job(window)
        assert "Carter moteur" in window.statusBar().currentMessage()

    def test_status_bar_reports_a_duplicate(self, window):
        send_job(window)
        send_job(window)
        assert "déjà été décompté" in window.statusBar().currentMessage()
