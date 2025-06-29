import hashlib
import os
import logging
import sqlite3

# Third-Party
from flask import session, current_app

# Local
from core.extensions import fernet

# Gemeinsamer Logger (wird auch in cards.py benutzt)
main_logger = logging.getLogger("main_logger")


def _get_session_userinfo():
    """Liefert userinfo aus Session (OAuth oder E-Mail)."""
    return session.get("oauth_userinfo") or session.get("email_userinfo")


def _normalize_name(userinfo):
    """Stellt sicher, dass Vor- und Nachname vorhanden sind."""
    first = userinfo.get("first_name") or ""
    last = userinfo.get("last_name") or ""
    if not first or not last:
        parts = userinfo.get("name", "").strip().split()
        first = parts[0] if parts else "Unknown"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def _fetch_role_and_year(email):
    """Liest Rolle und Beitrittsjahr aus verschlüsselter SQLite-Tabelle."""
    role = ""
    join_year = None
    try:
        db_path = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        with sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT role, join_year FROM members WHERE email_hash=?", (email_hash,)
            ).fetchone()
            if row:
                if row[0]:
                    try:
                        role = fernet.decrypt(row[0]).decode()
                    except Exception:
                        role = ""
                if row[1]:
                    try:
                        token_bytes = row[1].encode() if isinstance(row[1], str) else row[1]
                        join_year = fernet.decrypt(token_bytes).decode()
                    except Exception:
                        join_year = None
    except Exception as err:
        main_logger.error(f"DB access failed for {email}: {err}")
    return role, join_year


def build_user_data_from_session():
    """Aggregiert alle User-Informationen aus Session + DB.

    Gibt ein Dict mit den Schlüsseln
    user_id, first_name, last_name, role, photo_id, join_year
    zurück oder None, falls kein Login vorhanden ist.
    """
    userinfo = _get_session_userinfo()
    if not userinfo:
        return None

    email = userinfo.get("email")
    if not email:
        return None

    first_name, last_name = _normalize_name(userinfo)
    role, join_year = _fetch_role_and_year(email)
    photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]

    return {
        "user_id": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "photo_id": photo_id,
        "join_year": join_year,
    }