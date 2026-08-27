import pytest

from spoolmanager.inventory import DuplicateJobError
from spoolmanager.models import (
    JOB_APPLIED,
    JOB_REVERTED,
    JOB_REVIEW,
    STATE_EMPTY,
    STATE_NEW,
    STATE_OPEN,
    ParsedJob,
    ParsedUsage,
)


def job(usages, **overrides):
    payload = {
        "project_name": "Pièce test",
        "gcode_hash": "hash-" + str(abs(hash(str(usages)))),
        "printer": "Snapmaker U1",
        "total_g": sum(u.grams for u in usages),
        "usages": usages,
    }
    payload.update(overrides)
    return ParsedJob(**payload)


class TestSpoolLifecycle:
    def test_new_spool_starts_full(self, inv, make_spool):
        spool = inv.get_spool(make_spool(net=1000))
        assert spool.remaining_g == 1000
        assert spool.state == STATE_NEW
        assert spool.ratio == 1.0

    def test_partially_used_spool_can_be_registered(self, inv, make_filament):
        filament_id = make_filament()
        spool = inv.get_spool(inv.create_spool(filament_id, 1000, remaining_g=420))

        assert spool.remaining_g == 420
        # Le poids initial reste la référence de la jauge.
        assert spool.initial_net_g == 1000
        assert spool.ratio == pytest.approx(0.42)

    def test_gross_weight_includes_the_tare(self, inv, make_spool):
        spool = inv.get_spool(make_spool(net=800, empty_spool_g=215))
        assert spool.gross_g == 1015

    def test_remaining_value_is_prorated(self, inv, make_spool):
        spool = inv.get_spool(make_spool(net=1000, price=30.0, nominal_net_g=1000))
        inv.adjust(spool.id, -500, "essai")
        assert inv.get_spool(spool.id).value_eur == pytest.approx(15.0)


class TestSlots:
    def test_loading_a_slot_evicts_the_previous_spool(self, inv, make_spool):
        first, second = make_spool(), make_spool()
        inv.load_into_slot(first, 2)
        inv.load_into_slot(second, 2)

        assert inv.get_spool(first).loaded_slot is None
        assert inv.get_spool(second).loaded_slot == 2

    def test_slots_returns_every_position(self, inv, make_spool):
        inv.load_into_slot(make_spool(), 3)
        slots = inv.slots()

        assert sorted(slots) == [1, 2, 3, 4]
        assert slots[3] is not None
        assert slots[1] is None

    def test_unload(self, inv, make_spool):
        spool_id = make_spool(slot=1)
        inv.unload_slot(1)
        assert inv.get_spool(spool_id).loaded_slot is None


class TestWeighing:
    def test_weighing_corrects_the_drift(self, inv, make_spool):
        spool_id = make_spool(net=1000, empty_spool_g=220)
        inv.adjust(spool_id, -100, "impression théorique")

        # La balance annonce 1050 g brut, soit 830 g net au lieu des 900 g comptés.
        delta = inv.weigh(spool_id, 1050)

        assert delta == pytest.approx(-70)
        assert inv.get_spool(spool_id).remaining_g == pytest.approx(830)

    def test_weighing_can_add_back(self, inv, make_spool):
        spool_id = make_spool(net=1000, empty_spool_g=220)
        inv.adjust(spool_id, -500, "")
        inv.weigh(spool_id, 940)
        assert inv.get_spool(spool_id).remaining_g == pytest.approx(720)

    def test_identical_weight_creates_no_movement(self, inv, make_spool):
        spool_id = make_spool(net=1000, empty_spool_g=220)
        assert inv.weigh(spool_id, 1220) == 0.0
        assert len(inv.movements(spool_id)) == 1


class TestStateTransitions:
    def test_spool_becomes_open_then_empty(self, inv, make_spool):
        spool_id = make_spool(net=100)
        inv.adjust(spool_id, -40, "")
        assert inv.get_spool(spool_id).state == STATE_OPEN

        inv.adjust(spool_id, -60, "")
        assert inv.get_spool(spool_id).state == STATE_EMPTY

    def test_refilling_an_empty_spool_reopens_it(self, inv, make_spool):
        spool_id = make_spool(net=100)
        inv.adjust(spool_id, -100, "")
        inv.weigh(spool_id, 320)
        assert inv.get_spool(spool_id).state == STATE_OPEN


class TestJobIngestion:
    def test_confident_job_is_deducted_immediately(self, inv, make_spool):
        spool_id = make_spool(net=1000, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=25.0, material="PLA")

        job_id, status, _ = inv.ingest(job([usage]))

        assert status == JOB_APPLIED
        assert inv.get_spool(spool_id).remaining_g == pytest.approx(975)
        assert inv.job_usages(job_id)[0]["spool_id"] == spool_id

    def test_multi_material_job_hits_each_slot(self, inv, make_spool):
        pla = make_spool(net=1000, slot=1, material="PLA")
        petg = make_spool(net=1000, slot=3, material="PETG", color_hex="#1A1A1A")

        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=14.38, material="PLA"),
            ParsedUsage(extruder_index=1, slot=2, grams=0.0, material="PLA"),
            ParsedUsage(extruder_index=2, slot=3, grams=3.98, material="PETG"),
        ]
        _, status, _ = inv.ingest(job(usages))

        assert status == JOB_APPLIED
        assert inv.get_spool(pla).remaining_g == pytest.approx(985.62)
        assert inv.get_spool(petg).remaining_g == pytest.approx(996.02)

    def test_unmatchable_job_goes_to_review_without_touching_stock(self, inv, make_spool):
        spool_id = make_spool(net=1000, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=20.0, material="ABS")

        job_id, status, _ = inv.ingest(job([usage]))

        assert status == JOB_REVIEW
        assert inv.get_spool(spool_id).remaining_g == 1000
        assert inv.pending_review_count() == 1

    def test_partial_match_puts_the_whole_job_in_review(self, inv, make_spool):
        """Un décompte à moitié appliqué serait incompréhensible : tout ou rien."""
        pla = make_spool(net=1000, slot=1, material="PLA")
        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=10.0, material="PLA"),
            ParsedUsage(extruder_index=1, slot=2, grams=5.0, material="ASA"),
        ]

        _, status, _ = inv.ingest(job(usages))

        assert status == JOB_REVIEW
        assert inv.get_spool(pla).remaining_g == 1000

    def test_zero_gram_filament_needs_no_spool(self, inv, make_spool):
        make_spool(net=1000, slot=1, material="PLA")
        usages = [
            ParsedUsage(extruder_index=0, slot=1, grams=10.0, material="PLA"),
            ParsedUsage(extruder_index=1, slot=2, grams=0.0, material="PETG"),
        ]

        _, status, _ = inv.ingest(job(usages))
        assert status == JOB_APPLIED

    def test_job_larger_than_the_spool_goes_to_review(self, inv, make_spool):
        make_spool(net=50, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=200.0, material="PLA")

        _, status, matches = inv.ingest(job([usage]))

        assert status == JOB_REVIEW
        assert "insuffisant" in matches[0].reason or "que" in matches[0].reason


class TestDeduplication:
    def test_same_file_seen_twice_by_the_watcher_counts_once(self, inv, make_spool):
        make_spool(net=1000, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=10.0, material="PLA")
        parsed = job([usage], gcode_hash="abc", source="watch")

        inv.ingest(parsed)
        with pytest.raises(DuplicateJobError):
            inv.ingest(job([usage], gcode_hash="abc", source="watch"))

    def test_hook_refuses_an_immediate_repeat(self, inv, make_spool):
        make_spool(net=1000, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=10.0, material="PLA")

        inv.ingest(job([usage], gcode_hash="xyz", source="hook"))
        with pytest.raises(DuplicateJobError):
            inv.ingest(job([usage], gcode_hash="xyz", source="hook"))


class TestReviewAndUndo:
    def test_resolving_a_pending_job_applies_the_deduction(self, inv, make_spool):
        spool_id = make_spool(net=1000, material="PETG")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=30.0, material="ABS")
        job_id, status, _ = inv.ingest(job([usage]))
        assert status == JOB_REVIEW

        usage_row = inv.job_usages(job_id)[0]
        inv.resolve_job(job_id, {usage_row["id"]: spool_id})

        assert inv.get_job(job_id)["status"] == JOB_APPLIED
        assert inv.get_spool(spool_id).remaining_g == pytest.approx(970)

    def test_undo_restores_the_exact_amount(self, inv, make_spool):
        spool_id = make_spool(net=1000, slot=1, material="PLA")
        usage = ParsedUsage(extruder_index=0, slot=1, grams=37.42, material="PLA")
        job_id, _, _ = inv.ingest(job([usage]))

        inv.revert_job(job_id)

        assert inv.get_spool(spool_id).remaining_g == pytest.approx(1000)
        assert inv.get_job(job_id)["status"] == JOB_REVERTED

    def test_undo_is_idempotent(self, inv, make_spool):
        spool_id = make_spool(net=1000, slot=1, material="PLA")
        job_id, _, _ = inv.ingest(
            job([ParsedUsage(extruder_index=0, slot=1, grams=50.0, material="PLA")])
        )

        inv.revert_job(job_id)
        inv.revert_job(job_id)

        assert inv.get_spool(spool_id).remaining_g == pytest.approx(1000)

    def test_discarding_a_pending_job_leaves_stock_untouched(self, inv, make_spool):
        spool_id = make_spool(net=1000, material="PLA")
        job_id, _, _ = inv.ingest(
            job([ParsedUsage(extruder_index=0, slot=1, grams=10.0, material="ABS")])
        )

        inv.discard_job(job_id)

        assert inv.get_job(job_id) is None
        assert inv.get_spool(spool_id).remaining_g == 1000

    def test_history_keeps_every_movement(self, inv, make_spool):
        spool_id = make_spool(net=1000, slot=1, material="PLA")
        job_id, _, _ = inv.ingest(
            job([ParsedUsage(extruder_index=0, slot=1, grams=20.0, material="PLA")])
        )
        inv.revert_job(job_id)

        reasons = [m["reason"] for m in inv.movements(spool_id)]
        assert reasons == ["undo", "print", "init"]


class TestStats:
    def test_totals(self, inv, make_spool):
        make_spool(net=1000, price=25.0)
        make_spool(net=500, price=25.0)

        stats = inv.stats()
        assert stats["spool_count"] == 2
        assert stats["total_remaining_g"] == 1500
        assert stats["total_value_eur"] == pytest.approx(37.5)

    def test_printed_total_and_material_breakdown(self, inv, make_spool):
        make_spool(net=1000, slot=1, material="PLA")
        inv.ingest(job([ParsedUsage(extruder_index=0, slot=1, grams=12.0, material="PLA")]))

        assert inv.stats()["total_printed_g"] == pytest.approx(12.0)
        assert inv.consumption_by_material() == [("PLA", 12.0)]
