import pytest

from spoolmanager import db, i18n
from spoolmanager.inventory import Inventory


@pytest.fixture(autouse=True)
def _french_ui():
    i18n.set_language("fr")
    yield
    i18n.set_language("fr")


@pytest.fixture(autouse=True)
def _isolate_orca_temp(tmp_path, monkeypatch):
    """Évite que les tests lisent le vrai G-code temporaire d'Orca."""
    monkeypatch.setenv("SPOOLMANAGER_SLICE_TEMP", str(tmp_path / "orca-slice-temp-unused"))


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def inv(conn):
    return Inventory(conn)


@pytest.fixture
def make_filament(inv):
    def _make(material="PLA", name="PLA Basic", color_hex="#FF6A13", **overrides):
        fields = {
            "vendor": "Snapmaker",
            "material": material,
            "name": name,
            "color_hex": color_hex,
            "color_name": "",
            "density": 1.24,
            "empty_spool_g": 220,
            "price": 25.0,
            "nominal_net_g": 1000,
            "orca_preset": "",
        }
        fields.update(overrides)
        return inv.create_filament(**fields)

    return _make


@pytest.fixture
def make_spool(inv, make_filament):
    def _make(net=1000.0, slot=None, **filament_overrides):
        filament_id = make_filament(**filament_overrides)
        spool_id = inv.create_spool(filament_id, net)
        if slot is not None:
            inv.load_into_slot(spool_id, slot)
        return spool_id

    return _make
