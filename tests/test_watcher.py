import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager import config  # noqa: E402
from spoolmanager.watcher import Watcher  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOOLMANAGER_DATA_DIR", str(tmp_path / "data"))
    config.ensure_dirs()
    return tmp_path / "data"


@pytest.fixture
def watcher(app, data_dir):
    received = []
    watcher = Watcher()
    watcher.set_slice_temp_dir(None)
    watcher.job_detected.connect(received.append)
    watcher.received = received
    return watcher


def drop_in_inbox(data_dir, name="job.json", **overrides):
    payload = {
        "project_name": "Boîtier",
        "gcode_hash": "abc123",
        "total_g": 42.0,
        "printer": "Snapmaker U1",
        "source": "hook",
        "usages": [{"extruder_index": 0, "slot": 1, "grams": 42.0, "material": "PLA"}],
    }
    payload.update(overrides)
    (data_dir / "inbox" / name).write_text(json.dumps(payload), encoding="utf-8")


class TestInbox:
    def test_a_dropped_job_is_detected(self, watcher, data_dir):
        drop_in_inbox(data_dir)
        watcher.poll()

        assert len(watcher.received) == 1
        job = watcher.received[0]
        assert job.project_name == "Boîtier"
        assert job.usages[0].grams == 42.0

    def test_a_processed_file_is_archived_and_never_replayed(self, watcher, data_dir):
        drop_in_inbox(data_dir)
        watcher.poll()
        watcher.poll()

        assert len(watcher.received) == 1
        assert list((data_dir / "inbox").glob("*.json")) == []
        assert len(list((data_dir / "inbox-traites").glob("*.json"))) == 1

    def test_several_jobs_are_all_read(self, watcher, data_dir):
        drop_in_inbox(data_dir, "a.json", gcode_hash="a")
        drop_in_inbox(data_dir, "b.json", gcode_hash="b")
        watcher.poll()

        assert len(watcher.received) == 2

    def test_a_corrupt_file_is_reported_and_set_aside(self, watcher, data_dir):
        errors = []
        watcher.failed.connect(errors.append)
        (data_dir / "inbox" / "casse.json").write_text("{ pas du json")

        watcher.poll()

        assert watcher.received == []
        assert errors and "illisible" in errors[0]
        assert list((data_dir / "inbox").glob("*.json")) == []


class TestFolderWatch:
    def test_files_present_at_startup_are_not_counted(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        (exports / "ancien.gcode").write_bytes(
            (FIXTURES / "sample_single.gcode").read_bytes()
        )

        watcher.set_watch_dir(str(exports))
        watcher.poll()
        watcher.poll()

        assert watcher.received == []

    def test_a_new_file_is_detected_once_stable(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        watcher.set_watch_dir(str(exports))
        watcher.poll()

        target = exports / "nouveau.gcode"
        target.write_bytes((FIXTURES / "sample_u1_multi.gcode").read_bytes())

        # Premier sondage : le fichier est découvert, son écriture n'est pas confirmée.
        watcher.poll()
        assert watcher.received == []

        # Deuxième sondage : taille inchangée, le fichier est lu.
        watcher.poll()
        assert len(watcher.received) == 1
        assert watcher.received[0].source == "watch"
        assert watcher.received[0].total_g == pytest.approx(18.36)

    def test_a_growing_file_is_not_read_too_early(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        watcher.set_watch_dir(str(exports))
        watcher.poll()

        target = exports / "en_cours.gcode"
        target.write_bytes(b"; debut\n")
        watcher.poll()
        target.write_bytes(b"; debut\n" * 500)
        watcher.poll()

        assert watcher.received == []

    def test_the_same_file_is_read_only_once(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        watcher.set_watch_dir(str(exports))
        watcher.poll()

        (exports / "piece.gcode").write_bytes(
            (FIXTURES / "sample_single.gcode").read_bytes()
        )
        for _ in range(5):
            watcher.poll()

        assert len(watcher.received) == 1

    def test_non_gcode_files_are_ignored(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        watcher.set_watch_dir(str(exports))
        watcher.poll()

        (exports / "modele.stl").write_bytes(b"solid\n")
        watcher.poll()
        watcher.poll()

        assert watcher.received == []

    def test_changing_the_folder_resets_the_state(self, watcher, data_dir, tmp_path):
        first, second = tmp_path / "a", tmp_path / "b"
        first.mkdir()
        second.mkdir()

        watcher.set_watch_dir(str(first))
        watcher.poll()
        assert watcher._primed is True

        watcher.set_watch_dir(str(second))
        assert watcher._primed is False
        assert watcher._processed == set()

    def test_watching_can_be_turned_off(self, watcher, data_dir, tmp_path):
        exports = tmp_path / "exports"
        exports.mkdir()
        watcher.set_watch_dir(str(exports))
        watcher.poll()
        watcher.set_watch_dir(None)

        (exports / "piece.gcode").write_bytes(
            (FIXTURES / "sample_single.gcode").read_bytes()
        )
        watcher.poll()
        watcher.poll()

        assert watcher.received == []


class TestOrcaSliceTemp:
    """Pour la U1, Orca n'exécute pas le hook au tranchage : on lit le G-code temporaire."""

    def test_a_nested_temp_gcode_is_detected(self, watcher, tmp_path):
        root = tmp_path / "snapmaker_orca_model"
        metadata = root / "Thu_Aug_27" / "21_32_45#1#50" / "Metadata"
        metadata.mkdir(parents=True)
        watcher.set_slice_temp_dir(root)
        watcher.poll()

        hidden = metadata / ".11900.0.gcode"
        hidden.write_bytes((FIXTURES / "real_u1_multicolore.gcode").read_bytes())
        watcher.poll()
        watcher.poll()

        assert len(watcher.received) == 1
        assert watcher.received[0].source == "slice"
        assert watcher.received[0].total_g == pytest.approx(46.71)

    def test_files_already_there_are_not_counted(self, watcher, tmp_path):
        root = tmp_path / "snapmaker_orca_model"
        folder = root / "Metadata"
        folder.mkdir(parents=True)
        (folder / ".old.gcode").write_bytes((FIXTURES / "sample_single.gcode").read_bytes())

        watcher.set_slice_temp_dir(root)
        watcher.poll()
        watcher.poll()

        assert watcher.received == []
