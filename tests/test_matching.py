import pytest

from spoolmanager import matching
from spoolmanager.matching import color_distance, match_job, match_usage, score_spool
from spoolmanager.models import ParsedUsage


@pytest.fixture
def spools(inv, make_filament):
    """Une étagère réaliste : deux PLA de couleurs proches, un PETG, un TPU."""

    def add(net, slot=None, **overrides):
        filament_id = make_filament(**overrides)
        spool_id = inv.create_spool(filament_id, net)
        if slot:
            inv.load_into_slot(spool_id, slot)
        return spool_id

    ids = {
        "pla_orange": add(1000, slot=1, material="PLA", name="PLA Orange",
                          color_hex="#FF6A13", vendor="Snapmaker",
                          orca_preset="Snapmaker PLA Orange"),
        "pla_orange_bis": add(600, material="PLA", name="PLA Orange vif",
                              color_hex="#FF7020", vendor="Generic"),
        "petg_noir": add(800, slot=3, material="PETG", name="PETG Noir",
                         color_hex="#1A1A1A", vendor="Generic"),
        "tpu": add(400, material="TPU", name="TPU 70D", color_hex="#00A3E0"),
    }
    return ids, inv.list_spools()


class TestColorDistance:
    def test_identical(self):
        assert color_distance("#FF6A13", "#FF6A13") == 0

    def test_unknown_colour_returns_none(self):
        assert color_distance("", "#FFFFFF") is None
        assert color_distance("pas une couleur", "#FFFFFF") is None

    def test_black_and_white_are_far_apart(self):
        assert color_distance("#000000", "#FFFFFF") > 400


class TestScoring:
    def test_wrong_material_is_eliminated(self, spools):
        ids, shelf = spools
        petg = next(s for s in shelf if s.id == ids["petg_noir"])
        usage = ParsedUsage(slot=3, grams=10, material="PLA")

        assert score_spool(usage, petg) is None

    def test_slot_dominates_the_score(self, spools):
        ids, shelf = spools
        loaded = next(s for s in shelf if s.id == ids["pla_orange"])
        shelved = next(s for s in shelf if s.id == ids["pla_orange_bis"])
        usage = ParsedUsage(slot=1, grams=10, material="PLA")

        assert score_spool(usage, loaded).score > score_spool(usage, shelved).score

    def test_a_spool_in_another_slot_is_penalised(self, spools):
        ids, shelf = spools
        loaded_elsewhere = next(s for s in shelf if s.id == ids["pla_orange"])
        usage = ParsedUsage(slot=2, grams=10, material="PLA")

        candidate = score_spool(usage, loaded_elsewhere)
        assert any("autre emplacement" in r for r in candidate.reasons)

    def test_insufficient_stock_is_penalised(self, spools):
        ids, shelf = spools
        spool = next(s for s in shelf if s.id == ids["tpu"])
        usage = ParsedUsage(slot=1, grams=9999, material="TPU")

        assert any("insuffisant" in r for r in score_spool(usage, spool).reasons)


class TestAutomaticDecision:
    def test_loaded_slot_matches_without_confirmation(self, spools):
        ids, shelf = spools
        usage = ParsedUsage(slot=1, grams=25, material="PLA", color_hex="#FF6A13")

        match = match_usage(usage, shelf)

        assert match.automatic is True
        assert match.spool_id == ids["pla_orange"]
        assert match.confidence > 0.6

    def test_preset_identifies_a_shelved_spool(self, spools):
        ids, shelf = spools
        usage = ParsedUsage(
            slot=None, grams=25, material="PLA", preset="Snapmaker PLA Orange"
        )

        match = match_usage(usage, shelf)
        assert match.spool_id == ids["pla_orange"]

    def test_two_similar_spools_without_a_slot_are_ambiguous(self, inv, make_filament):
        """Deux PLA orange identiques et rien pour les départager : on demande."""
        for name in ("PLA Orange A", "PLA Orange B"):
            inv.create_spool(make_filament(name=name, color_hex="#FF6A13"), 1000)

        usage = ParsedUsage(slot=None, grams=20, material="PLA", color_hex="#FF6A13")
        match = match_usage(usage, inv.list_spools())

        assert match.automatic is False
        assert "ambigu" in match.reason.lower()

    def test_no_spool_of_that_material(self, spools):
        _, shelf = spools
        usage = ParsedUsage(slot=1, grams=20, material="ASA")

        match = match_usage(usage, shelf)
        assert match.spool_id is None
        assert "ASA" in match.reason

    def test_unused_filament_needs_no_decision(self, spools):
        _, shelf = spools
        match = match_usage(ParsedUsage(slot=2, grams=0.0, material="PLA"), shelf)

        assert match.automatic is True
        assert match.spool_id is None


class TestJobLevelMatching:
    def test_each_slot_gets_its_own_spool(self, spools):
        ids, shelf = spools
        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=14.4, material="PLA"),
            ParsedUsage(extruder_index=2, slot=3, grams=4.0, material="PETG"),
        ]

        matches = match_job(usages, shelf)

        assert matches[0].spool_id == ids["pla_orange"]
        assert matches[1].spool_id == ids["petg_noir"]
        assert matching.all_resolved(matches)

    def test_a_spool_is_never_assigned_twice(self, inv, make_filament):
        only_one = inv.create_spool(make_filament(name="PLA unique"), 1000)
        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=30, material="PLA"),
            ParsedUsage(extruder_index=1, slot=2, grams=20, material="PLA"),
        ]

        matches = match_job(usages, inv.list_spools())
        assigned = [m.spool_id for m in matches if m.spool_id is not None]

        assert assigned == [only_one]
        assert len(set(assigned)) == len(assigned)
        assert not matching.all_resolved(matches)

    def test_results_stay_in_extruder_order(self, spools):
        _, shelf = spools
        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=1.0, material="PLA"),
            ParsedUsage(extruder_index=1, slot=3, grams=99.0, material="PETG"),
        ]

        matches = match_job(usages, shelf)
        assert [m.usage_index for m in matches] == [0, 1]
