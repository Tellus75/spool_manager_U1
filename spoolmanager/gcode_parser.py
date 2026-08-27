"""Lecture des statistiques de filament dans un G-code produit par Snapmaker Orca.

Format confirmé sur l'installation locale (Snapmaker_Orca.dll) :

    ; filament used [mm] = 1234.56,0.00
    ; filament used [cm3] = 2.97,0.00
    ; filament used [g] = 3.69,0.00
    ; total filament used [g] = 3.69
    ; total filament cost = 0.12
    ; CONFIG_BLOCK_START
    ; filament_settings_id = "Generic PLA";"Generic PETG"
    ; filament_colour = #FFFFFF;#1A1A1A
    ; CONFIG_BLOCK_END

Les statistiques et le bloc de configuration se trouvent en fin de fichier : on ne
lit donc que la queue du G-code, qui peut peser plusieurs centaines de mégaoctets.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

from .models import ParsedJob, ParsedUsage

CONFIG_START = "; CONFIG_BLOCK_START"
CONFIG_END = "; CONFIG_BLOCK_END"

# Taille de queue lue par essai, jusqu'à trouver le début du bloc de configuration.
_TAIL_STEPS = (256 * 1024, 2 * 1024 * 1024, 16 * 1024 * 1024, 64 * 1024 * 1024)
_HEAD_BYTES = 64 * 1024
_HASH_BYTES = 256 * 1024

# Clés du bloc de configuration exploitées pour identifier chaque filament.
VECTOR_KEYS = (
    "filament_settings_id",
    "filament_colour",
    "filament_type",
    "filament_vendor",
    "filament_density",
    "filament_map",
)

# Orca sérialise les vecteurs de nombres avec des virgules et les vecteurs de chaînes
# avec des points-virgules, dans le même bloc :
#   ; filament_density = 1.32,1.32,1.32,1.32
#   ; filament_type = PLA;PETG;PLA;PLA
# Découper les nombres sur le point-virgule seul renverrait une valeur unique illisible.
_NUMERIC_VECTOR_KEYS = frozenset({"filament_density", "filament_map", "filament_diameter"})

_STAT_PATTERNS = {
    "length_mm": re.compile(r"^;\s*filament used \[mm\]\s*[=:]\s*(.+)$", re.MULTILINE),
    "volume_cm3": re.compile(r"^;\s*filament used \[cm3\]\s*[=:]\s*(.+)$", re.MULTILINE),
    "grams": re.compile(r"^;\s*filament used \[g\]\s*[=:]\s*(.+)$", re.MULTILINE),
}
_TOTAL_G_RE = re.compile(r"^;\s*total filament used \[g\]\s*[=:]\s*([\d.]+)", re.MULTILINE)
_TOTAL_COST_RE = re.compile(r"^;\s*total filament cost\s*[=:]\s*([\d.]+)", re.MULTILINE)
_WIPE_G_RE = re.compile(
    r"^;\s*total filament used for wipe tower \[g\]\s*[=:]\s*([\d.]+)", re.MULTILINE
)
_TIME_RE = re.compile(r"^;\s*(?:model printing time|estimated printing time.*?)\s*[=:]\s*(.+)$",
                      re.MULTILINE | re.IGNORECASE)
_CONFIG_LINE_RE = re.compile(r"^;\s*([a-zA-Z0-9_]+)\s*=\s*(.*)$")


class GcodeParseError(Exception):
    """Le fichier n'est pas un G-code Orca exploitable."""


def _read_head(path: Path) -> str:
    with open(path, "rb") as fh:
        return fh.read(_HEAD_BYTES).decode("utf-8", errors="replace")


def _read_tail(path: Path) -> str:
    """Renvoie la fin du fichier, agrandie jusqu'à contenir le bloc de configuration."""
    size = path.stat().st_size
    text = ""
    for step in _TAIL_STEPS:
        with open(path, "rb") as fh:
            if size > step:
                fh.seek(size - step)
            chunk = fh.read()
        text = chunk.decode("utf-8", errors="replace")
        if CONFIG_START in text or size <= step:
            break
    return text


def file_fingerprint(path: Path) -> str:
    """Empreinte bon marché d'un G-code : taille plus fin de fichier.

    Hacher l'intégralité d'un fichier de plusieurs centaines de mégaoctets serait
    inutilement coûteux, et la queue contient déjà toute la configuration du tranchage.
    """
    size = path.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode())
    with open(path, "rb") as fh:
        if size > _HASH_BYTES:
            fh.seek(size - _HASH_BYTES)
        digest.update(fh.read(_HASH_BYTES))
    return digest.hexdigest()


def split_config_value(raw: str) -> list[str]:
    """Découpe une valeur vectorielle du bloc de configuration.

    Les vecteurs sont séparés par des points-virgules, et les chaînes peuvent être
    entre guillemets (qui peuvent eux-mêmes contenir un point-virgule).
    """
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == '"':
            if in_quotes and index + 1 < len(raw) and raw[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            in_quotes = not in_quotes
        elif char == ";" and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    parts.append("".join(current).strip())
    return parts


def split_numeric_value(raw: str) -> list[str]:
    """Découpe un vecteur de nombres, quel que soit le séparateur employé par Orca."""
    return [token.strip().strip('"') for token in re.split(r"[,;]", raw) if token.strip()]


def split_vector(key: str, raw: str) -> list[str]:
    """Découpe une valeur du bloc de configuration selon le type de la clé."""
    if key in _NUMERIC_VECTOR_KEYS:
        return split_numeric_value(raw)
    return split_config_value(raw)


def parse_config_block(text: str) -> dict[str, str]:
    """Extrait les paires clé/valeur du bloc `; CONFIG_BLOCK_START ... END`."""
    start = text.find(CONFIG_START)
    if start == -1:
        return {}
    end = text.find(CONFIG_END, start)
    block = text[start:end] if end != -1 else text[start:]

    config: dict[str, str] = {}
    for line in block.splitlines():
        match = _CONFIG_LINE_RE.match(line)
        if match:
            config[match.group(1)] = match.group(2).strip()
    return config


def _floats(raw: str) -> list[float]:
    values: list[float] = []
    for token in re.split(r"[,;]", raw):
        token = token.strip().strip('"')
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError:
            values.append(0.0)
    return values


def _normalise_hex(value: str) -> str:
    value = value.strip().strip('"')
    if not value:
        return ""
    if not value.startswith("#"):
        value = "#" + value
    # Orca peut écrire #RRGGBBAA : on ne conserve que la partie visible.
    if len(value) == 9:
        value = value[:7]
    return value.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else ""


def _resolve_slots(filament_map: list[str], count: int) -> list[int]:
    """Emplacement physique de chaque filament du tranchage.

    Sur la Snapmaker U1, dont les quatre outils sont indépendants, l'ordre des
    filaments est celui des emplacements. `filament_map` sert aux machines bi-buses
    à répartir les filaments entre deux nez : ses valeurs s'y répètent et ne
    désignent alors pas un emplacement. On ne s'y fie donc que si elle décrit bien
    des emplacements tous distincts.
    """
    default = list(range(1, count + 1))
    if len(filament_map) != count:
        return default

    try:
        mapped = [int(float(value)) for value in filament_map]
    except ValueError:
        return default

    if len(set(mapped)) != count or any(slot < 1 for slot in mapped):
        return default
    return mapped


def parse_text(text: str, head: str = "") -> ParsedJob:
    """Analyse le contenu textuel (queue du fichier) d'un G-code Orca."""
    job = ParsedJob()
    config = parse_config_block(text)

    stats: dict[str, list[float]] = {}
    for name, pattern in _STAT_PATTERNS.items():
        match = pattern.search(text)
        stats[name] = _floats(match.group(1)) if match else []

    grams = stats.get("grams") or []
    if not grams:
        raise GcodeParseError(
            "Aucune ligne '; filament used [g]' trouvée : le fichier n'a pas été "
            "tranché par Snapmaker Orca ou est tronqué."
        )

    vectors: dict[str, list[str]] = {}
    for key in VECTOR_KEYS:
        vectors[key] = split_vector(key, config[key]) if key in config else []

    def vector_at(key: str, index: int) -> str:
        values = vectors.get(key) or []
        if index < len(values):
            return values[index].strip().strip('"')
        # Orca n'écrit parfois qu'une valeur quand tous les filaments la partagent.
        if len(values) == 1:
            return values[0].strip().strip('"')
        return ""

    presets = vectors.get("filament_settings_id") or []
    if presets and len(presets) != len(grams):
        job.warnings.append(
            f"{len(grams)} valeur(s) de grammage pour {len(presets)} filament(s) "
            "configuré(s) : l'association aux emplacements est incertaine."
        )

    slots = _resolve_slots(vectors.get("filament_map") or [], len(grams))

    for index, gram in enumerate(grams):
        density_raw = vector_at("filament_density", index)
        try:
            density = float(density_raw) if density_raw else 0.0
        except ValueError:
            density = 0.0

        usage = ParsedUsage(
            extruder_index=index,
            slot=slots[index],
            grams=round(gram, 3),
            length_mm=stats["length_mm"][index] if index < len(stats["length_mm"]) else 0.0,
            volume_cm3=stats["volume_cm3"][index] if index < len(stats["volume_cm3"]) else 0.0,
            preset=vector_at("filament_settings_id", index),
            material=vector_at("filament_type", index).upper(),
            color_hex=_normalise_hex(vector_at("filament_colour", index)),
            vendor=vector_at("filament_vendor", index),
            density=density,
        )
        job.usages.append(usage)

    total_match = _TOTAL_G_RE.search(text)
    job.total_g = float(total_match.group(1)) if total_match else round(sum(grams), 3)

    cost_match = _TOTAL_COST_RE.search(text)
    job.total_cost = float(cost_match.group(1)) if cost_match else 0.0

    wipe_match = _WIPE_G_RE.search(text)
    if wipe_match and float(wipe_match.group(1)) > 0:
        job.warnings.append(
            f"Dont {float(wipe_match.group(1)):.1f} g de tour de purge, "
            "déjà inclus dans le décompte par filament."
        )

    time_match = _TIME_RE.search(head) or _TIME_RE.search(text)
    if time_match:
        # Orca écrit parfois plusieurs durées sur la même ligne, séparées par un
        # point-virgule : seule la première nous intéresse.
        job.print_time = time_match.group(1).split(";")[0].strip()

    job.printer = (
        config.get("printer_model", "").strip('"')
        or split_config_value(config.get("printer_settings_id", ""))[0].strip('"')
    )

    if not any(u.grams > 0 for u in job.usages):
        job.warnings.append("Le tranchage ne consomme aucun filament.")

    return job


def parse_file(path: str | Path, source: str = "hook") -> ParsedJob:
    """Analyse un fichier G-code sur disque et renseigne ses métadonnées."""
    path = Path(path)
    if not path.is_file():
        raise GcodeParseError(f"Fichier introuvable : {path}")

    tail = _read_tail(path)
    head = _read_head(path)
    job = parse_text(tail, head=head)

    job.gcode_path = str(path)
    job.gcode_hash = file_fingerprint(path)
    job.source = source
    job.project_name = project_name_from_path(path)
    job.sliced_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    return job


def read_config_block(path: str | Path) -> dict[str, str]:
    """Bloc de configuration brut d'un G-code, utile pour inspecter un fichier réel."""
    return parse_config_block(_read_tail(Path(path)))


def project_name_from_path(path: str | Path) -> str:
    """Nom lisible du projet, déduit du nom de fichier exporté par Orca."""
    path = Path(path)
    name = path.name
    for suffix in (".gcode.3mf", ".gcode", ".3mf"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    # Orca préfixe volontiers le nom par le profil et la durée, par ex.
    # "0.20mm_PLA_U1_1h5m.gcode" : on garde le nom tel quel, plus lisible que rien.
    return name or path.stem


def default_gcode_name() -> str:
    """Nom de sortie transmis par Orca au script de post-traitement, s'il existe."""
    return os.environ.get("SLIC3R_PP_OUTPUT_NAME", "")
