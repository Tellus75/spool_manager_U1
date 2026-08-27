"""Diagnostic rapide de l'intégration des trancheurs sur la machine courante."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager import orca, slicers  # noqa: E402


def main() -> None:
    print(f"Trancheur detecte : {orca.is_installed()}")
    print(f"Processus ouvert  : {orca.is_orca_running()}")
    print(f"Commande du hook  : {orca.hook_command()}")

    print("\nTrancheurs :")
    for slicer in slicers.SLICERS:
        mark = "oui" if slicer.is_installed() else "non"
        print(f"  [{mark:<3}] {slicer.name:<18} {slicer.config_path()}")

    presets = orca.load_filament_presets()
    user = [p for p in presets if p.is_user]
    print(f"\nProfils filament  : {len(presets)} dont {len(user)} personnels")

    for preset in user[:20]:
        print(
            f"  [perso] {preset.name:<40} {preset.material:<8} "
            f"d={preset.density:<5} {preset.cost:>6} EUR  {preset.color_hex}"
        )

    print("\nProfils de process utilisateur :")
    for path, hooked in orca.hook_status():
        slicer = slicers.slicer_for_path(path)
        origin = f"{slicer.name} · " if slicer else ""
        print(f"  {'[HOOK]' if hooked else '[    ]'} {origin}{path.stem}")


if __name__ == "__main__":
    main()
