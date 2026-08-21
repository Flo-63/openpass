"""
Re-encrypts the members database from one Fernet key to another.

Only the `members` table is affected. Photos use PHOTO_ENCRYPTION_KEY and are not
touched; membership and email-login tokens are short-lived and expire on their own.

The script is safe to re-run: values that already decrypt under the new key are left
alone, so an interrupted run can simply be repeated. Every value keeps the storage type
it had (TEXT or BLOB) — the application writes `join_year` and `role` as bytes on the
import path and as str on the editor path, and both readers rely on that.

Usage:
    FERNET_KEY_OLD=<alt> FERNET_KEY_NEW=<neu> \\
        python utils/scripts/rotate_fernet_key.py [--db PFAD] [--dry-run] [--no-backup]

Exit status is 0 on success, 1 on a problem that left the database untouched.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_DB = Path(__file__).resolve().parents[2] / "instance" / "members.db"
COLUMNS = ("first_name_enc", "last_name_enc", "join_year", "role")


def _load_key(name: str) -> Fernet:
    """
    Builds a Fernet instance from an environment variable.

    Args:
        name (str): Name of the variable holding the urlsafe base64 key.

    Returns:
        Fernet: Cipher for that key.

    Raises:
        SystemExit: If the variable is unset or the value is not a valid key.
    """
    raw = os.getenv(name)
    if not raw:
        sys.exit(f"{name} ist nicht gesetzt.")
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except Exception as err:
        sys.exit(f"{name} ist kein gueltiger Fernet-Schluessel: {err}")


def _reencrypt(value, old: Fernet, new: Fernet):
    """
    Re-encrypts a single stored value, preserving its storage type.

    Args:
        value: The stored token, as str or bytes, or None.
        old (Fernet): Cipher the value is currently encrypted under.
        new (Fernet): Cipher to encrypt it with.

    Returns:
        tuple: (new_value, status) where status is one of "rotated", "already",
        "null" or "failed".
    """
    if value is None:
        return None, "null"

    was_str = isinstance(value, str)
    token = value.encode() if was_str else value

    # Already under the new key? Then this row was done in an earlier run.
    try:
        new.decrypt(token)
        return value, "already"
    except InvalidToken:
        pass

    try:
        plaintext = old.decrypt(token)
    except InvalidToken:
        return value, "failed"

    rotated = new.encrypt(plaintext)
    return (rotated.decode() if was_str else rotated), "rotated"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Pfad zur members.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="nur zaehlen, nichts schreiben")
    parser.add_argument("--no-backup", action="store_true",
                        help="keine Sicherungskopie anlegen (nicht empfohlen)")
    args = parser.parse_args(argv)

    old = _load_key("FERNET_KEY_OLD")
    new = _load_key("FERNET_KEY_NEW")
    if os.getenv("FERNET_KEY_OLD") == os.getenv("FERNET_KEY_NEW"):
        return int(bool(sys.stderr.write("Alter und neuer Schluessel sind identisch.\n")))

    db_path = Path(args.db)
    if not db_path.is_file():
        sys.exit(f"Datenbank nicht gefunden: {db_path}")

    if not args.dry_run and not args.no_backup:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = db_path.with_name(f"{db_path.name}.{stamp}.bak")
        shutil.copy2(db_path, backup)
        print(f"Sicherungskopie: {backup}")

    conn = sqlite3.connect(db_path, timeout=30)
    conn.isolation_level = None  # explicit transaction below
    cur = conn.cursor()

    rows = cur.execute(
        f"SELECT email_hash, {', '.join(COLUMNS)} FROM members"
    ).fetchall()
    print(f"Zeilen in members: {len(rows)}")

    tally = {"rotated": 0, "already": 0, "null": 0, "failed": 0}
    updates = []
    failed_rows = []

    for email_hash, *values in rows:
        new_values, row_failed = [], False
        for value in values:
            rotated, status = _reencrypt(value, old, new)
            tally[status] += 1
            if status == "failed":
                row_failed = True
            new_values.append(rotated)
        if row_failed:
            failed_rows.append(email_hash)
        updates.append((new_values, email_hash))

    print(f"  neu verschluesselt: {tally['rotated']}")
    print(f"  schon neu:          {tally['already']}")
    print(f"  leer (NULL):        {tally['null']}")
    print(f"  nicht entschluesselbar: {tally['failed']}")

    if failed_rows:
        print("\nAbbruch: Werte liessen sich weder mit dem alten noch mit dem neuen "
              "Schluessel entschluesseln.", file=sys.stderr)
        for h in failed_rows[:5]:
            print(f"  betroffen: email_hash {h[:10]}…", file=sys.stderr)
        if len(failed_rows) > 5:
            print(f"  … und {len(failed_rows) - 5} weitere", file=sys.stderr)
        print("Die Datenbank wurde nicht veraendert.", file=sys.stderr)
        conn.close()
        return 1

    if args.dry_run:
        print("\n--dry-run: nichts geschrieben.")
        conn.close()
        return 0

    assignments = ", ".join(f"{c} = ?" for c in COLUMNS)
    cur.execute("BEGIN IMMEDIATE")
    try:
        for new_values, email_hash in updates:
            cur.execute(
                f"UPDATE members SET {assignments} WHERE email_hash = ?",
                (*new_values, email_hash),
            )
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        conn.close()
        raise

    # Verify: everything must now decrypt under the new key alone.
    bad = 0
    for _hash, *values in cur.execute(
        f"SELECT email_hash, {', '.join(COLUMNS)} FROM members"
    ).fetchall():
        for value in values:
            if value is None:
                continue
            try:
                new.decrypt(value.encode() if isinstance(value, str) else value)
            except InvalidToken:
                bad += 1
    conn.close()

    if bad:
        print(f"\nPRUEFUNG FEHLGESCHLAGEN: {bad} Werte lassen sich nicht mit dem neuen "
              f"Schluessel lesen. Sicherungskopie zuruecksichern!", file=sys.stderr)
        return 1

    print("\nPruefung: alle Werte sind mit dem neuen Schluessel lesbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
