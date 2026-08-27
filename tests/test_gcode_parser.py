from pathlib import Path

import pytest

from spoolmanager import gcode_parser
from spoolmanager.gcode_parser import GcodeParseError, parse_file, split_config_value

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_multi_material_u1():
    job = parse_file(FIXTURES / "sample_u1_multi.gcode")

    assert job.printer == "Snapmaker U1"
    assert job.total_g == pytest.approx(18.36)
    assert job.total_cost == pytest.approx(0.46)
    assert job.print_time == "2h 14m 3s"
    assert len(job.usages) == 4


def test_usage_fields_are_aligned_per_extruder():
    job = parse_file(FIXTURES / "sample_u1_multi.gcode")
    first, second, third, fourth = job.usages

    assert (first.extruder_index, first.grams) == (0, pytest.approx(14.38))
    assert first.preset == "Snapmaker PLA Orange"
    assert first.material == "PLA"
    assert first.color_hex == "#FF6A13"
    assert first.vendor == "Snapmaker"
    assert first.density == pytest.approx(1.24)
    assert first.length_mm == pytest.approx(4821.33)
    assert first.volume_cm3 == pytest.approx(11.60)

    assert second.grams == 0.0
    assert third.material == "PETG"
    assert third.grams == pytest.approx(3.98)
    assert third.color_hex == "#1A1A1A"
    assert fourth.grams == 0.0


class TestSlotResolution:
    def test_filament_order_gives_the_slot_by_default(self):
        job = parse_file(FIXTURES / "sample_u1_multi.gcode")
        assert [u.slot for u in job.usages] == [1, 2, 3, 4]

    def test_an_explicit_permutation_is_honoured(self, tmp_path):
        gcode = tmp_path / "permute.gcode"
        gcode.write_text(
            "; filament used [g] = 1.0,2.0\n"
            "; CONFIG_BLOCK_START\n"
            "; filament_map = 2;1\n"
            "; filament_type = PLA;PETG\n"
            "; CONFIG_BLOCK_END\n"
        )
        assert [u.slot for u in parse_file(gcode).usages] == [2, 1]

    def test_a_dual_nozzle_grouping_is_ignored(self, tmp_path):
        """Sur une machine bi-buse, filament_map répartit les filaments entre deux
        nez et ses valeurs se répètent : elle ne désigne pas un emplacement."""
        gcode = tmp_path / "bibuse.gcode"
        gcode.write_text(
            "; filament used [g] = 1.0,2.0,3.0,4.0\n"
            "; CONFIG_BLOCK_START\n"
            "; filament_map = 1;2;1;2\n"
            "; filament_type = PLA;PLA;PLA;PLA\n"
            "; CONFIG_BLOCK_END\n"
        )
        assert [u.slot for u in parse_file(gcode).usages] == [1, 2, 3, 4]


class TestRealU1Export:
    """Verrouillage sur un vrai export de Snapmaker Orca 2.3.5 pour la U1.

    Ce fichier a révélé deux différences avec le format supposé : la durée n'est
    annoncée que par 'estimated printing time (normal mode)', et les vecteurs de
    nombres sont séparés par des virgules là où les chaînes le sont par des
    points-virgules.
    """

    @pytest.fixture
    def job(self):
        return parse_file(FIXTURES / "real_u1_2_3_5.gcode")

    def test_header_is_read(self, job):
        assert job.printer == "Snapmaker U1"
        assert job.print_time == "1h 56m 59s"
        assert job.total_g == pytest.approx(38.07)
        assert job.total_cost == pytest.approx(0.97)

    def test_the_four_slots_are_described(self, job):
        assert len(job.usages) == 4
        assert [u.slot for u in job.usages] == [1, 2, 3, 4]
        assert [u.grams for u in job.usages] == [pytest.approx(38.07), 0.0, 0.0, 0.0]
        assert [u.color_hex for u in job.usages] == ["#000000", "#8C9099", "#DE1619", "#000000"]

    def test_comma_separated_numbers_are_read(self, job):
        """La masse volumique est un vecteur à virgules : la découper sur le
        point-virgule seul renvoyait '1.32,1.32,1.32,1.32', donc aucune densité."""
        assert all(u.density == pytest.approx(1.32) for u in job.usages)

    def test_the_grams_match_the_volume_and_density(self, job):
        """Recoupement avec les chiffres d'Orca : 28.84 cm3 a 1.32 g/cm3 font 38.07 g."""
        used = job.usages[0]
        assert used.volume_cm3 * used.density == pytest.approx(used.grams, abs=0.05)

    def test_preset_and_vendor_are_unquoted(self, job):
        assert job.usages[0].preset == "Snapmaker PLA Matte @U1"
        assert job.usages[0].vendor == "Snapmaker"
        assert job.usages[0].material == "PLA"

    def test_a_single_colour_print_raises_no_alert(self, job):
        assert job.warnings == []


class TestRealMultiColourExport:
    """Deuxième export réel : deux couleurs, tour de purge et changements d'outil.

    Les changements sont annoncés dans le corps du fichier sous la forme
    'Change Tool2 -> Tool0', ce qui confirme que l'index du filament est bien le
    numéro d'outil, donc l'emplacement physique sur la U1.
    """

    @pytest.fixture
    def job(self):
        return parse_file(FIXTURES / "real_u1_multicolore.gcode")

    def test_two_slots_are_consumed(self, job):
        consumed = {u.slot: u.grams for u in job.usages if u.grams > 0}
        assert consumed == {1: pytest.approx(3.84), 3: pytest.approx(42.87)}

    def test_each_slot_keeps_its_own_colour(self, job):
        assert job.usages[0].color_hex == "#000000"
        assert job.usages[2].color_hex == "#DE1619"

    def test_the_purge_is_already_included_in_each_filament(self, job):
        """Le tranchage utilise une tour de purge, mais Orca n'en fait pas une ligne
        à part : la somme par filament retombe exactement sur le total annoncé."""
        assert sum(u.grams for u in job.usages) == pytest.approx(job.total_g)
        assert job.total_g == pytest.approx(46.71)

    def test_the_totals_hold_up(self, job):
        assert job.total_cost == pytest.approx(1.19)
        assert job.print_time == "2h 32m 32s"

    def test_the_two_exports_are_told_apart(self, job):
        """Deux tranchages du même modèle ne doivent pas partager d'empreinte."""
        other = parse_file(FIXTURES / "real_u1_2_3_5.gcode")
        assert job.gcode_hash != other.gcode_hash


def test_wipe_tower_is_reported_as_warning():
    job = parse_file(FIXTURES / "sample_u1_multi.gcode")
    assert any("purge" in w for w in job.warnings)


def test_parse_single_material():
    job = parse_file(FIXTURES / "sample_single.gcode")

    assert len(job.usages) == 1
    assert job.usages[0].grams == pytest.approx(6.27)
    assert job.usages[0].material == "PLA"
    assert job.warnings == []


def test_project_name_strips_gcode_suffix(tmp_path):
    source = (FIXTURES / "sample_single.gcode").read_bytes()
    target = tmp_path / "Support casque.gcode.3mf"
    target.write_bytes(source)

    assert parse_file(target).project_name == "Support casque"


def test_fingerprint_is_stable_and_content_sensitive(tmp_path):
    original = FIXTURES / "sample_single.gcode"
    copy = tmp_path / "copie.gcode"
    copy.write_bytes(original.read_bytes())
    modified = tmp_path / "modifie.gcode"
    modified.write_bytes(original.read_bytes().replace(b"6.27", b"9.99"))

    assert gcode_parser.file_fingerprint(original) == gcode_parser.file_fingerprint(copy)
    assert gcode_parser.file_fingerprint(original) != gcode_parser.file_fingerprint(modified)


def test_rejects_file_without_statistics(tmp_path):
    plain = tmp_path / "brut.gcode"
    plain.write_text("G28\nG1 X0 Y0\n")

    with pytest.raises(GcodeParseError):
        parse_file(plain)


def test_mismatched_vector_length_raises_a_warning(tmp_path):
    gcode = tmp_path / "desaligne.gcode"
    gcode.write_text(
        "; filament used [g] = 1.0,2.0,3.0\n"
        "; total filament used [g] = 6.0\n"
        "; CONFIG_BLOCK_START\n"
        '; filament_settings_id = "Generic PLA"\n'
        "; filament_type = PLA\n"
        "; CONFIG_BLOCK_END\n"
    )

    job = parse_file(gcode)
    assert len(job.usages) == 3
    assert any("incertaine" in w for w in job.warnings)


def test_tail_reading_handles_large_files(tmp_path):
    """La configuration doit être retrouvée même derrière plusieurs Mo de trajectoires."""
    big = tmp_path / "gros.gcode"
    filler = "G1 X10.5 Y20.5 E0.0231 F1800\n" * 200_000
    big.write_text(filler + (FIXTURES / "sample_single.gcode").read_text())

    job = parse_file(big)
    assert job.usages[0].grams == pytest.approx(6.27)
    assert job.printer == "Snapmaker U1"


class TestSplitConfigValue:
    def test_plain_semicolon_vector(self):
        assert split_config_value("#FFFFFF;#000000") == ["#FFFFFF", "#000000"]

    def test_quoted_entries_are_unwrapped(self):
        assert split_config_value('"Generic PLA";"Generic PETG"') == [
            "Generic PLA",
            "Generic PETG",
        ]

    def test_semicolon_inside_quotes_is_preserved(self):
        assert split_config_value('"PLA; renforcé";"PETG"') == ["PLA; renforcé", "PETG"]

    def test_single_value(self):
        assert split_config_value("1.24") == ["1.24"]

    def test_numbers_are_split_on_commas(self):
        assert gcode_parser.split_vector("filament_density", "1.32,1.32,1.27") == [
            "1.32",
            "1.32",
            "1.27",
        ]

    def test_strings_keep_their_commas(self):
        assert gcode_parser.split_vector("filament_type", "PLA, renforcé;PETG") == [
            "PLA, renforcé",
            "PETG",
        ]
