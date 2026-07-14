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
            trigger         TEXT NOT NULL,
            ts              TEXT DEFAULT (datetime('now')),
            lat             REAL,
            lon             REAL,
            alt_m           REAL,
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
            categoria   TEXT,
            descrizione TEXT,
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

    _seed_config(con)
    con.close()


def _seed_config(con):
    """Insert the default config values if they are not present yet."""
    from core.emergency import EmConfig, CONFIG_META
    defaults = EmConfig()
    for key, categoria, descrizione, tipo in CONFIG_META:
        value = str(getattr(defaults, key))
        con.execute("""
            INSERT OR IGNORE INTO config (key, value, tipo, categoria, descrizione)
            VALUES (?, ?, ?, ?, ?)
        """, (key, value, tipo, categoria, descrizione))
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


def get_ogn_latest():
    """Latest beacon per device over the last 10 minutes.
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
            WHERE ts >= datetime('now', '-10 minutes')
            GROUP BY ogn_id
        ) latest ON b.ogn_id = latest.ogn_id AND b.ts = latest.max_ts
        LEFT JOIN devices d ON b.ogn_id = d.ogn_id
        LEFT JOIN users   u ON d.owner_user_id = u.id
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


def update_ogn_state(ogn_id, state):
    con = _conn()
    con.execute("""
        UPDATE ogn_beacons SET state=?
        WHERE ogn_id=? AND ts=(SELECT MAX(ts) FROM ogn_beacons WHERE ogn_id=?)
    """, (state, ogn_id, ogn_id))
    con.commit()
    con.close()


# ── Emergencies ───────────────────────────────────────────────────────────────

def create_emergency(trigger, lat, lon, alt_m=None, session_id=None, ogn_beacon_id=None, note=None):
    con = _conn()
    cur = con.execute("""
        INSERT INTO emergencies (session_id, ogn_beacon_id, trigger, lat, lon, alt_m, note)
        VALUES (?,?,?,?,?,?,?)
    """, (session_id, ogn_beacon_id, trigger, lat, lon, alt_m, note))
    emergency_id = cur.lastrowid
    con.commit()
    con.close()
    return emergency_id


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
               COALESCE(u.nome,               ou.nome)               AS nome,
               COALESCE(u.cognome,            ou.cognome)            AS cognome,
               COALESCE(u.telefono,           ou.telefono)           AS telefono,
               COALESCE(u.emergenza_contatto, ou.emergenza_contatto) AS emergenza_contatto,
               COALESCE(u.emergenza_telefono, ou.emergenza_telefono) AS emergenza_telefono,
               COALESCE(u.gruppo_sanguigno,   ou.gruppo_sanguigno)   AS gruppo_sanguigno,
               COALESCE(u.note_salute,        ou.note_salute)        AS note_salute,
               COALESCE(u.lingua,             ou.lingua)             AS lingua,
               COALESCE(s.attivita, 'PARAGLIDER')                    AS attivita,
               ob.ogn_id       AS ogn_id,
               ob.display_name AS ogn_name
        FROM emergencies e
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


def get_all_emergencies():
    con = _conn()
    rows = con.execute("""
        SELECT e.*, u.nome, u.cognome, s.attivita
        FROM emergencies e
        LEFT JOIN sessions s ON e.session_id = s.id
        LEFT JOIN users u ON s.user_id = u.id
        ORDER BY e.ts DESC
        LIMIT 200
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


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


def set_config_value(key, value):
    """Update a single config value."""
    con = _conn()
    con.execute(
        "UPDATE config SET value=?, aggiornato=datetime('now') WHERE key=?",
        (str(value), key)
    )
    con.commit()
    con.close()


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
