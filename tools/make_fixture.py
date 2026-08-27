"""Fabrique une empreinte de test à partir d'un vrai G-code.

Un export de la U1 pèse une dizaine de mégaoctets, dont l'essentiel est constitué de
trajectoires sans intérêt pour le parseur. Cet outil n'en conserve que ce qui est lu :
l'en-tête, les statistiques de filament et le bloc de configuration, tels quels.

    python tools/make_fixture.py "piece.gcode" tests/fixtures/real_u1_2_4_0.gcode

À relancer après une mise à jour de Snapmaker Orca pour reverrouiller le parseur sur
le format de la nouvelle version.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spoolmanager import gcode_parser  # noqa: E402

STUB_BODY = """
; EXECUTABLE_BLOCK_START
G90
M83
G1 X10 Y10 F3000
T0
; EXECUTABLE_BLOCK_END

"""


def build(source: Path) -> str:
    head = gcode_parser._read_head(source)
    tail = gcode_parser._read_tail(source)

    end = head.find("; HEADER_BLOCK_END")
    if end == -1:
        raise SystemExit(f"Pas de bloc d'en-tête dans {source}")
    header = "\n".join(
        line
        for line in head[: end + len("; HEADER_BLOCK_END")].splitlines()
        # La vignette encodée en base64 pèse plusieurs kilo-octets et n'est jamais lue.
        if not line.startswith("; iVBOR") and "thumbnail" not in line
    )

    stats = tail.find("; filament used [mm]")
    config = tail.find(gcode_parser.CONFIG_END)
    if stats == -1 or config == -1:
        raise SystemExit(f"Pas de statistiques ou de configuration dans {source}")

    body = tail[stats : config + len(gcode_parser.CONFIG_END)]
    return header + STUB_BODY + body + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage : make_fixture.py <gcode source> <empreinte cible>")

    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    target.write_text(build(source), encoding="utf-8")

    job = gcode_parser.parse_file(target)
    print(f"{target} : {target.stat().st_size / 1024:.0f} Ko")
    print(f"  {job.printer}, {job.total_g:.2f} g, {job.print_time}")
    for usage in job.usages:
        if usage.grams > 0:
            print(f"  emplacement {usage.slot} : {usage.grams:.2f} g de {usage.material}")


if __name__ == "__main__":
    main()
