"""Vérifie le parseur sur un vrai G-code tranché depuis la Snapmaker U1.

Usage :
    python tools/validate_gcode.py                     # cherche le G-code le plus récent
    python tools/validate_gcode.py "C:\\chemin\\piece.gcode"
    python tools/validate_gcode.py piece.gcode --match # simule aussi l'appariement

L'outil affiche ce que le parseur a compris, contrôle la cohérence des chiffres
(somme des grammages, masse volumique, alignement des vecteurs de configuration) et
signale les lignes du bloc de configuration qui ressemblent à du filament sans être
exploitées : c'est le meilleur moyen de repérer un format inattendu.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager import gcode_parser  # noqa: E402
from spoolmanager.gcode_parser import GcodeParseError  # noqa: E402
from spoolmanager.models import ParsedJob  # noqa: E402

SEARCH_DIRS = ("Desktop", "Downloads", "Documents", "OneDrive/Bureau", "OneDrive/Documents")
PATTERNS = ("*.gcode", "*.gcode.3mf", "*.g")


def enable_utf8_console() -> None:
    """Évite les accents illisibles quand la console tourne encore en page 850."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def find_latest_gcode() -> Path | None:
    """Le G-code modifié le plus récemment dans les dossiers d'export habituels."""
    home = Path.home()
    found: list[Path] = []
    for folder in SEARCH_DIRS:
        base = home / folder
        if not base.is_dir():
            continue
        for pattern in PATTERNS:
            found.extend(p for p in base.glob(pattern) if p.is_file())
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def check_consistency(job: ParsedJob, config: dict[str, str]) -> list[str]:
    """Contrôles croisés entre les chiffres annoncés et les chiffres recalculés."""
    problems: list[str] = []

    summed = sum(u.grams for u in job.usages)
    if job.total_g and abs(summed - job.total_g) > max(0.5, job.total_g * 0.01):
        problems.append(
            f"La somme par filament ({summed:.2f} g) s'écarte du total annoncé "
            f"({job.total_g:.2f} g)."
        )

    for usage in job.usages:
        if usage.volume_cm3 and usage.density:
            expected = usage.volume_cm3 * usage.density
            if abs(expected - usage.grams) > max(0.3, expected * 0.05):
                problems.append(
                    f"Filament {usage.extruder_index + 1} : {usage.volume_cm3:.2f} cm3 "
                    f"a {usage.density} g/cm3 donneraient {expected:.2f} g, "
                    f"le G-code annonce {usage.grams:.2f} g."
                )
        if usage.grams > 0 and not usage.material:
            problems.append(f"Filament {usage.extruder_index + 1} : matière absente.")
        if usage.grams > 0 and not usage.color_hex:
            problems.append(f"Filament {usage.extruder_index + 1} : couleur illisible.")
        if usage.grams > 0 and not usage.preset:
            problems.append(f"Filament {usage.extruder_index + 1} : profil Orca absent.")
        if usage.grams > 0 and not usage.density:
            problems.append(f"Filament {usage.extruder_index + 1} : masse volumique illisible.")

    count = len(job.usages)
    for key in ("filament_settings_id", "filament_colour", "filament_type", "filament_density"):
        if key not in config:
            problems.append(f"Clé '{key}' absente du bloc de configuration.")
            continue
        values = gcode_parser.split_vector(key, config[key])
        if len(values) not in (1, count):
            problems.append(
                f"'{key}' contient {len(values)} valeur(s) pour {count} filament(s)."
            )

    if not job.printer:
        problems.append("Modèle d'imprimante non identifié.")
    if not job.print_time:
        problems.append("Durée d'impression non identifiée.")

    return problems


def unused_filament_keys(config: dict[str, str]) -> list[str]:
    """Clés de configuration liées au filament que le parseur ignore encore."""
    known = set(gcode_parser.VECTOR_KEYS)
    interesting = {"filament_cost", "filament_ids", "filament_map_mode", "filament_diameter"}
    return sorted(
        key for key in config if key.startswith("filament") and key not in known | interesting
    )


def show_matching(job: ParsedJob) -> None:
    """Rejoue l'appariement sur l'inventaire réel, sans rien modifier."""
    from spoolmanager import db, matching
    from spoolmanager.inventory import Inventory

    conn = db.connect()
    try:
        spools = Inventory(conn).list_spools()
    finally:
        conn.close()

    print(f"\nAPPARIEMENT SIMULE ({len(spools)} bobine(s) en stock, aucune écriture)")
    if not spools:
        print("  Aucune bobine enregistrée : rien à apparier.")
        return

    for match in matching.match_job(job.usages, spools):
        usage = match.usage
        if usage.grams <= 0:
            continue
        best = match.best
        target = best.spool.display_name if best else "aucune candidate"
        verdict = "AUTO" if match.automatic else "A VERIFIER"
        print(
            f"  [{verdict:>10}] filament {usage.extruder_index + 1} "
            f"{usage.grams:>7.2f} g -> {target} "
            f"(confiance {match.confidence:.0%}) {match.reason}"
        )


def report(path: Path, with_matching: bool) -> bool:
    print(f"Fichier : {path}")
    print(f"Taille  : {path.stat().st_size / 1024 / 1024:.1f} Mo\n")

    try:
        job = gcode_parser.parse_file(path, source="validation")
    except GcodeParseError as error:
        print(f"ECHEC DU PARSING : {error}")
        return False

    config = gcode_parser.read_config_block(path)

    print(f"Projet      : {job.project_name}")
    print(f"Imprimante  : {job.printer}")
    print(f"Durée       : {job.print_time}")
    print(f"Total       : {job.total_g:.2f} g pour {job.total_cost:.2f} EUR")
    print(f"Empreinte   : {job.gcode_hash[:16]}...")

    print("\nEmpl.  Grammes   Longueur   Volume  Matière  Couleur   Marque      Profil Orca")
    for usage in job.usages:
        print(
            f"{usage.slot:>4}  {usage.grams:>8.2f} {usage.length_mm:>10.1f} "
            f"{usage.volume_cm3:>8.2f}  {usage.material or '-':<8} "
            f"{usage.color_hex or '-':<9} {(usage.vendor or '-')[:11]:<11} "
            f"{usage.preset or '-'}"
        )

    if job.warnings:
        print("\nAvertissements du parseur :")
        for warning in job.warnings:
            print(f"  - {warning}")

    problems = check_consistency(job, config)
    if problems:
        print("\nINCOHERENCES DETECTEES :")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("\nCoherence : tous les controles passent.")

    unused = unused_filament_keys(config)
    if unused:
        print("\nClés 'filament*' présentes mais non exploitées (pour information) :")
        for key in unused:
            value = config[key]
            print(f"  {key} = {value[:90]}{'...' if len(value) > 90 else ''}")

    if with_matching:
        show_matching(job)

    return not problems


def main() -> int:
    enable_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gcode", nargs="*", help="G-code à analyser")
    parser.add_argument(
        "--match",
        action="store_true",
        help="simule aussi l'appariement avec les bobines enregistrées",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.gcode]
    if not paths:
        latest = find_latest_gcode()
        if latest is None:
            print(
                "Aucun G-code trouvé dans le Bureau, les Téléchargements ou les Documents.\n"
                "Tranche une petite pièce en deux couleurs depuis Snapmaker Orca, exporte-la, "
                "puis relance cet outil (ou passe le chemin du fichier en argument)."
            )
            return 2
        print("Aucun fichier indiqué : analyse du plus récent trouvé.\n")
        paths = [latest]

    ok = True
    for index, path in enumerate(paths):
        if index:
            print("\n" + "-" * 78 + "\n")
        if not path.is_file():
            print(f"Fichier introuvable : {path}")
            ok = False
            continue
        ok = report(path, args.match) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
