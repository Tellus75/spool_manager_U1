import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_gcode  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def test_a_well_formed_gcode_passes_every_check(capsys):
    assert validate_gcode.report(FIXTURES / "sample_u1_multi.gcode", with_matching=False)

    output = capsys.readouterr().out
    assert "Snapmaker U1" in output
    assert "14.38" in output
    assert "tous les controles passent" in output


def test_an_inconsistent_total_is_reported(tmp_path, capsys):
    gcode = tmp_path / "faux.gcode"
    gcode.write_text(
        "; model printing time: 1h 0m 0s\n"
        "; filament used [g] = 10.0,10.0\n"
        "; total filament used [g] = 90.0\n"
        "; CONFIG_BLOCK_START\n"
        '; filament_settings_id = "Generic PLA";"Generic PETG"\n'
        "; filament_colour = #FFFFFF;#000000\n"
        "; filament_type = PLA;PETG\n"
        "; filament_density = 1.24;1.27\n"
        "; printer_model = Snapmaker U1\n"
        "; CONFIG_BLOCK_END\n"
    )

    assert not validate_gcode.report(gcode, with_matching=False)
    assert "s'écarte du total annoncé" in capsys.readouterr().out


def test_a_missing_configuration_key_is_reported(tmp_path, capsys):
    gcode = tmp_path / "sans_couleur.gcode"
    gcode.write_text(
        "; model printing time: 1h 0m 0s\n"
        "; filament used [g] = 10.0\n"
        "; total filament used [g] = 10.0\n"
        "; CONFIG_BLOCK_START\n"
        '; filament_settings_id = "Generic PLA"\n'
        "; filament_type = PLA\n"
        "; filament_density = 1.24\n"
        "; printer_model = Snapmaker U1\n"
        "; CONFIG_BLOCK_END\n"
    )

    assert not validate_gcode.report(gcode, with_matching=False)
    assert "filament_colour" in capsys.readouterr().out


def test_a_file_that_orca_did_not_slice_is_rejected(tmp_path, capsys):
    plain = tmp_path / "brut.gcode"
    plain.write_text("G28\nG1 X0 Y0\n")

    assert not validate_gcode.report(plain, with_matching=False)
    assert "ECHEC DU PARSING" in capsys.readouterr().out


def test_unused_filament_keys_are_listed():
    config = {
        "filament_type": "PLA",
        "filament_cost": "24.99",
        "filament_shrink": "100%",
        "printer_model": "Snapmaker U1",
    }

    assert validate_gcode.unused_filament_keys(config) == ["filament_shrink"]


@pytest.mark.parametrize("name", ["sample_u1_multi.gcode", "sample_single.gcode"])
def test_every_fixture_can_be_reported(name, capsys):
    validate_gcode.report(FIXTURES / name, with_matching=False)
    assert "ECHEC" not in capsys.readouterr().out
