"""Accès SQLite : connexion, schéma et migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE filament (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor        TEXT    NOT NULL DEFAULT '',
        material      TEXT    NOT NULL,
        name          TEXT    NOT NULL,
        color_name    TEXT    NOT NULL DEFAULT '',
        color_hex     TEXT    NOT NULL DEFAULT '#9E9E9E',
        density       REAL    NOT NULL DEFAULT 1.24,
        diameter      REAL    NOT NULL DEFAULT 1.75,
        empty_spool_g REAL    NOT NULL DEFAULT 220,
        price         REAL    NOT NULL DEFAULT 0,
        nominal_net_g REAL    NOT NULL DEFAULT 1000,
        orca_preset   TEXT    NOT NULL DEFAULT '',
        notes         TEXT    NOT NULL DEFAULT '',
        created_at    TEXT    NOT NULL
    );

    CREATE TABLE spool (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        filament_id    INTEGER NOT NULL REFERENCES filament(id) ON DELETE CASCADE,
        label          TEXT    NOT NULL DEFAULT '',
        purchase_date  TEXT,
        initial_net_g  REAL    NOT NULL,
        shelf_location TEXT    NOT NULL DEFAULT '',
        state          TEXT    NOT NULL DEFAULT 'new',
        loaded_slot    INTEGER,
        created_at     TEXT    NOT NULL,
        archived_at    TEXT
    );

    -- Un seul rouleau à la fois dans un emplacement donné de l'imprimante.
    CREATE UNIQUE INDEX idx_spool_slot ON spool(loaded_slot) WHERE loaded_slot IS NOT NULL;
    CREATE INDEX idx_spool_filament ON spool(filament_id);

    CREATE TABLE print_job (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at     TEXT    NOT NULL,
        sliced_at      TEXT    NOT NULL DEFAULT '',
        project_name   TEXT    NOT NULL DEFAULT '',
        gcode_path     TEXT    NOT NULL DEFAULT '',
        gcode_hash     TEXT    NOT NULL DEFAULT '',
        printer        TEXT    NOT NULL DEFAULT '',
        total_g        REAL    NOT NULL DEFAULT 0,
        total_cost     REAL    NOT NULL DEFAULT 0,
        print_time     TEXT    NOT NULL DEFAULT '',
        status         TEXT    NOT NULL DEFAULT 'applied',
        source         TEXT    NOT NULL DEFAULT 'hook',
        note           TEXT    NOT NULL DEFAULT ''
    );

    -- Index non unique : re-trancher volontairement le même modèle doit pouvoir
    -- être décompté deux fois. La déduplication est décidée à l'ingestion.
    CREATE INDEX idx_job_hash ON print_job(gcode_hash);
    CREATE INDEX idx_job_status ON print_job(status);

    CREATE TABLE job_usage (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id         INTEGER NOT NULL REFERENCES print_job(id) ON DELETE CASCADE,
        extruder_index INTEGER,
        spool_id       INTEGER REFERENCES spool(id) ON DELETE SET NULL,
        grams          REAL    NOT NULL DEFAULT 0,
        length_mm      REAL    NOT NULL DEFAULT 0,
        volume_cm3     REAL    NOT NULL DEFAULT 0,
        preset         TEXT    NOT NULL DEFAULT '',
        material       TEXT    NOT NULL DEFAULT '',
        color_hex      TEXT    NOT NULL DEFAULT '',
        vendor         TEXT    NOT NULL DEFAULT '',
        confidence     REAL    NOT NULL DEFAULT 0,
        match_reason   TEXT    NOT NULL DEFAULT ''
    );

    CREATE INDEX idx_usage_job ON job_usage(job_id);
    CREATE INDEX idx_usage_spool ON job_usage(spool_id);

    CREATE TABLE stock_movement (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        spool_id   INTEGER NOT NULL REFERENCES spool(id) ON DELETE CASCADE,
        delta_g    REAL    NOT NULL,
        reason     TEXT    NOT NULL,
        job_id     INTEGER REFERENCES print_job(id) ON DELETE SET NULL,
        note       TEXT    NOT NULL DEFAULT '',
        created_at TEXT    NOT NULL
    );

    CREATE INDEX idx_movement_spool ON stock_movement(spool_id);
    CREATE INDEX idx_movement_job ON stock_movement(job_id);

    CREATE TABLE setting (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    -- Le restant d'une bobine n'est jamais stocké : il est toujours recalculé
    -- depuis ses mouvements, ce qui rend l'historique auditable et l'annulation exacte.
    CREATE VIEW spool_view AS
    SELECT
        s.id, s.filament_id, s.label, s.purchase_date, s.initial_net_g,
        s.shelf_location, s.state, s.loaded_slot, s.created_at, s.archived_at,
        f.vendor, f.material, f.name AS filament_name, f.color_name, f.color_hex,
        f.density, f.diameter, f.empty_spool_g, f.price, f.nominal_net_g,
        f.orca_preset, f.notes,
        COALESCE((SELECT SUM(m.delta_g) FROM stock_movement m WHERE m.spool_id = s.id), 0)
            AS remaining_g
    FROM spool s
    JOIN filament f ON f.id = s.filament_id;
    """,
}


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Ouvre la base, applique les migrations manquantes et renvoie la connexion."""
    if path is None:
        config.ensure_dirs()
        path = config.db_path()
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current + 1, SCHEMA_VERSION + 1):
        conn.executescript(_MIGRATIONS[version])
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO setting(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
