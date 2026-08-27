# Recette PyInstaller. Construction : python -m PyInstaller SpoolManager.spec
#
# Volontairement en mode dossier (onedir) plutôt qu'en fichier unique : Snapmaker Orca
# appelle l'exécutable à chaque tranchage pour jouer le rôle de hook, et un exécutable
# unique devrait décompresser plusieurs dizaines de mégaoctets à chaque appel.

from pathlib import Path

project = Path(SPECPATH)

# Modules Qt inutiles ici, qui pèsent lourd dans le paquet final.
EXCLUDED = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtOpenGL",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSensors", "PySide6.QtSpatialAudio",
    "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets", "tkinter", "unittest", "pydoc_data",
]

analysis = Analysis(
    ["run.py"],
    pathex=[str(project)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED,
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="SpoolManager",
    debug=False,
    strip=False,
    upx=False,
    # Sans console : l'application est graphique et le hook doit rester silencieux
    # pour ne pas faire clignoter une fenêtre noire à chaque tranchage.
    console=False,
    icon=str(project / "docs" / "spoolmanager.ico"),
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="SpoolManager",
)
