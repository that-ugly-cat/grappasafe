import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os

DB_PATH = Path(os.getenv("GRAPPASAFE_DB", "grappasafe.db"))


def _conn(db_path=None):
    con = sqlite3.connect(db_path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT UNIQUE NOT NULL,
            password_hash       TEXT NOT NULL,
            nome                TEXT NOT NULL,
            cognome             TEXT NOT NULL,
            telefono            TEXT,
            emergenza_contatto  TEXT,
            emergenza_telefono  TEXT,
            gruppo_sanguigno    TEXT,
            note_salute         TEXT,
            flarm_id            TEXT UNIQUE,
            lingua              TEXT NOT NULL DEFAULT 'it',
            share_token         TEXT UNIQUE NOT NULL,
            role                TEXT NOT NULL DEFAULT 'user',
            created_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            attivita    TEXT NOT NULL,
            started_at  TEXT DEFAULT (datetime('now')),
            ended_at    TEXT,
            state       TEXT NOT NULL DEFAULT 'GROUND'
        );

        CREATE TABLE IF NOT EXISTS gps_points (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            ts              TEXT NOT NULL,
            lat             REAL NOT NULL,
            lon             REAL NOT NULL,
            alt_m           REAL,
            accuracy_m      REAL,
            battery_pct     INTEGER,
            speed_kmh       REAL,
            vspeed_ms       REAL,
            motion_state    TEXT,
            impact_detected INTEGER DEFAULT 0,
            accel_magnitude REAL
        );

        CREATE INDEX IF NOT EXISTS idx_gps_session_ts ON gps_points (session_id, ts DESC);

        CREATE TABLE IF NOT EXISTS ogn_beacons (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ogn_id          TEXT NOT NULL,
            display_name    TEXT,
            ts              TEXT NOT NULL,
            lat             REAL,
            lon             REAL,
            alt_m           REAL,
            speed_kmh       REAL,
            vspeed_ms       REAL,
            course_deg      REAL,
            aircraft_type   INTEGER,
            linked_user_id  INTEGER REFERENCES users(id),
            state           TEXT NOT NULL DEFAULT 'UNKNOWN'
        );

        CREATE INDEX IF NOT EXISTS idx_ogn_id_ts ON ogn_beacons (ogn_id, ts DESC);

        CREATE TABLE IF NOT EXISTS emergencies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER REFERENCES sessions(id),
            ogn_beacon_id   INTEGER REFERENCES ogn_beacons(id),
            user_id         INTEGER REFERENCES users(id),
            trigger         TEXT NOT NULL,
            ts              TEXT DEFAULT (datetime('now')),
            lat             REAL,
            lon             REAL,
            alt_m           REAL,
            acknowledged_at TEXT,
            acknowledged_by INTEGER REFERENCES users(id),
            resolved_at     TEXT,
            resolved_by     INTEGER REFERENCES users(id),
            note            TEXT
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            emergency_id    INTEGER NOT NULL REFERENCES emergencies(id),
            channel         TEXT NOT NULL,
            recipient       TEXT NOT NULL,
            sent_at         TEXT DEFAULT (datetime('now')),
            success         INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS config (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            tipo        TEXT NOT NULL DEFAULT 'float',
            macchina    TEXT,                            -- SM | EM
            categoria   TEXT,                            -- volo | terrestre | comune
            descrizione TEXT,
            aggiornato  TEXT DEFAULT (datetime('now'))
        );

        -- Emergency rules, one row per trigger. Each rule can be toggled,
        -- scoped to a set of activities, and run immediately or as pending.
        CREATE TABLE IF NOT EXISTS emergency_rules (
            key         TEXT PRIMARY KEY,                -- AUTO_CHUTE | SIGNAL_LOST | AUTO_IMPACT | AUTO_IMMOBILE
            enabled     INTEGER NOT NULL DEFAULT 1,
            applies_to  TEXT NOT NULL DEFAULT '',        -- CSV of activity codes
            mode        TEXT NOT NULL DEFAULT 'immediate', -- immediate | pending
            aggiornato  TEXT DEFAULT (datetime('now'))
        );

        -- OGN/FLARM devices linked to a user (self-managed from the web).
        -- A user can register several devices (wing, reserve with FLARM, etc.).
        -- ogn_id is the beacon address (hex address or device id), used to
        -- resolve an OGN beacon back to its owner's identity.
        CREATE TABLE IF NOT EXISTS devices (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            display_name  TEXT NOT NULL,
            ogn_id        TEXT,
            activity      TEXT,
            color         TEXT NOT NULL DEFAULT '#3b82f6',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_devices_ogn   ON devices (ogn_id);
        CREATE INDEX IF NOT EXISTS idx_devices_owner ON devices (owner_user_id);
    """)
    con.commit()

    # Migration: link an emergency directly to its user, so a manual SOS
    # without an active session still carries the subject's identity.
    cols = [r["name"] for r in con.execute("PRAGMA table_info(emergencies)").fetchall()]
    if "user_id" not in cols:
        con.execute("ALTER TABLE emergencies ADD COLUMN user_id INTEGER REFERENCES users(id)")
        con.commit()
    # Migration: an operator can take an emergency in charge (acknowledge)
    # before resolving it, so the person in distress gets a "seen" signal.
    if "acknowledged_at" not in cols:
        con.execute("ALTER TABLE emergencies ADD COLUMN acknowledged_at TEXT")
        con.execute("ALTER TABLE emergencies ADD COLUMN acknowledged_by INTEGER REFERENCES users(id)")
        con.commit()

    _seed_config(con)
    _seed_rules(con)
    con.close()


def _seed_config(con):
    """Insert the default config values if they are not present yet."""
    from core.emergency import EmConfig, CONFIG_META
    defaults = EmConfig()
    for key, macchina, categoria, descrizione, tipo in CONFIG_META:
        value = str(getattr(defaults, key))
        con.execute("""
            INSERT OR IGNORE INTO config (key, value, tipo, macchina, categoria, descrizione)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (key, value, tipo, macchina, categoria, descrizione))
    # Message shown on the user's phone while an emergency is open (editable
    # from the admin config panel; the app also caches it and has a fallback).
    con.execute("""
        INSERT OR IGNORE INTO config (key, value, tipo, macchina, categoria, descrizione)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "emergency_user_message",
        "Resta dove sei, i soccorsi sono in arrivo.",
        "text", "APP", "app",
        "Messaggio mostrato sul telefono durante un'emergenza in corso",
    ))
    con.commit()


def _seed_rules(con):
    """Insert the default emergency rules if they are not present yet."""
    from core.emergency import RULE_DEFAULTS
    for key, enabled, applies_to, mode in RULE_DEFAULTS:
        con.execute("""
            INSERT OR IGNORE INTO emergency_rules (key, enabled, applies_to, mode)
            VALUES (?, ?, ?, ?)
        """, (key, enabled, applies_to, mode))
    con.commit()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, password_hash, nome, cognome, **kwargs):
    con = _conn()
    token = str(uuid.uuid4())
    cur = con.execute("""
        INSERT INTO users (username, password_hash, nome, cognome,
            telefono, emergenza_contatto, emergenza_telefono,
            gruppo_sanguigno, note_salute, flarm_id, lingua, share_token, role)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        username, password_hash, nome, cognome,
        kwargs.get("telefono"), kwargs.get("emergenza_contatto"),
        kwargs.get("emergenza_telefono"), kwargs.get("gruppo_sanguigno"),
        kwargs.get("note_salute"), kwargs.get("flarm_id"),
        kwargs.get("lingua", "it"), token,
        kwargs.get("role", "user"),
    ))
    con.commit()
    uid = cur.lastrowid
    con.close()
    return uid


def get_user_by_username(username):
    con = _conn()
    row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    con = _conn()
    row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_user_by_share_token(token):
    con = _conn()
    row = con.execute("SELECT * FROM users WHERE share_token=?", (token,)).fetchone()
    con.close()
    return dict(row) if row else None


def update_user_profile(user_id, **fields):
    allowed = {"nome", "cognome", "telefono", "emergenza_contatto",
               "emergenza_telefono", "gruppo_sanguigno", "note_salute",
               "flarm_id", "lingua"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k}=?" for k in updates)
    con = _conn()
    con.execute(f"UPDATE users SET {sets} WHERE id=?", (*updates.values(), user_id))
    con.commit()
    con.close()


def update_user_password(user_id, password_hash):
    con = _conn()
    con.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))
    con.commit()
    con.close()


def get_all_users():
    con = _conn()
    rows = con.execute("SELECT * FROM users ORDER BY cognome, nome").fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_user(user_id):
    con = _conn()
    con.execute("DELETE FROM users WHERE id=?", (user_id,))
    con.commit()
    con.close()


def get_user(user_id):
    """Explicit alias for get_user_by_id, used by the admin API."""
    return get_user_by_id(user_id)


def update_user_full(user_id, *, username, nome, cognome, role,
                     password_hash=None, telefono=None, gruppo_sanguigno=None,
                     emergenza_contatto=None, emergenza_telefono=None,
                     flarm_id=None, lingua="it", note_salute=None):
    """Update every field of a user. password_hash=None leaves it unchanged."""
    con = _conn()
    if password_hash:
        con.execute("""
            UPDATE users SET username=?, nome=?, cognome=?, role=?,
              password_hash=?, telefono=?, gruppo_sanguigno=?,
              emergenza_contatto=?, emergenza_telefono=?,
              flarm_id=?, lingua=?, note_salute=?
            WHERE id=?
        """, (username, nome, cognome, role, password_hash,
              telefono, gruppo_sanguigno, emergenza_contatto, emergenza_telefono,
              flarm_id, lingua, note_salute, user_id))
    else:
        con.execute("""
            UPDATE users SET username=?, nome=?, cognome=?, role=?,
              telefono=?, gruppo_sanguigno=?,
              emergenza_contatto=?, emergenza_telefono=?,
              flarm_id=?, lingua=?, note_salute=?
            WHERE id=?
        """, (username, nome, cognome, role,
              telefono, gruppo_sanguigno, emergenza_contatto, emergenza_telefono,
              flarm_id, lingua, note_salute, user_id))
    con.commit()
    con.close()


# ── Devices (OGN <-> user linking) ────────────────────────────────────────────

def get_user_devices(user_id):
    con = _conn()
    rows = con.execute(
        "SELECT id, display_name, ogn_id, activity, color, created_at "
        "FROM devices WHERE owner_user_id=? ORDER BY display_name",
        (user_id,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_device(device_id):
    con = _conn()
    row = con.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_all_sessions_summary(limit=1000):
    """App sessions with user, timing and point count, for the admin data page."""
    con = _conn()
    rows = con.execute("""
        SELECT s.id, s.attivita, s.started_at, s.ended_at, s.state,
               u.nome, u.cognome, u.username,
               (SELECT COUNT(*) FROM gps_points p WHERE p.session_id = s.id) AS points
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        ORDER BY s.started_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_session_points(session_id):
    """All GPS points of a session, full columns, for CSV export."""
    con = _conn()
    rows = con.execute("""
        SELECT ts, lat, lon, alt_m, accuracy_m, battery_pct, speed_kmh, vspeed_ms,
               motion_state, impact_detected, accel_magnitude
        FROM gps_points WHERE session_id = ? ORDER BY ts
    """, (session_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_device_owner_id(ogn_id):
    """Owner user_id of the device registered with this ogn_id, or None."""
    if not ogn_id:
        return None
    con = _conn()
    row = con.execute("SELECT owner_user_id FROM devices WHERE ogn_id=?", (ogn_id,)).fetchone()
    con.close()
    return row["owner_user_id"] if row else None


def add_device(owner_user_id, display_name, ogn_id=None, activity=None, color="#3b82f6"):
    con = _conn()
    cur = con.execute(
        "INSERT INTO devices (owner_user_id, display_name, ogn_id, activity, color) "
        "VALUES (?,?,?,?,?)",
        (owner_user_id, display_name, (ogn_id or None), (activity or None), color),
    )
    con.commit()
    did = cur.lastrowid
    con.close()
    return did


def update_device(device_id, owner_user_id, display_name, ogn_id=None, activity=None, color="#3b82f6"):
    """Update a device only if it belongs to owner_user_id (ownership guard)."""
    con = _conn()
    con.execute(
        "UPDATE devices SET display_name=?, ogn_id=?, activity=?, color=? "
        "WHERE id=? AND owner_user_id=?",
        (display_name, (ogn_id or None), (activity or None), color, device_id, owner_user_id),
    )
    con.commit()
    con.close()


def delete_device(device_id, owner_user_id):
    """Delete a device only if it belongs to owner_user_id."""
    con = _conn()
    con.execute(
        "DELETE FROM devices WHERE id=? AND owner_user_id=?",
        (device_id, owner_user_id),
    )
    con.commit()
    con.close()


def get_all_devices():
    """All devices with their owner, for the admin view."""
    con = _conn()
    rows = con.execute("""
        SELECT d.id, d.display_name, d.ogn_id, d.activity, d.color,
               d.owner_user_id, u.username AS owner_username,
               u.nome AS owner_nome, u.cognome AS owner_cognome
        FROM devices d LEFT JOIN users u ON d.owner_user_id = u.id
        ORDER BY u.cognome, u.nome, d.display_name
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(user_id, attivita):
    initial_state = "GROUND" if attivita in ("PARAGLIDER", "HANGGLIDER") else "ACTIVE"
    con = _conn()
    cur = con.execute(
        "INSERT INTO sessions (user_id, attivita, state) VALUES (?,?,?)",
        (user_id, attivita, initial_state)
    )
    session_id = cur.lastrowid
    con.commit()
    con.close()
    return session_id


def end_session(session_id):
    con = _conn()
    con.execute(
        "UPDATE sessions SET ended_at=datetime('now') WHERE id=? AND ended_at IS NULL",
        (session_id,)
    )
    con.commit()
    con.close()


def get_active_session(user_id):
    con = _conn()
    row = con.execute(
        "SELECT * FROM sessions WHERE user_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_session(session_id):
    con = _conn()
    row = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def update_session_state(session_id, state):
    con = _conn()
    con.execute("UPDATE sessions SET state=? WHERE id=?", (state, session_id))
    con.commit()
    con.close()


def get_all_active_sessions():
    con = _conn()
    rows = con.execute("""
        SELECT s.*, u.nome, u.cognome, u.share_token
        FROM sessions s JOIN users u ON s.user_id = u.id
        WHERE s.ended_at IS NULL
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── GPS points ────────────────────────────────────────────────────────────────

def write_gps_point(session_id, ts, lat, lon, **kwargs):
    con = _conn()
    con.execute("""
        INSERT INTO gps_points
            (session_id, ts, lat, lon, alt_m, accuracy_m, battery_pct,
             speed_kmh, vspeed_ms,
             motion_state, impact_detected, accel_magnitude)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        session_id, ts, lat, lon,
        kwargs.get("alt_m"), kwargs.get("accuracy_m"), kwargs.get("battery_pct"),
        kwargs.get("speed_kmh"), kwargs.get("vspeed_ms"),
        kwargs.get("motion_state"), int(kwargs.get("impact_detected", False)),
        kwargs.get("accel_magnitude"),
    ))
    con.commit()
    con.close()


def get_track(session_id, limit=500):
    con = _conn()
    rows = con.execute("""
        SELECT * FROM gps_points WHERE session_id=?
        ORDER BY ts DESC LIMIT ?
    """, (session_id, limit)).fetchall()
    con.close()
    return [dict(r) for r in reversed(rows)]


def get_latest_point(session_id):
    con = _conn()
    row = con.execute(
        "SELECT * FROM gps_points WHERE session_id=? ORDER BY ts DESC LIMIT 1",
        (session_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


# ── OGN beacons ───────────────────────────────────────────────────────────────

def write_ogn_beacon(ogn_id, display_name, ts, lat, lon, **kwargs):
    con = _conn()
    con.execute("""
        INSERT INTO ogn_beacons
            (ogn_id, display_name, ts, lat, lon, alt_m, speed_kmh, vspeed_ms,
             course_deg, aircraft_type)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        ogn_id, display_name, ts, lat, lon,
        kwargs.get("alt_m"), kwargs.get("speed_kmh"),
        kwargs.get("vspeed_ms"), kwargs.get("course_deg"),
        kwargs.get("aircraft_type"),
    ))
    beacon_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    return beacon_id


def get_ogn_latest(window_min=10):
    """Latest beacon per device within the live window (minutes).
    Resolves the owner's identity when the beacon is linked to a device."""
    con = _conn()
    rows = con.execute("""
        SELECT b.*,
               d.owner_user_id AS owner_user_id,
               d.activity      AS device_activity,
               u.nome    AS owner_nome,
               u.cognome AS owner_cognome
        FROM ogn_beacons b
        INNER JOIN (
            SELECT ogn_id, MAX(ts) AS max_ts FROM ogn_beacons
            WHERE datetime(ts) >= datetime('now', ?)
            GROUP BY ogn_id
        ) latest ON b.ogn_id = latest.ogn_id AND b.ts = latest.max_ts
        LEFT JOIN devices d ON b.ogn_id = d.ogn_id
        LEFT JOIN users   u ON d.owner_user_id = u.id
    """, (f'-{int(window_min)} minutes',)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_ogn_track(ogn_id, limit=300, gap_min=30):
    """Beacon track for one OGN device, trimmed to the current flight.
    An OGN id accumulates many flights over days, so we split on gaps longer
    than gap_min minutes and keep only the latest contiguous run."""
    con = _conn()
    rows = con.execute("""
        SELECT ts, lat, lon, alt_m, speed_kmh, vspeed_ms, course_deg
        FROM ogn_beacons WHERE ogn_id=?
        ORDER BY ts DESC LIMIT ?
    """, (ogn_id, limit)).fetchall()
    con.close()
    pts = [dict(r) for r in reversed(rows)]   # oldest first
    if len(pts) < 2:
        return pts

    def _parse(ts):
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    start = 0
    for i in range(len(pts) - 1, 0, -1):
        t1, t0 = _parse(pts[i]["ts"]), _parse(pts[i - 1]["ts"])
        if t1 and t0 and (t1 - t0).total_seconds() > gap_min * 60:
            start = i
            break
    return pts[start:]


def update_ogn_state(ogn_id, state):
    con = _conn()
    con.execute("""
        UPDATE ogn_beacons SET state=?
        WHERE ogn_id=? AND ts=(SELECT MAX(ts) FROM ogn_beacons WHERE ogn_id=?)
    """, (state, ogn_id, ogn_id))
    con.commit()
    con.close()


# ── Emergencies ───────────────────────────────────────────────────────────────

def create_emergency(trigger, lat, lon, alt_m=None, session_id=None, ogn_beacon_id=None, note=None, user_id=None):
    con = _conn()
    cur = con.execute("""
        INSERT INTO emergencies (session_id, ogn_beacon_id, user_id, trigger, lat, lon, alt_m, note)
        VALUES (?,?,?,?,?,?,?,?)
    """, (session_id, ogn_beacon_id, user_id, trigger, lat, lon, alt_m, note))
    emergency_id = cur.lastrowid
    con.commit()
    con.close()
    return emergency_id


def acknowledge_emergency(emergency_id, acknowledged_by):
    """Mark an emergency as taken in charge by an operator (distinct from
    resolving it). No-op if already acknowledged or already resolved."""
    con = _conn()
    con.execute("""
        UPDATE emergencies
        SET acknowledged_at = datetime('now'), acknowledged_by = ?
        WHERE id = ? AND acknowledged_at IS NULL AND resolved_at IS NULL
    """, (acknowledged_by, emergency_id))
    con.commit()
    con.close()


def resolve_emergency(emergency_id, resolved_by, note=None):
    con = _conn()
    con.execute("""
        UPDATE emergencies SET resolved_at=datetime('now'), resolved_by=?, note=?
        WHERE id=?
    """, (resolved_by, note, emergency_id))
    con.commit()
    con.close()


def get_open_emergencies():
    """Open emergencies with the subject's identity.
    Two resolution paths, merged with COALESCE:
      - APP: emergency -> session -> user
      - OGN: emergency -> ogn_beacon -> device (ogn_id) -> owner user
    This way an OGN emergency (SIGNAL_LOST, AUTO_CHUTE) also carries name and
    phone, provided the device has been linked to a user from the web."""
    con = _conn()
    rows = con.execute("""
        SELECT e.*,
               COALESCE(du.nome,               u.nome,               ou.nome)               AS nome,
               COALESCE(du.cognome,            u.cognome,            ou.cognome)            AS cognome,
               COALESCE(du.telefono,           u.telefono,           ou.telefono)           AS telefono,
               COALESCE(du.emergenza_contatto, u.emergenza_contatto, ou.emergenza_contatto) AS emergenza_contatto,
               COALESCE(du.emergenza_telefono, u.emergenza_telefono, ou.emergenza_telefono) AS emergenza_telefono,
               COALESCE(du.gruppo_sanguigno,   u.gruppo_sanguigno,   ou.gruppo_sanguigno)   AS gruppo_sanguigno,
               COALESCE(du.note_salute,        u.note_salute,        ou.note_salute)        AS note_salute,
               COALESCE(du.lingua,             u.lingua,             ou.lingua)             AS lingua,
               COALESCE(s.attivita, CASE WHEN e.ogn_beacon_id IS NOT NULL THEN 'PARAGLIDER' END)                    AS attivita,
               ob.ogn_id       AS ogn_id,
               ob.display_name AS ogn_name
        FROM emergencies e
        LEFT JOIN users       du ON e.user_id       = du.id
        LEFT JOIN sessions    s  ON e.session_id    = s.id
        LEFT JOIN users       u  ON s.user_id       = u.id
        LEFT JOIN ogn_beacons ob ON e.ogn_beacon_id = ob.id
        LEFT JOIN devices     d  ON ob.ogn_id       = d.ogn_id
        LEFT JOIN users       ou ON d.owner_user_id = ou.id
        WHERE e.resolved_at IS NULL
        ORDER BY e.ts DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_open_emergency_for_user(user_id):
    """The user's currently open emergency, if any — matched either directly
    (manual SOS with user_id) or via one of their sessions. Lets the mobile app
    know whether its emergency is still open so it can keep the red overlay up."""
    con = _conn()
    row = con.execute("""
        SELECT e.* FROM emergencies e
        LEFT JOIN sessions s ON e.session_id = s.id
        WHERE e.resolved_at IS NULL AND (e.user_id = ? OR s.user_id = ?)
        ORDER BY e.ts DESC
        LIMIT 1
    """, (user_id, user_id)).fetchone()
    con.close()
    return dict(row) if row else None


def get_emergency(eid):
    """One emergency with the full subject identity (both resolution paths)."""
    con = _conn()
    row = con.execute("""
        SELECT e.*,
               COALESCE(du.nome,               u.nome,               ou.nome)               AS nome,
               COALESCE(du.cognome,            u.cognome,            ou.cognome)            AS cognome,
               COALESCE(du.telefono,           u.telefono,           ou.telefono)           AS telefono,
               COALESCE(du.emergenza_contatto, u.emergenza_contatto, ou.emergenza_contatto) AS emergenza_contatto,
               COALESCE(du.emergenza_telefono, u.emergenza_telefono, ou.emergenza_telefono) AS emergenza_telefono,
               COALESCE(du.gruppo_sanguigno,   u.gruppo_sanguigno,   ou.gruppo_sanguigno)   AS gruppo_sanguigno,
               COALESCE(du.note_salute,        u.note_salute,        ou.note_salute)        AS note_salute,
               COALESCE(du.lingua,             u.lingua,             ou.lingua)             AS lingua,
               COALESCE(e.user_id,            s.user_id,            d.owner_user_id)       AS subject_user_id,
               COALESCE(s.attivita, CASE WHEN e.ogn_beacon_id IS NOT NULL THEN 'PARAGLIDER' END)                    AS attivita,
               ob.ogn_id       AS ogn_id,
               rb.nome         AS resolver_nome,
               rb.cognome      AS resolver_cognome,
               ab.nome         AS acker_nome,
               ab.cognome      AS acker_cognome
        FROM emergencies e
        LEFT JOIN users       du ON e.user_id         = du.id
        LEFT JOIN sessions    s  ON e.session_id      = s.id
        LEFT JOIN users       u  ON s.user_id         = u.id
        LEFT JOIN ogn_beacons ob ON e.ogn_beacon_id   = ob.id
        LEFT JOIN devices     d  ON ob.ogn_id         = d.ogn_id
        LEFT JOIN users       ou ON d.owner_user_id   = ou.id
        LEFT JOIN users       rb ON e.resolved_by     = rb.id
        LEFT JOIN users       ab ON e.acknowledged_by = ab.id
        WHERE e.id = ?
    """, (eid,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_all_emergencies():
    """Every emergency (open and resolved) with identity resolved via both the
    session and the OGN-device path, plus who resolved it. For the recap page."""
    con = _conn()
    rows = con.execute("""
        SELECT e.*,
               COALESCE(du.nome,               u.nome,               ou.nome)               AS nome,
               COALESCE(du.cognome,            u.cognome,            ou.cognome)            AS cognome,
               COALESCE(du.telefono,           u.telefono,           ou.telefono)           AS telefono,
               COALESCE(du.emergenza_contatto, u.emergenza_contatto, ou.emergenza_contatto) AS emergenza_contatto,
               COALESCE(du.emergenza_telefono, u.emergenza_telefono, ou.emergenza_telefono) AS emergenza_telefono,
               COALESCE(du.gruppo_sanguigno,   u.gruppo_sanguigno,   ou.gruppo_sanguigno)   AS gruppo_sanguigno,
               COALESCE(e.user_id,            s.user_id,            d.owner_user_id)       AS subject_user_id,
               COALESCE(s.attivita, CASE WHEN e.ogn_beacon_id IS NOT NULL THEN 'PARAGLIDER' END)                    AS attivita,
               ob.ogn_id       AS ogn_id,
               rb.nome         AS resolver_nome,
               rb.cognome      AS resolver_cognome
        FROM emergencies e
        LEFT JOIN users       du ON e.user_id       = du.id
        LEFT JOIN sessions    s  ON e.session_id    = s.id
        LEFT JOIN users       u  ON s.user_id       = u.id
        LEFT JOIN ogn_beacons ob ON e.ogn_beacon_id = ob.id
        LEFT JOIN devices     d  ON ob.ogn_id       = d.ogn_id
        LEFT JOIN users       ou ON d.owner_user_id = ou.id
        LEFT JOIN users       rb ON e.resolved_by   = rb.id
        ORDER BY e.ts DESC
        LIMIT 500
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Retention ─────────────────────────────────────────────────────────────────

def purge_old_tracks(retention_days):
    """Delete GPS points and OGN beacons older than retention_days, keeping
    anything linked to an emergency (open or resolved). Returns row counts."""
    con = _conn()
    cutoff = f'-{int(retention_days)} days'
    c1 = con.execute("""
        DELETE FROM gps_points
        WHERE datetime(ts) < datetime('now', ?)
          AND session_id NOT IN (SELECT session_id FROM emergencies WHERE session_id IS NOT NULL)
    """, (cutoff,)).rowcount
    c2 = con.execute("""
        DELETE FROM ogn_beacons
        WHERE datetime(ts) < datetime('now', ?)
          AND id NOT IN (SELECT ogn_beacon_id FROM emergencies WHERE ogn_beacon_id IS NOT NULL)
    """, (cutoff,)).rowcount
    con.commit()
    con.close()
    return {"gps_points": c1, "ogn_beacons": c2}


# ── Notification log ──────────────────────────────────────────────────────────

def log_notification(emergency_id, channel, recipient, success):
    con = _conn()
    con.execute(
        "INSERT INTO notification_log (emergency_id, channel, recipient, success) VALUES (?,?,?,?)",
        (emergency_id, channel, recipient, int(success))
    )
    con.commit()
    con.close()


# ── Config ────────────────────────────────────────────────────────────────────

def get_all_config():
    """Return every config row as a list of dicts."""
    con = _conn()
    rows = con.execute(
        "SELECT * FROM config ORDER BY categoria, key"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_config_value(key, default=None):
    """Single config value by key, or the default if absent."""
    con = _conn()
    row = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default


def set_config_value(key, value):
    """Update a single config value."""
    con = _conn()
    con.execute(
        "UPDATE config SET value=?, aggiornato=datetime('now') WHERE key=?",
        (str(value), key)
    )
    con.commit()
    con.close()


# ── Emergency rules ───────────────────────────────────────────────────────────

def get_emergency_rules():
    """All emergency rules as a list of dicts."""
    con = _conn()
    rows = con.execute("SELECT * FROM emergency_rules ORDER BY key").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_emergency_rule(key):
    con = _conn()
    row = con.execute("SELECT * FROM emergency_rules WHERE key=?", (key,)).fetchone()
    con.close()
    return dict(row) if row else None


def set_emergency_rule(key, enabled, applies_to, mode):
    con = _conn()
    con.execute("""
        UPDATE emergency_rules
        SET enabled=?, applies_to=?, mode=?, aggiornato=datetime('now')
        WHERE key=?
    """, (int(enabled), applies_to, mode, key))
    con.commit()
    con.close()


def load_em_rules() -> dict:
    """Emergency rules keyed by trigger name, for the evaluator.
    Each value: {enabled: bool, applies_to: set[str], mode: str}."""
    rules = {}
    for r in get_emergency_rules():
        rules[r["key"]] = {
            "enabled":    bool(r["enabled"]),
            "applies_to": {a for a in (r["applies_to"] or "").split(",") if a},
            "mode":       r["mode"],
        }
    return rules


def load_em_config():
    """Build an EmConfig from the values stored in the DB."""
    from core.emergency import EmConfig
    rows = get_all_config()
    kwargs = {}
    for row in rows:
        key  = row["key"]
        tipo = row["tipo"]
        val  = row["value"]
        try:
            if tipo == "int":
                kwargs[key] = int(val)
            elif tipo == "float":
                kwargs[key] = float(val)
            elif tipo == "bool":
                kwargs[key] = val.lower() in ("true", "1", "yes")
            else:
                kwargs[key] = val
        except (ValueError, TypeError):
            pass  # fall back to the EmConfig default
    # drop unknown keys
    valid = {f.name for f in EmConfig.__dataclass_fields__.values()}
    kwargs = {k: v for k, v in kwargs.items() if k in valid}
    return EmConfig(**kwargs)
