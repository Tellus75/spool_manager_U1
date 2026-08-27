"""Catalogues d'imprimantes connues.

Ajouter une machine plus tard, c'est surtout ajouter une fiche ici :
nombre d'emplacements, libellé (outil indépendant ou AMS) et noms tels
qu'ils apparaissent dans le G-code.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PRINTER_ID = "snapmaker_u1"
CUSTOM_PRINTER_ID = "custom"


@dataclass(frozen=True)
class PrinterProfile:
    id: str
    name: str
    slot_count: int
    # "tool" : emplacements indépendants (U1). "ams" : magasin unique (A1 Mini).
    slot_kind: str
    # Sur la U1, Orca n'exécute le hook qu'à l'export : il faut surveiller le temp.
    watch_slice_temp: bool
    gcode_models: tuple[str, ...] = ()


PRINTERS: tuple[PrinterProfile, ...] = (
    PrinterProfile(
        id="snapmaker_u1",
        name="Snapmaker U1",
        slot_count=4,
        slot_kind="tool",
        watch_slice_temp=True,
        gcode_models=("Snapmaker U1", "U1"),
    ),
    PrinterProfile(
        id="bambu_a1_mini",
        name="Bambu Lab A1 mini",
        slot_count=4,
        slot_kind="ams",
        watch_slice_temp=False,
        gcode_models=("Bambu Lab A1 mini", "A1 mini", "BBL A1M"),
    ),
    PrinterProfile(
        id=CUSTOM_PRINTER_ID,
        name="",
        slot_count=1,
        slot_kind="tool",
        watch_slice_temp=True,
        gcode_models=(),
    ),
)

_BY_ID = {printer.id: printer for printer in PRINTERS}


def get(printer_id: str | None) -> PrinterProfile:
    """Profil connu, ou U1 si l'identifiant est vide / inconnu."""
    if not printer_id:
        return _BY_ID[DEFAULT_PRINTER_ID]
    return _BY_ID.get(printer_id, _BY_ID[DEFAULT_PRINTER_ID])


def selectable() -> tuple[PrinterProfile, ...]:
    """Imprimantes proposées dans les réglages, y compris « autre »."""
    return PRINTERS


def display_name(printer: PrinterProfile, custom_label: str = "") -> str:
    if printer.id == CUSTOM_PRINTER_ID:
        from .i18n import t

        return custom_label or t("printer.custom")
    return printer.name


def slot_caption(slot: int, kind: str, *, compact: bool = False) -> str:
    from .i18n import t

    if kind == "ams":
        return t("card.ams" if compact else "printer.ams", slot=slot)
    return t("card.slot" if compact else "printer.slot", slot=slot)


def kind_for_gcode_printer(name: str) -> str:
    """`tool` ou `ams` d'après le nom d'imprimante lu dans le G-code."""
    needle = (name or "").casefold()
    if not needle:
        return "tool"
    for profile in PRINTERS:
        for model in profile.gcode_models:
            if model.casefold() in needle:
                return profile.slot_kind
    return "tool"
