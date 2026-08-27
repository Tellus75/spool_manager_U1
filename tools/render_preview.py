"""Rend chaque onglet dans un PNG, pour contrôler l'aspect sans ouvrir la fenêtre."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Le moteur « offscreen » n'a pas accès aux polices installées et rend des carrés :
# on ne le force que si l'appelant le demande explicitement.
if os.environ.get("PREVIEW_OFFSCREEN") == "1":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SPOOLMANAGER_DATA_DIR"] = tempfile.mkdtemp(prefix="spool-preview-")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spoolmanager import config, db  # noqa: E402
from spoolmanager.inventory import Inventory  # noqa: E402
from spoolmanager.models import ParsedJob, ParsedUsage  # noqa: E402
from spoolmanager.ui import theme  # noqa: E402
from spoolmanager.ui.main_window import MainWindow  # noqa: E402

DEMO_FILAMENTS = [
    ("Snapmaker", "PLA", "PLA Matte", "Orange lave", "#FF6A13", 1000, 1000, "A1", 1),
    ("Snapmaker", "PLA", "PLA Matte", "Noir profond", "#1A1A1A", 1000, 612, "A2", 2),
    ("Prusament", "PETG", "PETG HF", "Blanc", "#F2F2F2", 1000, 845, "A3", 3),
    ("Sunlu", "PLA", "PLA Silk", "Bleu ciel", "#00A3E0", 1000, 118, "A4", 4),
    ("Generic", "TPU", "TPU 70D", "Rouge", "#D32F2F", 500, 500, "B1", None),
    ("Polymaker", "ASA", "ASA Pro", "Gris", "#8C9099", 1000, 74, "B2", None),
    ("Snapmaker", "PLA", "PLA SnapSpeed", "Vert menthe", "#3DD68C", 1000, 990, "B3", None),
    ("Bambu Lab", "PETG", "PETG Basic", "Jaune", "#F4EE2A", 1000, 430, "B4", None),
]


def seed(inventory: Inventory) -> None:
    for vendor, material, name, colour, hexa, net, left, shelf, slot in DEMO_FILAMENTS:
        filament_id = inventory.create_filament(
            vendor=vendor,
            material=material,
            name=name,
            color_name=colour,
            color_hex=hexa,
            density=1.24,
            empty_spool_g=220,
            price=27.9,
            nominal_net_g=net,
            orca_preset=f"{vendor} {name} @U1",
        )
        spool_id = inventory.create_spool(
            filament_id, net, shelf_location=shelf, remaining_g=left
        )
        if slot:
            inventory.load_into_slot(spool_id, slot)

    inventory.ingest(
        ParsedJob(
            project_name="Carter de drone",
            gcode_hash="demo-1",
            printer="Snapmaker U1",
            print_time="2h 14m",
            total_g=18.36,
            total_cost=0.46,
            usages=[
                ParsedUsage(extruder_index=0, slot=1, grams=14.38, material="PLA",
                            color_hex="#FF6A13"),
                ParsedUsage(extruder_index=1, slot=2, grams=3.98, material="PLA",
                            color_hex="#1A1A1A"),
            ],
        )
    )
    inventory.ingest(
        ParsedJob(
            project_name="Support d'étagère",
            gcode_hash="demo-2",
            printer="Snapmaker U1",
            print_time="46m",
            total_g=62.4,
            total_cost=1.55,
            usages=[
                ParsedUsage(extruder_index=2, slot=3, grams=62.4, material="PETG",
                            color_hex="#F2F2F2"),
            ],
        )
    )
    inventory.ingest(
        ParsedJob(
            project_name="Pièce en nylon",
            gcode_hash="demo-3",
            printer="Snapmaker U1",
            total_g=40.0,
            usages=[
                ParsedUsage(extruder_index=0, slot=1, grams=40.0, material="PA-CF"),
            ],
        )
    )


def main() -> None:
    config.ensure_dirs()
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.STYLESHEET)

    connection = db.connect()
    seed(Inventory(connection))

    window = MainWindow(connection, start_hidden=True)
    window.watcher.stop()
    window.resize(1360, 880)
    window.show()
    window.refresh_all()

    output = Path(__file__).resolve().parent.parent / "docs" / "apercu"
    output.mkdir(parents=True, exist_ok=True)

    names = ["tableau-de-bord", "bobines", "imprimante-u1", "historique", "reglages"]
    for index, name in enumerate(names):
        window.tabs.setCurrentIndex(index)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 400)
        QTimer.singleShot(0, lambda: None)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 400)
        window.grab().save(str(output / f"{name}.png"))
        print(f"écrit : {output / f'{name}.png'}")

    connection.close()


if __name__ == "__main__":
    main()
