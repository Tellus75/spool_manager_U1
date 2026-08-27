"""Moteur de stock : bobines, mouvements et décompte des tranchages.

Le restant d'une bobine n'est jamais écrit en base. Il est toujours la somme de ses
mouvements, ce qui garantit qu'une annulation restitue exactement ce qui a été retiré
et que l'historique reste vérifiable.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import matching
from .models import (
    DEFAULT_SLOT_COUNT,
    JOB_APPLIED,
    JOB_REVERTED,
    JOB_REVIEW,
    REASON_ADJUST,
    REASON_INIT,
    REASON_PRINT,
    REASON_UNDO,
    REASON_WEIGH,
    STATE_ARCHIVED,
    STATE_EMPTY,
    STATE_NEW,
    STATE_OPEN,
    ParsedJob,
    Spool,
)

# Fenêtre pendant laquelle un même G-code n'est pas recompté, pour absorber un
# double déclenchement du hook et de la surveillance de dossier.
DEDUPE_WINDOW = timedelta(minutes=5)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DuplicateJobError(Exception):
    """Ce tranchage a déjà été enregistré très récemment."""

    def __init__(self, job_id: int):
        super().__init__(f"Tranchage déjà enregistré (job {job_id})")
        self.job_id = job_id


class Inventory:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------ filaments

    def list_filaments(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM filament ORDER BY vendor COLLATE NOCASE, name COLLATE NOCASE"
        ).fetchall()

    def get_filament(self, filament_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM filament WHERE id = ?", (filament_id,)
        ).fetchone()

    def create_filament(self, **fields: Any) -> int:
        fields.setdefault("created_at", _now())
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.conn.execute(
            f"INSERT INTO filament ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def update_filament(self, filament_id: int, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        self.conn.execute(
            f"UPDATE filament SET {assignments} WHERE id = ?",
            (*fields.values(), filament_id),
        )
        self.conn.commit()

    def delete_filament(self, filament_id: int) -> None:
        self.conn.execute("DELETE FROM filament WHERE id = ?", (filament_id,))
        self.conn.commit()

    def find_filament_by_preset(self, preset: str) -> sqlite3.Row | None:
        if not preset:
            return None
        return self.conn.execute(
            "SELECT * FROM filament WHERE orca_preset = ? COLLATE NOCASE LIMIT 1", (preset,)
        ).fetchone()

    # --------------------------------------------------------------------- bobines

    def list_spools(self, include_archived: bool = False) -> list[Spool]:
        query = "SELECT * FROM spool_view"
        if not include_archived:
            query += f" WHERE state <> '{STATE_ARCHIVED}'"
        query += " ORDER BY loaded_slot IS NULL, loaded_slot, shelf_location, id"
        return [Spool.from_row(row) for row in self.conn.execute(query)]

    def get_spool(self, spool_id: int) -> Spool | None:
        row = self.conn.execute(
            "SELECT * FROM spool_view WHERE id = ?", (spool_id,)
        ).fetchone()
        return Spool.from_row(row) if row else None

    def create_spool(
        self,
        filament_id: int,
        initial_net_g: float,
        *,
        label: str = "",
        shelf_location: str = "",
        purchase_date: str | None = None,
        state: str = STATE_NEW,
        remaining_g: float | None = None,
    ) -> int:
        """Crée une bobine et son mouvement de mise en stock.

        `remaining_g` permet de saisir une bobine déjà entamée sans fausser le
        poids initial qui sert de référence pour la jauge de remplissage.
        """
        cursor = self.conn.execute(
            "INSERT INTO spool (filament_id, label, purchase_date, initial_net_g, "
            "shelf_location, state, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                filament_id,
                label,
                purchase_date,
                initial_net_g,
                shelf_location,
                state,
                _now(),
            ),
        )
        spool_id = int(cursor.lastrowid)
        start = initial_net_g if remaining_g is None else remaining_g
        self._add_movement(spool_id, start, REASON_INIT, note="Mise en stock")
        self.conn.commit()
        return spool_id

    def update_spool(self, spool_id: int, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        self.conn.execute(
            f"UPDATE spool SET {assignments} WHERE id = ?", (*fields.values(), spool_id)
        )
        self.conn.commit()

    def delete_spool(self, spool_id: int) -> None:
        self.conn.execute("DELETE FROM spool WHERE id = ?", (spool_id,))
        self.conn.commit()

    def archive_spool(self, spool_id: int) -> None:
        self.conn.execute(
            "UPDATE spool SET state = ?, loaded_slot = NULL, archived_at = ? WHERE id = ?",
            (STATE_ARCHIVED, _now(), spool_id),
        )
        self.conn.commit()

    # ---------------------------------------------------------- emplacements U1

    def slot_count(self) -> int:
        from .db import get_setting

        try:
            return max(1, int(get_setting(self.conn, "slot_count", str(DEFAULT_SLOT_COUNT))))
        except ValueError:
            return DEFAULT_SLOT_COUNT

    def slots(self) -> dict[int, Spool | None]:
        loaded = {s.loaded_slot: s for s in self.list_spools() if s.loaded_slot}
        return {slot: loaded.get(slot) for slot in range(1, self.slot_count() + 1)}

    def load_into_slot(self, spool_id: int, slot: int) -> None:
        """Place une bobine dans un emplacement, en libérant l'occupant précédent."""
        self.conn.execute(
            "UPDATE spool SET loaded_slot = NULL WHERE loaded_slot = ?", (slot,)
        )
        self.conn.execute(
            "UPDATE spool SET loaded_slot = ? WHERE id = ?", (slot, spool_id)
        )
        self.conn.commit()

    def unload_slot(self, slot: int) -> None:
        self.conn.execute(
            "UPDATE spool SET loaded_slot = NULL WHERE loaded_slot = ?", (slot,)
        )
        self.conn.commit()

    def unload_spool(self, spool_id: int) -> None:
        self.conn.execute(
            "UPDATE spool SET loaded_slot = NULL WHERE id = ?", (spool_id,)
        )
        self.conn.commit()

    # ------------------------------------------------------------- mouvements

    def _add_movement(
        self,
        spool_id: int,
        delta_g: float,
        reason: str,
        *,
        job_id: int | None = None,
        note: str = "",
    ) -> int:
        cursor = self.conn.execute(
            "INSERT INTO stock_movement (spool_id, delta_g, reason, job_id, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (spool_id, round(delta_g, 3), reason, job_id, note, _now()),
        )
        return int(cursor.lastrowid)

    def movements(self, spool_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT m.*, j.project_name FROM stock_movement m "
            "LEFT JOIN print_job j ON j.id = m.job_id "
            "WHERE m.spool_id = ? ORDER BY m.id DESC",
            (spool_id,),
        ).fetchall()

    def weigh(self, spool_id: int, gross_g: float, note: str = "") -> float:
        """Recale le restant à partir d'un poids brut mesuré sur une balance.

        Le comptage théorique dérive toujours un peu ; la pesée fait foi.
        Renvoie l'écart appliqué, en grammes.
        """
        spool = self.get_spool(spool_id)
        if spool is None:
            raise ValueError(f"Bobine {spool_id} introuvable")

        measured_net = max(0.0, gross_g - spool.empty_spool_g)
        delta = measured_net - spool.remaining_g
        if abs(delta) < 0.01:
            return 0.0

        detail = f"Pesée {gross_g:.0f} g brut, tare {spool.empty_spool_g:.0f} g"
        self._add_movement(
            spool_id, delta, REASON_WEIGH, note=note or detail
        )
        self._refresh_state(spool_id)
        self.conn.commit()
        return round(delta, 2)

    def adjust(self, spool_id: int, delta_g: float, note: str = "") -> None:
        self._add_movement(spool_id, delta_g, REASON_ADJUST, note=note)
        self._refresh_state(spool_id)
        self.conn.commit()

    def _refresh_state(self, spool_id: int) -> None:
        """Fait suivre l'état de la bobine à son niveau de remplissage."""
        spool = self.get_spool(spool_id)
        if spool is None or spool.state == STATE_ARCHIVED:
            return

        if spool.remaining_g <= 0.5:
            new_state = STATE_EMPTY
        elif spool.remaining_g < spool.initial_net_g:
            new_state = STATE_OPEN
        else:
            new_state = spool.state if spool.state != STATE_EMPTY else STATE_OPEN

        if new_state != spool.state:
            self.conn.execute(
                "UPDATE spool SET state = ? WHERE id = ?", (new_state, spool_id)
            )

    # ------------------------------------------------------------------- jobs

    def find_recent_duplicate(self, gcode_hash: str) -> int | None:
        if not gcode_hash:
            return None
        threshold = (datetime.now() - DEDUPE_WINDOW).isoformat(timespec="seconds")
        row = self.conn.execute(
            "SELECT id FROM print_job WHERE gcode_hash = ? AND created_at >= ? "
            "ORDER BY id DESC LIMIT 1",
            (gcode_hash, threshold),
        ).fetchone()
        return int(row["id"]) if row else None

    def find_any_duplicate(self, gcode_hash: str) -> int | None:
        if not gcode_hash:
            return None
        row = self.conn.execute(
            "SELECT id FROM print_job WHERE gcode_hash = ? ORDER BY id DESC LIMIT 1",
            (gcode_hash,),
        ).fetchone()
        return int(row["id"]) if row else None

    def ingest(self, parsed: ParsedJob) -> tuple[int, str, list[matching.Match]]:
        """Enregistre un tranchage, l'apparie et décompte si la certitude est suffisante.

        Renvoie l'identifiant du job, son statut et le détail des appariements.
        """
        duplicate = (
            self.find_any_duplicate(parsed.gcode_hash)
            if parsed.source == "watch"
            else self.find_recent_duplicate(parsed.gcode_hash)
        )
        if duplicate is not None:
            raise DuplicateJobError(duplicate)

        spools = self.list_spools()
        matches = matching.match_job(parsed.usages, spools)
        status = JOB_APPLIED if matching.all_resolved(matches) else JOB_REVIEW

        job_id = self._insert_job(parsed, status)
        for match in matches:
            self._insert_usage(job_id, match)

        if status == JOB_APPLIED:
            self._apply_movements(job_id)

        self.conn.commit()
        return job_id, status, matches

    def _insert_job(self, parsed: ParsedJob, status: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO print_job (created_at, sliced_at, project_name, gcode_path, "
            "gcode_hash, printer, total_g, total_cost, print_time, status, source, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                parsed.sliced_at,
                parsed.project_name,
                parsed.gcode_path,
                parsed.gcode_hash,
                parsed.printer,
                parsed.total_g,
                parsed.total_cost,
                parsed.print_time,
                status,
                parsed.source,
                " | ".join(parsed.warnings),
            ),
        )
        return int(cursor.lastrowid)

    def _insert_usage(self, job_id: int, match: matching.Match) -> int:
        usage = match.usage
        cursor = self.conn.execute(
            "INSERT INTO job_usage (job_id, extruder_index, spool_id, grams, length_mm, "
            "volume_cm3, preset, material, color_hex, vendor, confidence, match_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                usage.slot if usage.slot is not None else usage.extruder_index,
                match.spool_id,
                usage.grams,
                usage.length_mm,
                usage.volume_cm3,
                usage.preset,
                usage.material,
                usage.color_hex,
                usage.vendor,
                match.confidence,
                match.reason,
            ),
        )
        return int(cursor.lastrowid)

    def _apply_movements(self, job_id: int) -> None:
        """Crée les retraits de stock d'un job dont toutes les bobines sont connues."""
        job = self.get_job(job_id)
        label = job["project_name"] if job else ""
        for usage in self.job_usages(job_id):
            if usage["spool_id"] is None or usage["grams"] <= 0:
                continue
            self._add_movement(
                int(usage["spool_id"]),
                -float(usage["grams"]),
                REASON_PRINT,
                job_id=job_id,
                note=label,
            )
            self._refresh_state(int(usage["spool_id"]))

    def resolve_job(self, job_id: int, assignments: dict[int, int | None]) -> None:
        """Affecte manuellement les bobines d'un job en attente puis le décompte.

        `assignments` associe l'identifiant d'une ligne `job_usage` à une bobine.
        """
        for usage_id, spool_id in assignments.items():
            self.conn.execute(
                "UPDATE job_usage SET spool_id = ?, match_reason = ?, confidence = 1.0 "
                "WHERE id = ? AND job_id = ?",
                (spool_id, "Choix manuel", usage_id, job_id),
            )

        self._apply_movements(job_id)
        self.conn.execute(
            "UPDATE print_job SET status = ? WHERE id = ?", (JOB_APPLIED, job_id)
        )
        self.conn.commit()

    def revert_job(self, job_id: int) -> None:
        """Annule un décompte en créant les mouvements inverses."""
        job = self.get_job(job_id)
        if job is None or job["status"] == JOB_REVERTED:
            return

        rows = self.conn.execute(
            "SELECT spool_id, SUM(delta_g) AS total FROM stock_movement "
            "WHERE job_id = ? AND reason = ? GROUP BY spool_id",
            (job_id, REASON_PRINT),
        ).fetchall()

        for row in rows:
            self._add_movement(
                int(row["spool_id"]),
                -float(row["total"]),
                REASON_UNDO,
                job_id=job_id,
                note=f"Annulation de « {job['project_name']} »",
            )
            self._refresh_state(int(row["spool_id"]))

        self.conn.execute(
            "UPDATE print_job SET status = ? WHERE id = ?", (JOB_REVERTED, job_id)
        )
        self.conn.commit()

    def discard_job(self, job_id: int) -> None:
        """Supprime un job en attente sans jamais toucher au stock."""
        self.conn.execute(
            "DELETE FROM print_job WHERE id = ? AND status = ?", (job_id, JOB_REVIEW)
        )
        self.conn.commit()

    def get_job(self, job_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM print_job WHERE id = ?", (job_id,)
        ).fetchone()

    def job_usages(self, job_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM job_usage WHERE job_id = ? ORDER BY extruder_index, id",
            (job_id,),
        ).fetchall()

    def list_jobs(self, statuses: Iterable[str] | None = None, limit: int = 300):
        query = "SELECT * FROM print_job"
        params: list[Any] = []
        if statuses:
            statuses = list(statuses)
            query += f" WHERE status IN ({', '.join('?' for _ in statuses)})"
            params.extend(statuses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchall()

    def pending_review_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM print_job WHERE status = ?", (JOB_REVIEW,)
        ).fetchone()
        return int(row["n"])

    # ------------------------------------------------------------ statistiques

    def stats(self) -> dict[str, float]:
        spools = [s for s in self.list_spools() if s.state != STATE_ARCHIVED]
        printed = self.conn.execute(
            "SELECT COALESCE(SUM(-delta_g), 0) AS total FROM stock_movement WHERE reason = ?",
            (REASON_PRINT,),
        ).fetchone()["total"]

        return {
            "spool_count": len(spools),
            "total_remaining_g": sum(s.remaining_g for s in spools),
            "total_value_eur": sum(s.value_eur for s in spools),
            "total_printed_g": float(printed),
            "low_count": sum(1 for s in spools if 0 < s.remaining_g <= self.low_threshold()),
            "empty_count": sum(1 for s in spools if s.remaining_g <= 0.5),
        }

    def low_threshold(self) -> float:
        from .db import get_setting

        try:
            return float(get_setting(self.conn, "low_threshold_g", "150"))
        except ValueError:
            return 150.0

    def consumption_by_material(self) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            "SELECT u.material AS material, SUM(u.grams) AS total "
            "FROM job_usage u JOIN print_job j ON j.id = u.job_id "
            "WHERE j.status = ? AND u.grams > 0 "
            "GROUP BY u.material ORDER BY total DESC",
            (JOB_APPLIED,),
        ).fetchall()
        return [(r["material"] or "Inconnu", float(r["total"])) for r in rows]
