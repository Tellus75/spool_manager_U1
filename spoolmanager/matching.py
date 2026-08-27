"""Association automatique entre un filament du tranchage et une bobine de l'étagère.

Chaque bobine candidate reçoit un score. Le signal le plus fort est l'emplacement :
si le G-code consomme le filament de l'emplacement 2 et qu'une bobine est déclarée
chargée dans l'emplacement 2 de la U1, c'est presque certainement celle-là. La matière,
le profil Orca et la couleur servent ensuite de contrôles de cohérence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .i18n import t
from .models import STATE_ARCHIVED, STATE_OPEN, ParsedUsage, Spool

# Poids de chaque indice. L'emplacement domine volontairement tous les autres.
SCORE_SLOT = 200.0
SCORE_PRESET = 100.0
SCORE_COLOR_EXACT = 50.0
SCORE_COLOR_CLOSE = 25.0
SCORE_COLOR_FAR = -25.0
SCORE_VENDOR = 20.0
SCORE_MATERIAL = 30.0
SCORE_ENOUGH_STOCK = 10.0
SCORE_NOT_ENOUGH_STOCK = -60.0
SCORE_ALREADY_OPEN = 5.0
SCORE_WRONG_SLOT = -30.0

# Seuils de déclenchement du décompte sans confirmation.
#
# Un seuil absolu élevé serait un piège : il exigerait qu'une bobine soit déclarée
# chargée dans l'imprimante pour être décomptée, alors que les emplacements ne sont
# pas toujours tenus à jour. La décision repose donc sur l'écart avec le second
# candidat : une bobine nettement devant les autres, ou seule plausible, est retenue.
MIN_PLAUSIBLE_SCORE = 35.0
AUTO_MIN_MARGIN = 40.0

COLOR_CLOSE_DISTANCE = 40.0
COLOR_FAR_DISTANCE = 120.0

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass
class Candidate:
    spool: Spool
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class Match:
    """Décision d'appariement pour un filament du tranchage."""

    usage_index: int
    usage: ParsedUsage
    candidates: list[Candidate] = field(default_factory=list)
    spool_id: int | None = None
    confidence: float = 0.0
    reason: str = ""
    automatic: bool = False

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


def _rgb(value: str) -> tuple[int, int, int] | None:
    if not value or not _HEX_RE.match(value):
        return None
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def color_distance(left: str, right: str) -> float | None:
    """Distance euclidienne entre deux couleurs RVB, ou None si l'une est inconnue."""
    first, second = _rgb(left), _rgb(right)
    if first is None or second is None:
        return None
    return sum((a - b) ** 2 for a, b in zip(first, second)) ** 0.5


def _normalise(value: str) -> str:
    return (value or "").strip().casefold()


def score_spool(usage: ParsedUsage, spool: Spool) -> Candidate | None:
    """Note une bobine face à un filament du tranchage, ou None si elle est écartée."""
    if spool.state == STATE_ARCHIVED:
        return None

    usage_material = _normalise(usage.material)
    spool_material = _normalise(spool.material)
    if usage_material and spool_material and usage_material != spool_material:
        return None

    score = 0.0
    reasons: list[str] = []

    if usage_material and usage_material == spool_material:
        score += SCORE_MATERIAL
        reasons.append(t("match.material", material=spool.material))

    if usage.slot is not None and spool.loaded_slot is not None:
        if spool.loaded_slot == usage.slot:
            score += SCORE_SLOT
            reasons.append(t("match.slot", slot=usage.slot))
        else:
            score += SCORE_WRONG_SLOT
            reasons.append(t("match.other_slot", slot=spool.loaded_slot))

    if usage.preset and spool.orca_preset:
        if _normalise(usage.preset) == _normalise(spool.orca_preset):
            score += SCORE_PRESET
            reasons.append(t("match.preset"))

    distance = color_distance(usage.color_hex, spool.color_hex)
    if distance is not None:
        if distance == 0:
            score += SCORE_COLOR_EXACT
            reasons.append(t("match.color_same"))
        elif distance <= COLOR_CLOSE_DISTANCE:
            score += SCORE_COLOR_CLOSE
            reasons.append(t("match.color_close"))
        elif distance >= COLOR_FAR_DISTANCE:
            score += SCORE_COLOR_FAR
            reasons.append(t("match.color_far"))

    if usage.vendor and _normalise(usage.vendor) == _normalise(spool.vendor):
        score += SCORE_VENDOR
        reasons.append(t("match.vendor", vendor=spool.vendor))

    if spool.remaining_g >= usage.grams:
        score += SCORE_ENOUGH_STOCK
    else:
        score += SCORE_NOT_ENOUGH_STOCK
        reasons.append(t("match.low_stock"))

    if spool.state == STATE_OPEN:
        score += SCORE_ALREADY_OPEN

    return Candidate(spool=spool, score=round(score, 2), reasons=reasons)


def _confidence(best: float, runner_up: float | None) -> float:
    """Confiance entre 0 et 1.

    L'écart avec le second candidat pèse davantage que le score brut : ce qui compte
    n'est pas d'avoir beaucoup d'indices, c'est qu'une seule bobine soit crédible.
    """
    strength = max(0.0, min(1.0, best / 250.0))
    if runner_up is None:
        separation = 1.0
    else:
        separation = max(0.0, min(1.0, (best - runner_up) / 120.0))
    return round(max(0.0, min(1.0, 0.35 * strength + 0.65 * separation)), 3)


def match_usage(usage: ParsedUsage, spools: list[Spool], usage_index: int = 0) -> Match:
    """Choisit la bobine la plus probable pour un filament donné."""
    candidates = [c for c in (score_spool(usage, s) for s in spools) if c is not None]
    candidates.sort(key=lambda c: (-c.score, c.spool.id))

    match = Match(usage_index=usage_index, usage=usage, candidates=candidates)

    if usage.grams <= 0:
        match.reason = t("match.no_usage")
        match.automatic = True
        return match

    if not candidates:
        match.reason = (
            t("match.no_material", material=usage.material)
            if usage.material
            else t("match.no_spool")
        )
        return match

    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    runner_score = runner_up.score if runner_up else None
    margin = best.score - runner_score if runner_score is not None else None

    match.confidence = _confidence(best.score, runner_score)

    if margin is not None and margin < AUTO_MIN_MARGIN:
        match.reason = (
            t("match.ambiguous", best=best.spool.display_name, other=runner_up.spool.display_name)
        )
        return match

    if best.score < MIN_PLAUSIBLE_SCORE:
        match.reason = t("match.weak", name=best.spool.display_name)
        return match

    if best.spool.remaining_g < usage.grams:
        match.reason = (
            t(
                "match.short",
                name=best.spool.display_name,
                remaining=best.spool.remaining_g,
                needed=usage.grams,
            )
        )
        return match

    match.spool_id = best.spool.id
    match.automatic = True
    match.reason = ", ".join(best.reasons)
    return match


def match_job(usages: list[ParsedUsage], spools: list[Spool]) -> list[Match]:
    """Apparie tous les filaments d'un tranchage en évitant d'utiliser deux fois la même bobine."""
    matches: list[Match] = []
    taken: set[int] = set()

    # Les consommations les plus lourdes sont arbitrées en premier : ce sont celles
    # dont une erreur d'attribution coûterait le plus cher.
    order = sorted(range(len(usages)), key=lambda i: -usages[i].grams)
    results: dict[int, Match] = {}

    for index in order:
        usage = usages[index]
        available = [s for s in spools if s.id not in taken]
        match = match_usage(usage, available, usage_index=index)
        if match.spool_id is not None:
            taken.add(match.spool_id)
        results[index] = match

    for index in range(len(usages)):
        matches.append(results[index])
    return matches


def all_resolved(matches: list[Match]) -> bool:
    """Vrai si chaque filament réellement consommé a reçu une bobine automatiquement."""
    return all(m.spool_id is not None or m.usage.grams <= 0 for m in matches)
