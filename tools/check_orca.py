"""Diagnostic rapide de l'intégration Orca sur la machine courante."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager import orca  # noqa: E402


def main() -> None:
    print(f"Orca detecte      : {orca.is_installed()}  ({orca.orca_dir()})")
    print(f"Orca en cours     : {orca.is_orca_running()}")
    print(f"Commande du hook  : {orca.hook_command()}")

    presets = orca.load_filament_presets()
    user = [p for p in presets if p.is_user]
    print(f"\nProfils filament  : {len(presets)} dont {len(user)} personnels")

    for preset in user:
        print(
            f"  [perso] {preset.name:<40} {preset.material:<6} "
            f"d={preset.density:<5} {preset.cost:>6} EUR  {preset.color_hex}"
        )

    snapmaker = [p for p in presets if "U1" in p.name][:8]
    print("\nQuelques profils U1 :")
    for preset in snapmaker:
        print(
            f"          {preset.name:<40} {preset.material:<6} "
            f"d={preset.density:<5} {preset.cost:>6} EUR  {preset.color_hex}"
        )

    print("\nProfils de process utilisateur :")
    for path, hooked in orca.hook_status():
        print(f"  {'[HOOK]' if hooked else '[    ]'} {path.stem}")


if __name__ == "__main__":
    main()
