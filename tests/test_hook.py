import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
HOOK = ROOT / "hook" / "orca_hook.py"


@pytest.fixture
def hook_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOOLMANAGER_DATA_DIR", str(tmp_path / "data"))
    sys.path.insert(0, str(ROOT / "hook"))
    from spoolmanager import config

    importlib.reload(config)
    module = importlib.import_module("orca_hook")
    importlib.reload(module)
    yield module, tmp_path / "data"
    sys.path.remove(str(ROOT / "hook"))


def test_hook_writes_job_to_inbox(hook_env):
    module, data_dir = hook_env
    gcode = FIXTURES / "sample_u1_multi.gcode"

    assert module.main(["orca_hook.py", str(gcode)]) == 0

    files = list((data_dir / "inbox").glob("*.json"))
    assert len(files) == 1

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["printer"] == "Snapmaker U1"
    assert payload["total_g"] == pytest.approx(18.36)
    assert payload["source"] == "hook"
    assert len(payload["usages"]) == 4
    assert payload["usages"][0]["preset"] == "Snapmaker PLA Orange"


def test_hook_picks_gcode_from_last_argument(hook_env):
    module, _ = hook_env
    gcode = FIXTURES / "sample_single.gcode"

    assert module.find_gcode_path(["--verbose", str(gcode)]) == gcode
    assert module.find_gcode_path(["--verbose"]) is None


def test_hook_uses_orca_output_name_for_project(hook_env, monkeypatch):
    module, data_dir = hook_env
    monkeypatch.setenv("SLIC3R_PP_OUTPUT_NAME", r"D:\Exports\Boitier capteur.gcode")

    module.main(["orca_hook.py", str(FIXTURES / "sample_single.gcode")])

    payload = json.loads(next((data_dir / "inbox").glob("*.json")).read_text(encoding="utf-8"))
    assert payload["project_name"] == "Boitier capteur"


def test_hook_never_fails_on_a_bad_file(hook_env, tmp_path):
    module, data_dir = hook_env
    broken = tmp_path / "casse.gcode"
    broken.write_text("ceci n'est pas un gcode")

    assert module.main(["orca_hook.py", str(broken)]) == 0
    assert list((data_dir / "inbox").glob("*.json")) == []
    assert "Échec" in (data_dir / "logs" / "orca_hook.log").read_text(encoding="utf-8")


def test_hook_mode_of_the_packaged_entry_point(tmp_path, monkeypatch):
    """L'exécutable packagé sert lui-même de hook via `SpoolManager.exe --hook`."""
    monkeypatch.setenv("SPOOLMANAGER_DATA_DIR", str(tmp_path / "data"))
    from spoolmanager import config
    from spoolmanager.__main__ import main

    importlib.reload(config)

    assert main(["--hook", str(FIXTURES / "sample_u1_multi.gcode")]) == 0

    files = list((tmp_path / "data" / "inbox").glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8"))["total_g"] == pytest.approx(18.36)


def test_hook_runs_as_a_real_subprocess(tmp_path):
    """Reproduit l'appel exact d'Orca : un interpréteur, le script, puis le G-code."""
    env = {
        **dict(__import__("os").environ),
        "SPOOLMANAGER_DATA_DIR": str(tmp_path / "data"),
    }
    result = subprocess.run(
        [sys.executable, str(HOOK), str(FIXTURES / "sample_u1_multi.gcode")],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert list((tmp_path / "data" / "inbox").glob("*.json"))
