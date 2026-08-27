"""Structures de données partagées entre le parseur, les moteurs et l'interface."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

# États possibles d'une bobine.
STATE_NEW = "new"
STATE_OPEN = "open"
STATE_EMPTY = "empty"
STATE_ARCHIVED = "archived"

STATE_LABELS = {
    STATE_NEW: "Neuve",
    STATE_OPEN: "Entamée",
    STATE_EMPTY: "Vide",
    STATE_ARCHIVED: "Archivée",
}

# Raisons de mouvement de stock.
REASON_INIT = "init"
REASON_PRINT = "print"
REASON_WEIGH = "weigh"
REASON_ADJUST = "adjust"
REASON_UNDO = "undo"

REASON_LABELS = {
    REASON_INIT: "Mise en stock",
    REASON_PRINT: "Impression",
    REASON_WEIGH: "Pesée de recalage",
    REASON_ADJUST: "Correction manuelle",
    REASON_UNDO: "Annulation",
}

# Statuts d'un job tranché.
JOB_APPLIED = "applied"
JOB_REVIEW = "review"
JOB_REVERTED = "reverted"

JOB_STATUS_LABELS = {
    JOB_APPLIED: "Décompté",
    JOB_REVIEW: "À vérifier",
    JOB_REVERTED: "Annulé",
}

# Nombre d'emplacements filament de la Snapmaker U1.
DEFAULT_SLOT_COUNT = 4


def format_timestamp(value: str) -> str:
    """Affiche un horodatage ISO au format de la langue courante."""
    if not value:
        return ""
    from .i18n import t

    try:
        return datetime.fromisoformat(value).strftime(t("date.format"))
    except ValueError:
        return value.replace("T", " ")


@dataclass
class ParsedUsage:
    """Consommation d'un filament pour un tranchage, telle que lue dans le G-code."""

    extruder_index: int | None = None
    # Emplacement physique (1 à 4 sur la U1), issu de `filament_map` quand Orca le fournit.
    slot: int | None = None
    grams: float = 0.0
    length_mm: float = 0.0
    volume_cm3: float = 0.0
    preset: str = ""
    material: str = ""
    color_hex: str = ""
    vendor: str = ""
    density: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedUsage":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ParsedJob:
    """Résultat complet du parsing d'un G-code tranché par Snapmaker Orca."""

    project_name: str = ""
    gcode_path: str = ""
    gcode_hash: str = ""
    printer: str = ""
    sliced_at: str = ""
    total_g: float = 0.0
    total_cost: float = 0.0
    print_time: str = ""
    usages: list[ParsedUsage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "hook"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["usages"] = [u.to_dict() for u in self.usages]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedJob":
        known = {f for f in cls.__dataclass_fields__}
        payload = {k: v for k, v in data.items() if k in known}
        payload["usages"] = [ParsedUsage.from_dict(u) for u in data.get("usages", [])]
        return cls(**payload)


@dataclass
class Spool:
    """Vue applicative d'une bobine, jointe à son type de filament."""

    id: int
    filament_id: int
    label: str
    purchase_date: str | None
    initial_net_g: float
    shelf_location: str
    state: str
    loaded_slot: int | None
    vendor: str
    material: str
    filament_name: str
    color_name: str
    color_hex: str
    density: float
    diameter: float
    empty_spool_g: float
    price: float
    nominal_net_g: float
    orca_preset: str
    remaining_g: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Spool":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: row[k] for k in row.keys() if k in known})

    @property
    def display_name(self) -> str:
        if self.label:
            return self.label
        parts = [p for p in (self.vendor, self.filament_name) if p]
        return " ".join(parts) or f"Bobine {self.id}"

    @property
    def ratio(self) -> float:
        """Part restante entre 0 et 1, sur la base du poids net initial."""
        if self.initial_net_g <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_g / self.initial_net_g))

    @property
    def gross_g(self) -> float:
        """Poids total attendu sur la balance, bobine vide comprise."""
        return self.remaining_g + self.empty_spool_g

    @property
    def value_eur(self) -> float:
        """Valeur du filament restant, au prorata du prix d'achat."""
        if self.nominal_net_g <= 0:
            return 0.0
        return self.price * self.remaining_g / self.nominal_net_g

    @property
    def is_loaded(self) -> bool:
        return self.loaded_slot is not None
