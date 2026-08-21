"""
Diagnostic helper: decrypt the stored role and join year for a single member.

Reads the Fernet key from the environment. An earlier version had the production key
as a literal in this file, which put it into the public git history and made every
encrypted field in the members database readable by anyone who cloned the repository.
Never reintroduce a key literal here — the file is versioned.

Usage:
    FERNET_KEY=... python utils/scripts/dbcheck.py member@example.org [path/to/members.db]
"""

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

from cryptography.fernet import Fernet

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "instance" / "members.db"


def main(argv: list[str]) -> int:
    """
    Prints the decrypted role and join year for the given email address.

    Args:
        argv (list[str]): Command line arguments; the first is the email address, the
            optional second is the path to the members database.

    Returns:
        int: Process exit status.
    """
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    key = os.getenv("FERNET_KEY")
    if not key:
        print(
            "FERNET_KEY is not set. Export it from your secret store before running "
            "this script, e.g. `FERNET_KEY=$(...) python utils/scripts/dbcheck.py ...`",
            file=sys.stderr,
        )
        return 2

    email = argv[0].strip().lower()
    db_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DB_PATH
    if not db_path.is_file():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    fernet = Fernet(key.encode() if isinstance(key, str) else key)
    email_hash = hashlib.sha256(email.encode()).hexdigest()

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT role, join_year FROM members WHERE email_hash = ?", (email_hash,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        print(f"No record for {email} (hash {email_hash[:10]}…)")
        return 1

    for name, token in zip(("role", "join_year"), row):
        if token is None:
            print(f"{name}: NULL")
            continue
        if isinstance(token, str):
            token = token.encode()
        try:
            print(f"{name}: {fernet.decrypt(token).decode()}")
        except Exception as err:
            print(f"{name}: could not decrypt ({err})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
