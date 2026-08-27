"""Parcours complet sur de vrais exports Snapmaker Orca 2.3.5 pour la U1.

Les empreintes `real_u1_2_3_5.gcode` (une couleur) et `real_u1_multicolore.gcode`
(deux couleurs, tour de purge) reprennent, sans les trajectoires ni la vignette, des
G-codes réellement tranchés : en-tête, statistiques et bloc de configuration d'origine.
Ces tests rejouent la chaîne entière, du hook appelé par Orca jusqu'au stock décompté.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager import config, db, hook_runner  # noqa: E402
from spoolmanager.inventory import DuplicateJobError, Inventory  # noqa: E402
from spoolmanager.models import JOB_APPLIED, ParsedJob  # noqa: E402
from spoolmanager.watcher import Watcher  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
ONE_COLOUR = FIXTURES / "real_u1_2_3_5.gcode"
TWO_COLOURS = FIXTURES / "real_u1_multicolore.gcode"


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@dataclass
class Bench:
    """Une étagère plausible et la chaîne de traitement branchée dessus."""

    inventory: Inventory
    watcher: Watcher
    black: int
    red: int
    jobs: list[ParsedJob] = field(default_factory=list)

    def slice(self, gcode: Path) -> ParsedJob:
        """Rejoue un tranchage : Orca appelle le hook, l'application relève sa boîte."""
        hook_runner.run(["orca_hook.py", str(gcode)])
        self.watcher.poll()
        return self.jobs[-1]

    def remaining(self, spool_id: int) -> float:
        return self.inventory.get_spool(spool_id).remaining_g


@pytest.fixture
def bench(app, tmp_path, monkeypatch):
    monkeypatch.setenv("SPOOLMANAGER_DATA_DIR", str(tmp_path / "data"))
    config.ensure_dirs()

    connection = db.connect(tmp_path / "app.db")
    inventory = Inventory(connection)

    def matte(name: str, color: str) -> int:
        return inventory.create_filament(
            vendor="Snapmaker",
            material="PLA",
            name=name,
            color_hex=color,
            density=1.32,
            orca_preset="Snapmaker PLA Matte @U1",
        )

    black = inventory.create_spool(matte("PLA Matte Noir", "#000000"), 1000)
    red = inventory.create_spool(matte("PLA Matte Rouge", "#DE1619"), 1000)
    inventory.load_into_slot(black, 1)
    inventory.load_into_slot(red, 3)
    inventory.create_spool(
        inventory.create_filament(
            vendor="Generic", material="PETG", name="PETG Bleu", color_hex="#00A3E0"
        ),
        1000,
    )

    bench = Bench(inventory=inventory, watcher=Watcher(), black=black, red=red)
    bench.watcher.job_detected.connect(bench.jobs.append)

    yield bench
    connection.close()


class TestSingleColourSlicing:
    def test_the_hook_files_the_job_in_the_inbox(self, bench):
        job = bench.slice(ONE_COLOUR)

        assert job.total_g == pytest.approx(38.07)
        assert job.printer == "Snapmaker U1"

    def test_the_filament_is_deducted_from_the_loaded_spool(self, bench):
        bench.inventory.ingest(bench.slice(ONE_COLOUR))

        assert bench.remaining(bench.black) == pytest.approx(961.93)

    def test_the_job_is_applied_without_review(self, bench):
        _, status, matches = bench.inventory.ingest(bench.slice(ONE_COLOUR))

        assert status == JOB_APPLIED
        assert bench.inventory.pending_review_count() == 0
        assert matches[0].automatic

    def test_the_untouched_spools_keep_their_stock(self, bench):
        bench.inventory.ingest(bench.slice(ONE_COLOUR))

        assert bench.remaining(bench.red) == 1000

    def test_undoing_restores_the_spool(self, bench):
        job_id, _, _ = bench.inventory.ingest(bench.slice(ONE_COLOUR))
        bench.inventory.revert_job(job_id)

        assert bench.remaining(bench.black) == pytest.approx(1000)

    def test_the_same_slicing_is_not_counted_twice(self, bench, tmp_path):
        bench.inventory.ingest(bench.slice(ONE_COLOUR))

        copy = tmp_path / "meme piece.gcode"
        copy.write_bytes(ONE_COLOUR.read_bytes())
        with pytest.raises(DuplicateJobError):
            bench.inventory.ingest(bench.slice(copy))

        assert bench.remaining(bench.black) == pytest.approx(961.93)


class TestMultiColourSlicing:
    def test_both_spools_are_deducted_in_one_pass(self, bench):
        bench.inventory.ingest(bench.slice(TWO_COLOURS))

        assert bench.remaining(bench.black) == pytest.approx(996.16)
        assert bench.remaining(bench.red) == pytest.approx(957.13)

    def test_each_slot_finds_its_own_spool(self, bench):
        _, status, matches = bench.inventory.ingest(bench.slice(TWO_COLOURS))

        assert status == JOB_APPLIED
        assigned = {m.usage.slot: m.spool_id for m in matches if m.usage.grams > 0}
        assert assigned == {1: bench.black, 3: bench.red}

    def test_two_colours_of_the_same_material_are_not_confused(self, bench):
        """Le noir et le rouge partagent matière, marque et profil Orca : seuls
        l'emplacement et la couleur les distinguent."""
        _, _, matches = bench.inventory.ingest(bench.slice(TWO_COLOURS))

        black_match = next(m for m in matches if m.usage.slot == 1)
        assert black_match.spool_id == bench.black
        assert black_match.confidence > 0.5

    def test_the_history_records_one_line_per_consumed_filament(self, bench):
        job_id, _, _ = bench.inventory.ingest(bench.slice(TWO_COLOURS))

        deducted = [u for u in bench.inventory.job_usages(job_id) if u["grams"] > 0]
        assert len(deducted) == 2
        assert sum(u["grams"] for u in deducted) == pytest.approx(46.71)

    def test_undoing_restores_both_spools(self, bench):
        job_id, _, _ = bench.inventory.ingest(bench.slice(TWO_COLOURS))
        bench.inventory.revert_job(job_id)

        assert bench.remaining(bench.black) == pytest.approx(1000)
        assert bench.remaining(bench.red) == pytest.approx(1000)

    def test_two_slicings_of_the_same_model_both_count(self, bench):
        """Une couleur puis deux couleurs : ce sont deux tranchages distincts."""
        bench.inventory.ingest(bench.slice(ONE_COLOUR))
        bench.inventory.ingest(bench.slice(TWO_COLOURS))

        assert bench.remaining(bench.black) == pytest.approx(958.09)
        assert bench.remaining(bench.red) == pytest.approx(957.13)
