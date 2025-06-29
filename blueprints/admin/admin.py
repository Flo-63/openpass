# admin.py
# Standard Library
import csv
import hashlib
import io
import logging
import os
import sqlite3
from datetime import datetime
from dateutil import parser

# Third-Party
import portalocker
from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    current_app,
    abort
)

# Local
from core.extensions import admin_required, fernet

import_logger = logging.getLogger("import_logger")

admin_bp = Blueprint('admin', __name__, template_folder='templates')

@admin_bp.errorhandler(401)
@admin_bp.errorhandler(403)
def _admin_not_found(err):
    """
    Routes unauthorized/forbidden errors to 404.

    :param err: Error object
    :return: 404 response
    """
    return abort(404)

@admin_bp.route("/upload_members", methods=["GET", "POST"])
@admin_required
def upload_members():
    """
    Handles member data upload and processing.

    Processes CSV files with member data, validates content,
    and stores in SQLite database with encryption.

    :return: Template or redirect response
    :rtype: flask.Response
    :raises ValueError: On CSV validation errors
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])

    if request.method == "POST":
        import_logger.info("Starting member import.")
        file = request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            import_logger.warning(f"Invalid or missing file upload: {file.filename if file else None}")
            flash("Please upload a valid CSV file.", "danger")
            return redirect(url_for("admin.upload_members"))

        file_content = file.stream.read().decode("utf-8-sig")
        lines = file_content.splitlines()

        try:
            dialect = csv.Sniffer().sniff(file_content, delimiters=";,|\t,")
            delimiter = dialect.delimiter
            import_logger.info(f"CSV delimiter detected: '{delimiter}'")
        except Exception:
            delimiter = current_app.config.get("CSV_DELIMITER", ",") or ","
            import_logger.warning(f"CSV delimiter not detected, fallback: '{delimiter}'")

        reader = csv.DictReader(lines, delimiter=delimiter, restval="")

        if not reader.fieldnames:
            flash("CSV file has no header row.", "danger")
            return redirect(url_for("admin.upload_members"))

        def normalize(s):
            return (
                s.strip()
                 .lower()
                 .replace("-", "")
                 .replace("_", "")
                 .replace("ä", "ae")
                 .replace("ö", "oe")
                 .replace("ü", "ue")
                 .replace("ß", "ss")
                 .replace("\ufeff", "")  # Remove BOM
            )

        field_map = {normalize(name): name for name in reader.fieldnames}

        import_logger.debug(f"Original field names: {reader.fieldnames}")
        import_logger.debug(f"Normalized field names: {list(field_map.keys())}")

        candidates = {
            "email": {"email", "e-mail", "mail", "e_mail"},
            "firstname": {"vorname", "firstname", "first_name"},
            "lastname": {"nachname", "lastname", "last_name"},
            "joindate": {"eintritt", "eintrittsdatum", "beitritt", "beitrittsdatum", "joindate", "join"},
            "role": {"rolle", "role"}
        }

        try:
            mapped_fields = {}
            for key, variants in candidates.items():
                for variant in variants:
                    if normalize(variant) in field_map:
                        mapped_fields[key] = field_map[normalize(variant)]
                        break
                if key not in mapped_fields:
                    import_logger.warning(
                        f"CSV field mapping failed for '{key}'. "
                        f"Detected fields: {list(field_map.values())}"
                    )
                    raise ValueError(
                        f"Required field '{key}' missing in CSV. "
                        f"Please check column headers (e.g., 'First Name', 'Last Name', 'Email')."
                    )

            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            LOCK_PATH = DB_PATH + ".lock"

            with open(LOCK_PATH, "w") as lock_file:
                portalocker.lock(lock_file, portalocker.LOCK_EX)

                conn = sqlite3.connect(DB_PATH, timeout=10)
                cur = conn.cursor()
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
                import_logger.info(f"Preparing/overwriting members DB: {DB_PATH}")
                for i, row in enumerate(reader, start=2):
                    try:
                        email = row.get(mapped_fields["email"], "").strip().lower()
                        first_name = row.get(mapped_fields["firstname"], "").strip()
                        last_name = row.get(mapped_fields["lastname"], "").strip()
                        role = row.get(mapped_fields.get("role", ""), "").strip() if "role" in mapped_fields else ""


                        # join_year aus Datum extrahieren
                        raw_date = row.get(mapped_fields['joindate'], '').strip()
                        join_year = None
                        parsed_date = None
                        if raw_date:
                            try:
                                parsed_date = datetime.strptime(raw_date, "%d.%m.%Y")
                            except ValueError:
                                try:
                                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d")
                                except ValueError:
                                    try:
                                        parsed_date = parser.parse(raw_date, dayfirst=True)
                                    except Exception:
                                        import_logger.warning(f"Row {i}: Could not parse join date: {raw_date}")
                            if parsed_date:
                                join_year = parsed_date.year
                                import_logger.info(
                                    f"Eintrittsdatum: {parsed_date}")

                        missing_fields = []
                        if not email:
                            missing_fields.append("Email address")
                        if not first_name:
                            missing_fields.append("First name")
                        if not last_name:
                            missing_fields.append("Last name")

                        if missing_fields:
                            raise ValueError(", ".join(missing_fields))

                        email_hash = hashlib.sha256(email.encode()).hexdigest()
                        first_name_enc = fernet.encrypt(first_name.encode()).decode()
                        last_name_enc = fernet.encrypt(last_name.encode()).decode()
                        role_enc = fernet.encrypt(role.encode())
                        join_year_enc = fernet.encrypt(str(join_year).encode()) if join_year else None

                        import_logger.debug(f"Email: {email} Vorname: {first_name} Nachname: {last_name} Rolle:{role} Eintrittsdatum: {parsed_date} Eintrittsjahr:{join_year}")
                        import_logger.debug(
                            f"Email_hash: {email_hash} Vorname: {first_name_enc} Nachname: {last_name_enc} Rolle:{role_enc} Eintrittsjahr:{join_year_enc}")

                        cur.execute("INSERT INTO members VALUES (?, ?, ?, ?, ?)",
                                    (email_hash, first_name_enc, last_name_enc, join_year_enc, role_enc ))
                        count += 1

                    except sqlite3.IntegrityError:
                        flash(f"⚠️ Row {i} – Address already exists: {email}", "warning")
                        import_logger.warning(f"Row {i}: Email already exists: {email}")

                    except Exception as row_error:
                        email_fallback = email or "unknown"
                        name_fallback = f"{first_name} {last_name}".strip() or email_fallback

                        error_msg = str(row_error)

                        if "Email address" in error_msg:
                            msg = f"Email address missing for {name_fallback}"
                        elif "First name" in error_msg or "Last name" in error_msg:
                            msg = f"{error_msg} missing for {email_fallback}"
                        else:
                            msg = f"Invalid data for {name_fallback}"

                        flash(f"⚠️ Row {i} – {msg}", "warning")
                        import_logger.warning(f"Row {i} skipped – {msg} | Content: {row}")

                conn.commit()
                conn.close()

            flash(f"{count} members successfully saved.", "success")
            import_logger.info(f"{count} members successfully saved.")

        except Exception as e:
            import_logger.exception("Error processing CSV")
            flash(f"❌ Error processing CSV: {str(e)}", "danger")
            return redirect(url_for("admin.upload_members"))

        return redirect(url_for("admin.upload_members"))

    return render_template("upload_members.html")