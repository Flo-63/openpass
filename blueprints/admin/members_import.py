"""
===============================================================================
Project   : openpass
Module    : services/members_import.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is the service module to provide import functions

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# services/members_import.py
import csv
import io
import re
import unicodedata
from datetime import datetime
from flask import current_app
from core.extensions import fernet

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Header-Normalisierung
# ---------------------------------------------------------------------------
def normalize_header(header: str) -> str:
    """
    Normalizes a given string to a standard header format.

    This function processes the input string by lowering the case, removing
    leading and trailing whitespaces, normalizing Unicode characters, replacing
    certain special characters with defined string replacements, and removing
    non-alphanumeric characters except for the specified transformations.
    The result is a clean and standardized header string.

    Args:
        header (str): The input string representing the header to be normalized.

    Returns:
        str: A normalized version of the input header string.
    """
    if not header:
        return ""
    s = header.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", "", s)  # keep alphanumerics only
    return s


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------
def parse_csv(file) -> list[dict]:
    """
    Parses a CSV file and extracts structured data into a list of dictionaries.

    This function processes a CSV file uploaded as a file-like object and extracts
    rows of data by identifying and normalizing column headers based on predefined
    aliases. It ensures that required fields are present and ignores empty or invalid lines
    in the CSV file. The returned data consists of dictionaries with consistent
    keys for further processing.

    Parameters
    ----------
    file : Werkzeug.datastructures.FileStorage
        A file-like object containing the raw CSV content to be parsed. This
        object must provide a `stream.read()` method.

    Returns
    -------
    list[dict]
        A list of dictionaries where each dictionary represents a row of the
        parsed CSV file, with standardized keys (e.g., "email", "firstname",
        "lastname", etc.).

    Raises
    ------
    ValueError
        If the CSV file appears to be empty or if it is missing required fields
        such as "email", "firstname", or "lastname".
    """
    content = file.stream.read().decode("utf-8-sig")

    # --- detect dialect (delimiter)
    try:
        sample = content[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
        delimiter = dialect.delimiter
    except Exception:
        # fallback: pick most frequent among candidates
        candidates = [",", ";", "|", "\t"]
        delimiter = max(candidates, key=content.count)
    current_app.logger.info(f"Detected CSV delimiter: '{delimiter}'")

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("CSV file appears to be empty.")

    # --- build header map
    normalized_map = {normalize_header(h): i for i, h in enumerate(headers)}

    # possible column name variants
    header_aliases = {
        "email": ["email", "mail", "emailadresse", "adresse", "e-mail"],
        "firstname": ["vorname", "firstname", "first", "first_name"],
        "lastname": ["nachname", "lastname", "last", "last_name"],
        "joindate": ["eintritt", "eintrittsdatum", "beitritt", "beitrittsdatum", "join", "joindate"],
        "role": ["rolle", "role", "funktion", "position"],
    }

    resolved = {}
    for canonical, variants in header_aliases.items():
        for variant in variants:
            norm = normalize_header(variant)
            if norm in normalized_map:
                resolved[canonical] = normalized_map[norm]
                break

    missing = [key for key in ["email", "firstname", "lastname"] if key not in resolved]
    if missing:
        raise ValueError(f"CSV missing required fields: {', '.join(missing)}")

    # --- build rows
    rows = []
    for line in reader:
        # ⬇️ Fix: leere Zeilen komplett überspringen
        if not any(cell.strip() for cell in line):
            continue

        row = {}
        for key, idx in resolved.items():
            row[key] = line[idx].strip() if idx < len(line) else ""

        rows.append(row)

    return rows




# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_rows(rows: list[dict]) -> list[dict]:
    """
    Validates and processes a list of dictionaries representing rows of data. Checks for missing or invalid
    fields such as firstname, lastname, email, and joindate. Also ensures that email addresses are unique
    and attempts to parse and validate the joindate field in multiple formats. Appends validation errors
    for each row and returns the processed data.

    Args:
        rows (list[dict]): A list of dictionaries, where each dictionary represents a row of input data.

    Returns:
        list[dict]: A list of dictionaries representing the processed rows, including validation errors
        and additional derived fields such as join_year.

    Raises:
        KeyError: Raised if any required field is missing from the input dictionaries.
    """
    validated = []
    seen_emails = set()

    for idx, row in enumerate(rows, start=2):
        errors = []

        firstname = row.get("firstname", "").strip()
        lastname = row.get("lastname", "").strip()
        email = row.get("email", "").strip().lower()
        joindate = row.get("joindate", "").strip()
        role = row.get("role", "").strip()

        if not firstname:
            errors.append("Vorname fehlt")
        if not lastname:
            errors.append("Nachname fehlt")
        if not email or not EMAIL_RE.match(email):
            errors.append("Ungültige E-Mail-Adresse")
        if email in seen_emails:
            errors.append("Doppelte E-Mail-Adresse")
        seen_emails.add(email)

        join_year = None
        if joindate:
            try:
                parsed = datetime.strptime(joindate, "%d.%m.%Y")
            except Exception:
                try:
                    parsed = datetime.strptime(joindate, "%Y-%m-%d")
                except Exception:
                    parsed = None
            if parsed:
                join_year = parsed.year
            else:
                errors.append(f"Eintrittsdatum ungültig: {joindate}")

        validated.append({
            "rownum": idx,
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "joindate": joindate,
            "join_year": join_year,
            "role": role,
            "_errors": errors
        })

    return validated


# ---------------------------------------------------------------------------
# DB Commit
# ---------------------------------------------------------------------------
def commit_members(validated_rows: list[dict], db_path: str):
    """
    Commits validated member records to a SQLite database.

    This function takes a list of validated member records and securely stores them
    in a SQLite database. Any existing member data in the database is completely
    replaced. Each member's sensitive information is encrypted using the Fernet
    encryption mechanism before being stored, ensuring data confidentiality. The
    function creates a lock file to ensure exclusive access when writing to the
    database. Only valid records are included, and those containing errors are
    skipped.

    Parameters:
    validated_rows: list[dict]
        A list of dictionaries containing member records to be stored. Each record
        must contain at least 'email', 'firstname', and 'lastname'. Optional keys
        include 'role' and 'join_year'.
    db_path: str
        The file path to the SQLite database.

    Returns:
    int
        The number of validated records successfully committed to the database.
    """
    import sqlite3, portalocker, hashlib
    from core.extensions import fernet

    LOCK_PATH = db_path + ".lock"

    with open(LOCK_PATH, "w") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()

        # 🔄 Vollständiges Ersetzen
        cur.execute("DROP TABLE IF EXISTS members")
        cur.execute("""
            CREATE TABLE members (
                email_hash TEXT PRIMARY KEY,
                first_name_enc TEXT NOT NULL,
                last_name_enc TEXT NOT NULL,
                join_year BLOB,
                role BLOB
            )
        """)

        count = 0
        for row in validated_rows:
            if row.get("_errors"):
                continue

            email = row["email"].strip().lower()
            firstname = row["firstname"].strip()
            lastname = row["lastname"].strip()
            role = row.get("role", "").strip()
            join_year = row.get("join_year")

            email_hash = hashlib.sha256(email.encode()).hexdigest()
            first_enc = fernet.encrypt(firstname.encode()).decode()
            last_enc = fernet.encrypt(lastname.encode()).decode()
            role_enc = fernet.encrypt(role.encode())
            join_enc = (
                fernet.encrypt(str(join_year).encode())
                if join_year else None
            )

            cur.execute("""
                INSERT INTO members (email_hash, first_name_enc, last_name_enc, join_year, role)
                VALUES (?, ?, ?, ?, ?)
            """, (email_hash, first_enc, last_enc, join_enc, role_enc))
            count += 1

        conn.commit()
        conn.close()

    return count


# ---------------------------------------------------------------------------
# Sync Analysis
# ---------------------------------------------------------------------------
def sync_members(validated_rows: list[dict], db_path: str) -> dict:
    """
    Analyzes the difference between CSV data and existing database members.

    Compares the validated CSV rows with existing members in the database
    to identify:
    - Members to be deleted (exist in DB but not in CSV)
    - Members to be added (exist in CSV but not in DB)
    - Members that remain unchanged (exist in both)

    Parameters:
    validated_rows: list[dict]
        A list of validated dictionaries from the CSV containing member data.
    db_path: str
        The file path to the SQLite database.

    Returns:
    dict
        A dictionary containing three lists:
        - "to_delete": list of existing members not in CSV
        - "to_add": list of new members from CSV
        - "existing": list of unchanged members
    """
    import sqlite3, hashlib
    from core.extensions import fernet

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Load existing members from DB
    cur.execute("""
        SELECT email_hash, first_name_enc, last_name_enc, join_year, role
        FROM members
    """)

    existing_members = {}
    for row in cur.fetchall():
        email_hash = row[0]
        try:
            firstname = fernet.decrypt(row[1].encode()).decode()
            lastname = fernet.decrypt(row[2].encode()).decode()
            join_year = fernet.decrypt(row[3]).decode() if row[3] else ""
            role = fernet.decrypt(row[4]).decode() if row[4] else ""
        except Exception:
            firstname, lastname, join_year, role = "?", "?", "", ""

        existing_members[email_hash] = {
            "email_hash": email_hash,
            "firstname": firstname,
            "lastname": lastname,
            "join_year": join_year,
            "role": role,
        }

    conn.close()

    # Build set of CSV email hashes
    csv_email_hashes = set()
    for row in validated_rows:
        if not row.get("_errors"):
            email = row["email"].strip().lower()
            email_hash = hashlib.sha256(email.encode()).hexdigest()
            csv_email_hashes.add(email_hash)

    # Determine changes
    to_delete = []
    for email_hash, member in existing_members.items():
        if email_hash not in csv_email_hashes:
            to_delete.append(member)

    to_add = []
    existing = []
    for row in validated_rows:
        if row.get("_errors"):
            continue

        email = row["email"].strip().lower()
        email_hash = hashlib.sha256(email.encode()).hexdigest()

        if email_hash in existing_members:
            existing.append(row)
        else:
            to_add.append(row)

    return {
        "to_delete": to_delete,
        "to_add": to_add,
        "existing": existing,
    }


# ---------------------------------------------------------------------------
# Commit Sync
# ---------------------------------------------------------------------------
def commit_sync(to_delete_hashes: list[str], to_add: list[dict], db_path: str):
    """
    Commits synchronization changes to the database.

    Deletes members that are no longer in the CSV and adds new members
    from the CSV that don't exist in the database yet.

    Parameters:
    to_delete_hashes: list[str]
        List of email_hash values to delete from the database.
    to_add: list[dict]
        List of validated member dictionaries to add to the database.
    db_path: str
        The file path to the SQLite database.

    Returns:
    dict
        A dictionary with counts: {"deleted": int, "added": int}
    """
    import sqlite3, portalocker, hashlib
    from core.extensions import fernet

    LOCK_PATH = db_path + ".lock"

    with open(LOCK_PATH, "w") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()

        # Delete members
        deleted_count = 0
        for email_hash in to_delete_hashes:
            cur.execute("DELETE FROM members WHERE email_hash = ?", (email_hash,))
            deleted_count += cur.rowcount

        # Add new members
        added_count = 0
        for row in to_add:
            email = row["email"].strip().lower()
            firstname = row["firstname"].strip()
            lastname = row["lastname"].strip()
            role = row.get("role", "").strip()
            join_year = row.get("join_year")

            email_hash = hashlib.sha256(email.encode()).hexdigest()
            first_enc = fernet.encrypt(firstname.encode()).decode()
            last_enc = fernet.encrypt(lastname.encode()).decode()
            role_enc = fernet.encrypt(role.encode())
            join_enc = (
                fernet.encrypt(str(join_year).encode())
                if join_year else None
            )

            cur.execute("""
                INSERT INTO members (email_hash, first_name_enc, last_name_enc, join_year, role)
                VALUES (?, ?, ?, ?, ?)
            """, (email_hash, first_enc, last_enc, join_enc, role_enc))
            added_count += cur.rowcount

        conn.commit()
        conn.close()

    return {"deleted": deleted_count, "added": added_count}


