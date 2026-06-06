"""Simple SQLite helper for Flask → device/screen DB queries."""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "web" / ".data" / "eink.db"


def _query(sql: str, params=()):
    """Run a read-only query, return rows as dicts."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_device(device_id: str) -> dict | None:
    rows = _query("SELECT * FROM devices WHERE id = ?", (device_id,))
    return rows[0] if rows else None


def get_device_screens(device_id: str) -> list[dict]:
    return _query(
        """SELECT ds.*, s.name as screen_name, s.type as screen_type, s.config as screen_config
           FROM device_screens ds
           JOIN screens s ON ds.screen_id = s.id
           WHERE ds.device_id = ? AND ds.enabled = 1
           ORDER BY ds.sort_order ASC""",
        (device_id,)
    )


def register_device(device_id: str, variant: str = "e1001", name: str = None) -> dict | None:
    """Auto-register a device. Returns device dict or None if failed."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    try:
        now = int(__import__('time').time() * 1000)
        display_name = name or f"Display {device_id[:4]}"
        conn.execute(
            "INSERT OR IGNORE INTO devices (id, name, variant, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
            (device_id, display_name, variant, now, now)
        )
        conn.commit()
        return {"id": device_id, "name": display_name, "variant": variant}
    except Exception:
        return None
    finally:
        conn.close()
