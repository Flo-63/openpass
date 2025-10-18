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
    Normalizes a given header string by converting it to lowercase, stripping leading and trailing
    whitespace, replacing German umlauts with their equivalent, and removing all non-alphanumeric
    characters.

    Parameters:
        header (str): The header string to be normalized.

    Returns:
        str: The normalized version of the input header string. If the input is empty, returns an
        empty string.
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
    Parses the given CSV file and extracts its content into a list of dictionaries.

    The function reads the content of a provided file-like object, deduces the CSV delimiter using sniffing
    or fallback approaches, and parses the file. It maps the CSV headers to predefined key names, resolving
    aliases for supported columns such as email, firstname, and lastname. It ensures that the required
    fields are present and skips empty rows to create structured data as dictionaries.

    Parameters:
    file (werkzeug.datastructures.FileStorage): The file-like object to be parsed. The object must have a
        'stream' attribute that supports reading and decoding.

    Returns:
    list[dict]: A list of dictionaries where each dictionary represents a row from the CSV file. The keys
        of each dictionary correspond to canonical header names (e.g., email, firstname, lastname).

    Raises:
    ValueError: If the CSV file lacks required fields or is empty.
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
    Validates a list of row data dictionaries by verifying required fields, checking for formatting errors,
    and flagging duplicate email addresses.

    Each row in the input is processed, and the function outputs a list of validated dictionaries
    containing the cleaned data and any detected validation errors. Rows are identified with their
    original position in the input list for easier traceback.

    Args:
        rows (list[dict]): List of dictionaries where each dictionary represents a row of data to validate.

    Returns:
        list[dict]: List of dictionaries containing the validated data along with errors if found.
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
    Commits validated member data to the database.

    This function processes a list of validated member records and stores them in a SQLite
    database. Each record is hashed and encrypted for secured storage. It ensures data integrity
    by utilizing a file locking mechanism to handle concurrent access to the database.

    Arguments:
        validated_rows (list[dict]): A list of member records, each represented as a dictionary.
            Each record must include keys corresponding to the expected fields within the database.
        db_path (str): The file path of the SQLite database.

    Returns:
        int: The number of rows successfully inserted or updated in the database.
    """
    import sqlite3
    import portalocker
    import hashlib

    LOCK_PATH = db_path + ".lock"

    with open(LOCK_PATH, "w") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS members (
                email_hash TEXT PRIMARY KEY,
                first_name_enc TEXT NOT NULL,
                last_name_enc TEXT NOT NULL,
                join_year BLOB,
                role BLOB
            )
        """)

        count = 0
        for row in validated_rows:
            if row["_errors"]:
                continue

            email_hash = hashlib.sha256(row["email"].encode()).hexdigest()
            first_name_enc = fernet.encrypt(row["firstname"].encode()).decode()
            last_name_enc = fernet.encrypt(row["lastname"].encode()).decode()
            role_enc = fernet.encrypt(row["role"].encode())
            join_year_enc = (
                fernet.encrypt(str(row["join_year"]).encode())
                if row["join_year"] else None
            )

            cur.execute("""
                INSERT OR REPLACE INTO members 
                (email_hash, first_name_enc, last_name_enc, join_year, role)
                VALUES (?, ?, ?, ?, ?)
            """, (email_hash, first_name_enc, last_name_enc, join_year_enc, role_enc))
            count += 1

        conn.commit()
        conn.close()
    return count

