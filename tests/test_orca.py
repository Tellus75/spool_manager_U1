import json

import pytest

from spoolmanager import orca


@pytest.fixture
def fake_orca(tmp_path, monkeypatch):
    """Reproduit l'arborescence de configuration de Snapmaker Orca."""
    root = tmp_path / "Snapmaker_Orca"
    system = root / "system" / "Snapmaker" / "filament"
    user_filament = root / "user" / "default" / "filament"
    user_process = root / "user" / "default" / "process"
    for folder in (system, user_filament, user_process):
        folder.mkdir(parents=True)

    (system / "fdm_filament_pla.json").write_text(
        json.dumps(
            {
                "name": "fdm_filament_pla",
                "instantiation": "false",
                "filament_type": ["PLA"],
                "filament_density": ["1.24"],
                "filament_diameter": ["1.75"],
            }
        )
    )
    (system / "Snapmaker PLA Matte.json").write_text(
        json.dumps(
            {
                "name": "Snapmaker PLA Matte @U1",
                "inherits": "fdm_filament_pla",
                "filament_vendor": ["Snapmaker"],
                "filament_cost": ["21.99"],
                "default_filament_colour": ["#1A1A1A"],
            }
        )
    )
    (user_filament / "TPU 70D.json").write_text(
        json.dumps(
            {
                "name": "TPU 70D",
                "inherits": "Snapmaker PLA Matte @U1",
                "filament_type": ["TPU"],
                "filament_density": ["1.26"],
                "filament_cost": ["38.99"],
            }
        )
    )
    (user_process / "0.20 Strength.json").write_text(
        json.dumps({"name": "0.20 Strength", "post_process": ""})
    )

    monkeypatch.setattr(orca.config, "orca_config_dir", lambda: root)
    return root


class TestPresetLoading:
    def test_base_profiles_are_hidden(self, fake_orca):
        names = {p.name for p in orca.load_filament_presets()}
        assert "fdm_filament_pla" not in names
        assert "Snapmaker PLA Matte @U1" in names

    def test_inherited_values_are_resolved(self, fake_orca):
        preset = next(
            p for p in orca.load_filament_presets() if p.name == "Snapmaker PLA Matte @U1"
        )
        assert preset.material == "PLA"
        assert preset.density == pytest.approx(1.24)
        assert preset.cost == pytest.approx(21.99)
        assert preset.color_hex == "#1A1A1A"
        assert preset.vendor == "Snapmaker"

    def test_child_overrides_its_parent(self, fake_orca):
        preset = next(p for p in orca.load_filament_presets() if p.name == "TPU 70D")
        assert preset.material == "TPU"
        assert preset.density == pytest.approx(1.26)
        assert preset.cost == pytest.approx(38.99)
        # Hérité du parent, non redéfini.
        assert preset.color_hex == "#1A1A1A"
        assert preset.is_user is True

    def test_user_presets_come_first(self, fake_orca):
        presets = orca.load_filament_presets()
        assert presets[0].is_user is True

    def test_missing_orca_installation_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orca.config, "orca_config_dir", lambda: tmp_path / "absent")
        assert orca.load_filament_presets() == []
        assert orca.is_installed() is False


class TestHookInstallation:
    def test_install_and_detect(self, fake_orca):
        preset = orca.user_process_presets()[0]
        assert orca.is_hooked(preset) is False

        assert orca.install_hook(preset) is True
        assert orca.is_hooked(preset) is True
        assert orca.hook_command() in orca.read_post_process(preset)

    def test_existing_scripts_are_preserved(self, fake_orca):
        preset = orca.user_process_presets()[0]
        data = json.loads(preset.read_text())
        data["post_process"] = ["autre_script.py"]
        preset.write_text(json.dumps(data))

        orca.install_hook(preset)

        scripts = orca.read_post_process(preset)
        assert "autre_script.py" in scripts
        assert len(scripts) == 2

    def test_installing_twice_does_not_duplicate(self, fake_orca):
        preset = orca.user_process_presets()[0]
        orca.install_hook(preset)
        orca.install_hook(preset)

        assert len(orca.read_post_process(preset)) == 1

    def test_uninstall_leaves_other_scripts(self, fake_orca):
        preset = orca.user_process_presets()[0]
        data = json.loads(preset.read_text())
        data["post_process"] = ["autre_script.py"]
        preset.write_text(json.dumps(data))
        orca.install_hook(preset)

        orca.uninstall_hook(preset)

        assert orca.read_post_process(preset) == ["autre_script.py"]
        assert orca.is_hooked(preset) is False

    def test_original_preset_is_backed_up(self, fake_orca):
        preset = orca.user_process_presets()[0]
        orca.install_hook(preset)

        backup = preset.with_suffix(preset.suffix + ".spoolmanager.bak")
        assert backup.exists()
        assert json.loads(backup.read_text())["post_process"] == ""

    def test_preset_stays_valid_json(self, fake_orca):
        preset = orca.user_process_presets()[0]
        orca.install_hook(preset)

        data = json.loads(preset.read_text(encoding="utf-8"))
        assert data["name"] == "0.20 Strength"

    def test_status_lists_every_user_preset(self, fake_orca):
        status = orca.hook_status()
        assert len(status) == 1
        assert status[0][1] is False


class TestHookInstalledByTheExecutable:
    """Le hook posé par l'exécutable packagé doit rester reconnu depuis les sources.

    Les deux commandes diffèrent (`SpoolManager.exe --hook` contre
    `python.exe orca_hook.py`) : les confondre ferait croire à un profil dépourvu de
    hook, et un second y serait ajouté.
    """

    EXE_HOOK = '"C:\\Programmes\\SpoolManager\\SpoolManager.exe" --hook'

    def equip(self, preset, command=EXE_HOOK):
        data = json.loads(preset.read_text())
        data["post_process"] = [command]
        preset.write_text(json.dumps(data))

    def test_it_is_detected(self, fake_orca):
        preset = orca.user_process_presets()[0]
        self.equip(preset)

        assert orca.is_hooked(preset) is True

    def test_reinstalling_replaces_it_instead_of_adding_a_second(self, fake_orca):
        preset = orca.user_process_presets()[0]
        self.equip(preset)

        orca.install_hook(preset)

        scripts = orca.read_post_process(preset)
        assert scripts == [orca.hook_command()]

    def test_it_can_be_removed(self, fake_orca):
        preset = orca.user_process_presets()[0]
        self.equip(preset)

        orca.uninstall_hook(preset)

        assert orca.read_post_process(preset) == []

    def test_someone_elses_script_is_left_alone(self, fake_orca):
        """Un script tiers ne doit être ni reconnu comme le nôtre, ni supprimé."""
        preset = orca.user_process_presets()[0]
        self.equip(preset, "autre_outil.exe --hook")

        assert orca.is_hooked(preset) is False

        orca.uninstall_hook(preset)
        assert orca.read_post_process(preset) == ["autre_outil.exe --hook"]


def test_hook_command_quotes_paths():
    command = orca.hook_command()
    assert command.startswith('"')
    assert command.count('"') >= 2
