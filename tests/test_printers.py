from spoolmanager import printers, slicers
from spoolmanager.models import DEFAULT_SLOT_COUNT


class TestPrinterCatalog:
    def test_default_is_the_u1(self):
        printer = printers.get(None)
        assert printer.id == "snapmaker_u1"
        assert printer.slot_count == 4
        assert printer.slot_kind == "tool"

    def test_a1_mini_uses_ams_labels(self):
        printer = printers.get("bambu_a1_mini")
        assert printer.slot_count == 4
        assert printer.slot_kind == "ams"
        assert printers.kind_for_gcode_printer("Bambu Lab A1 mini") == "ams"

    def test_unknown_id_falls_back_to_the_u1(self):
        assert printers.get("nope").id == "snapmaker_u1"

    def test_custom_keeps_a_free_slot_count(self, inv):
        from spoolmanager import db

        db.set_setting(inv.conn, "printer_id", printers.CUSTOM_PRINTER_ID)
        db.set_setting(inv.conn, "slot_count", "2")
        assert inv.slot_count() == 2

    def test_known_printer_ignores_stored_slot_count(self, inv):
        from spoolmanager import db

        db.set_setting(inv.conn, "printer_id", "snapmaker_u1")
        db.set_setting(inv.conn, "slot_count", "2")
        assert inv.slot_count() == 4
        assert inv.slot_count() == DEFAULT_SLOT_COUNT


class TestSlicerCatalog:
    def test_empty_enabled_list_means_all(self):
        assert slicers.parse_enabled_ids("") == [s.id for s in slicers.SLICERS]

    def test_unknown_ids_are_dropped(self):
        assert slicers.parse_enabled_ids("orca_slicer,nope") == ["orca_slicer"]

    def test_none_means_no_slicer(self):
        assert slicers.parse_enabled_ids("none") == []
