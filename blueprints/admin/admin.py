"""
===============================================================================
Project   : openpass
Module    : blueprints/admin/admin.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides administrative functionalities for managing member data.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# Standard Library
import csv
import os
import hashlib
import logging
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
    abort,
    make_response
)

# Local
from core.extensions import admin_required, fernet
from . import members_import

import_logger = logging.getLogger("import_logger")

admin_bp = Blueprint('admin', __name__, template_folder='templates')

@admin_bp.errorhandler(401)
@admin_bp.errorhandler(403)
def _admin_not_found(err):
    """
    Handles specific HTTP error codes for the admin blueprint by redirecting
    to a 404 error page. This function is used to capture unauthorized access
    errors (401) and forbidden access errors (403), and instead of rendering
    their default error pages, it explicitly aborts with a 404 status.

    Parameters:
    err : Exception
        The exception object associated with the HTTP error that was raised.

    Returns:
    None
        Does not return a value but redirects to an HTTP 404 page.

    Raises:
    HTTPException
        Explicitly raises a 404 status to replace error codes 401 and 403.
    """
    return abort(404)

@admin_bp.route("/upload_members", methods=["GET", "POST"])
@admin_required
def upload_members():
    """
    Handles uploading and processing of a CSV file containing member data. This function
    is mapped to the '/upload_members' route, and is restricted to administrative users
    via the `@admin_required` decorator. It validates the submitted file, processes its
    content, maps CSV headers to predefined fields, and updates a SQLite members database.

    Exceptions occurring during file parsing, field mapping, or database operations are
    handled with appropriate error messages flashed to the user interface.

    The data handling involves securely encrypting sensitive fields before storing them
    in the database.

    Parameters:
        None

    Returns:
        Response object for rendering the upload page as 'GET' or redirecting after
        form submission as 'POST'.

    Raises:
        Flash messages for validation issues, data parsing errors, missing fields, and
        duplicate entries while processing the CSV file.
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

@admin_required
@admin_bp.post("/members/import-validate")
def import_validate():
    """
    Handles the import and validation of a CSV file containing member data. This endpoint
    is restricted to administrator access and is responsible for parsing the uploaded file,
    validating its content, and rendering a preview of the validated rows.

    Raises an error if the uploaded file is not a valid CSV or if no file is provided.

    Arguments:
        None

    Raises:
        HTTPException: Returns an HTTP 400 response if the uploaded file is not valid or
        no file is provided.

    Returns:
        Response: Renders a template with the validated rows. If the request includes HTMX
        headers, a partial HTML template is returned; otherwise, the full HTML page is rendered.
    """
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith(".csv"):
        return make_response("<div class='text-red-600'>❌ Keine gültige CSV.</div>", 400)

    file.stream.seek(0)
    rows = members_import.parse_csv(file)
    validated = members_import.validate_rows(rows)

    # wenn HTMX → Partial, sonst volle Seite
    tpl = "members_import_preview_partial.html" if "HX-Request" in request.headers else "members_import_preview.html"
    return render_template(tpl, rows=validated)

@admin_required
@admin_bp.route("/members/import-commit", methods=["POST"])
def import_commit():
    """
    Handles the commit operation for importing member data from a form input,
    validates the extracted data from the form, and updates the member database
    if the provided data is error-free. Provides feedback to the user on both
    validation errors and successful import operations.

    Parameters:
        None

    Returns:
        flask.wrappers.Response: Depending on the validation outcomes and request
        headers, this function responds with either an HTML error preview,
        success flash messages with redirection, or an HX redirect for HTMX
        requests.

    Raises:
        None
    """
    # 🔹 Datenbankpfad definieren
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])

    # 🔹 Eingehende CSV-Daten aus dem Formular extrahieren
    rows = []
    i = 0
    while f"rows[{i}][email]" in request.form:
        rows.append({
            "firstname": request.form.get(f"rows[{i}][firstname]", "").strip(),
            "lastname": request.form.get(f"rows[{i}][lastname]", "").strip(),
            "email": request.form.get(f"rows[{i}][email]", "").strip(),
            "joindate": request.form.get(f"rows[{i}][joindate]", "").strip(),
            "role": request.form.get(f"rows[{i}][role]", "").strip(),
        })
        i += 1

    # 🔹 Validierung der Daten
    validated = members_import.validate_rows(rows)
    error_count = sum(bool(r.get("_errors")) for r in validated)
    current_app.logger.info(f"Validation result: {error_count} errors")

    # 🔹 Falls Fehler gefunden wurden → Preview mit Warnung anzeigen
    if error_count > 0:
        flash(f"⚠️ Import konnte nicht abgeschlossen werden – {error_count} fehlerhafte Zeilen vorhanden.", "error")
        return render_template("members_import_preview_partial.html", rows=validated)

    # 🔹 Commit der Daten in die Mitgliederdatenbank
    count = members_import.commit_members(validated, DB_PATH)
    flash(f"✅ {count} Mitglieder erfolgreich importiert.", "success")

    # Wenn HTMX im Spiel ist → HX-Redirect-Header verwenden
    if request.headers.get("Hx-Request"):
        response = current_app.make_response("")
        response.status_code = 204
        response.headers["HX-Redirect"] = url_for("admin.members_manage")
        return response

    # sonst klassischer Redirect
    return redirect(url_for("admin.members_manage"))


@admin_bp.post("/members/import-revalidate")
@admin_required
def import_revalidate():
    """
    Handles revalidation of members import data.

    This function processes the incoming form data to rebuild rows, validates these rows using
    the `members_import.validate_rows` service, and renders a partial preview of the import
    results.

    Raises:
        Any exceptions raised by `members_import.validate_rows` or `render_template`.

    Returns:
        Response: Rendered HTML response with the validated rows.

    Parameters:
        None
    """
    form = request.form
    rows = []

    # Rebuild rows from form inputs
    i = 0
    while f"rows[{i}][email]" in form:
        row = {
            "firstname": form.get(f"rows[{i}][firstname]", "").strip(),
            "lastname": form.get(f"rows[{i}][lastname]", "").strip(),
            "email": form.get(f"rows[{i}][email]", "").strip(),
            "joindate": form.get(f"rows[{i}][joindate]", "").strip(),
            "role": form.get(f"rows[{i}][role]", "").strip(),
        }
        rows.append(row)
        i += 1

    from services import members_import
    validated = members_import.validate_rows(rows)
    return render_template("members_import_preview_partial.html", rows=validated)

@admin_bp.post("/members/sync-validate")
@admin_required
def sync_validate():
    """
    Validates a CSV file for member synchronization and shows preview of changes.

    This endpoint analyzes the uploaded CSV against the existing member database
    to identify members to be deleted (not in CSV), added (new in CSV), and
    unchanged (exist in both).

    Returns:
        Response: Renders sync preview template with lists of changes or
        returns to import preview if validation errors exist.
    """
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith(".csv"):
        return make_response("<div class='text-red-600'>❌ Keine gültige CSV.</div>", 400)

    file.stream.seek(0)
    rows = members_import.parse_csv(file)
    validated = members_import.validate_rows(rows)

    # Check for errors
    if any(r.get("_errors") for r in validated):
        flash("⚠️ Bitte beheben Sie erst alle Fehler in der CSV-Datei.", "error")
        tpl = "members_import_preview_partial.html" if "HX-Request" in request.headers else "members_import_preview.html"
        return render_template(tpl, rows=validated)

    # Perform sync analysis
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
    sync_result = members_import.sync_members(validated, DB_PATH)

    tpl = "members_sync_preview_partial.html" if "HX-Request" in request.headers else "members_sync_preview.html"
    return render_template(
        tpl,
        to_delete=sync_result["to_delete"],
        to_add=sync_result["to_add"],
        existing=sync_result["existing"],
    )

@admin_bp.post("/members/sync-commit")
@admin_required
def sync_commit():
    """
    Commits the synchronization by deleting removed members and adding new ones.

    Processes form data containing member hashes to delete and new member
    data to add, then commits these changes to the database.

    Returns:
        Response: Redirect to members management page with success message.
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])

    # Parse member hashes to delete
    to_delete_hashes = []
    for key in request.form.keys():
        if key.startswith("delete_"):
            email_hash = key.replace("delete_", "")
            to_delete_hashes.append(email_hash)

    # Parse new members to add
    to_add = []
    i = 0
    while f"add[{i}][email]" in request.form:
        to_add.append({
            "firstname": request.form.get(f"add[{i}][firstname]", "").strip(),
            "lastname": request.form.get(f"add[{i}][lastname]", "").strip(),
            "email": request.form.get(f"add[{i}][email]", "").strip(),
            "joindate": request.form.get(f"add[{i}][joindate]", "").strip(),
            "role": request.form.get(f"add[{i}][role]", "").strip(),
        })
        i += 1

    # Revalidate to_add to get join_year
    validated_to_add = members_import.validate_rows(to_add)

    # Commit the sync
    result = members_import.commit_sync(to_delete_hashes, validated_to_add, DB_PATH)

    flash(f"✅ Abgleich erfolgreich: {result['added']} hinzugefügt, {result['deleted']} gelöscht.", "success")

    # If HTMX request → use HX-Redirect
    if request.headers.get("Hx-Request"):
        response = current_app.make_response("")
        response.status_code = 204
        response.headers["HX-Redirect"] = url_for("admin.members_manage")
        return response

    return redirect(url_for("admin.members_manage"))

@admin_bp.route("/members", methods=["GET", "POST"])
@admin_required
def members_manage():
    """
    Handles the management of members within the administration panel. Depending
    on the HTTP method used, allows querying or updating member information as
    necessary.

    Functionality is restricted to administrators only.

    Returns:
        Response: An HTML template for managing members is rendered.
    """
    return render_template("members_manage.html")

@admin_bp.get("/members/list")
@admin_required
def members_list():
    """
    Handles the retrieval of a list of members to be displayed on the members list page.
    The function interacts with the members database, decrypts sensitive information,
    and prepares the data for rendering in the specified HTML template.

    Parameters:
        None

    Returns:
        str: Rendered HTML template with member information.

    Raises:
        Any exceptions related to database connectivity or decryption are handled internally
        and resolved by setting '?' or empty values for problematic fields to ensure that
        the function does not break.
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
    members = []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Nur Hash anzeigen, keine verschlüsselte E-Mail lesen
    cur.execute("""
        SELECT email_hash, first_name_enc, last_name_enc, join_year, role
        FROM members
        ORDER BY last_name_enc
    """)

    for row in cur.fetchall():
        try:
            firstname = fernet.decrypt(row[1].encode()).decode()
            lastname = fernet.decrypt(row[2].encode()).decode()
            join_year = fernet.decrypt(row[3]).decode() if row[3] else ""
            role = fernet.decrypt(row[4]).decode() if row[4] else ""
        except Exception:
            firstname, lastname, join_year, role = "?", "?", "", ""

        members.append({
            "email_hash": row[0],
            "firstname": firstname,
            "lastname": lastname,
            "join_year": join_year,
            "role": role,
        })

    conn.close()
    return render_template("members_list_partial.html", members=members)

@admin_bp.get("/members/new")
@admin_required
def member_new():
    """
    Handles the endpoint for creating a new member within the admin panel. This view
    requires administrative privileges. It returns a template with pre-filled empty
    member data for editing.

    Returns:
        werkzeug.wrappers.response.Response: The rendered member editor template
        with an empty member object for editing.
    """
    empty_member = {
        "email_hash": "",
        "firstname": "",
        "lastname": "",
        "join_year": "",
        "role": "",
        "email": "",
    }
    return render_template("member_editor_partial.html", member=empty_member)


@admin_bp.route("/members/edit/<email_hash>", methods=["GET", "POST"])
@admin_required
def member_edit(email_hash):
    """
    Handles viewing and editing of member data. This function supports both GET and POST
    requests. In the POST request, member details are updated in the database while in
    the GET request, the current details of the member are fetched and displayed in the
    editor. For POST operations, input data is encrypted using the provided `fernet`
    cipher before being stored.

    Parameters:
        email_hash (str): Hashed value of the email used to identify the member.

    Returns:
        Response object or rendered template for the member edit view.

    Raises:
        404: If no member associated with the provided email hash is found.
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # -----------------------------
    # POST: Änderungen speichern
    # -----------------------------
    if request.method == "POST":
        new_email = request.form.get("new_email", "").strip().lower()
        firstname = request.form.get("firstname", "").strip()
        lastname = request.form.get("lastname", "").strip()
        join_year = request.form.get("join_year", "").strip()
        role = request.form.get("role", "").strip()

        # Hash aktualisieren, falls E-Mail geändert
        new_hash = hashlib.sha256(new_email.encode()).hexdigest() if new_email else email_hash

        # Verschlüsselung vorbereiten
        first_enc = fernet.encrypt(firstname.encode()).decode()
        last_enc = fernet.encrypt(lastname.encode()).decode()
        join_enc = fernet.encrypt(str(join_year).encode()).decode() if join_year else None
        role_enc = fernet.encrypt(role.encode()).decode() if role else None

        cur.execute("""
            UPDATE members
               SET email_hash = ?,
                   first_name_enc = ?,
                   last_name_enc = ?,
                   join_year = ?,
                   role = ?
             WHERE email_hash = ?
        """, (new_hash, first_enc, last_enc, join_enc, role_enc, email_hash))
        conn.commit()
        conn.close()

        flash("Mitglied erfolgreich aktualisiert ✅", "success")
        return members_list()

    # -----------------------------
    # GET: Editor anzeigen
    # -----------------------------
    cur.execute("""
        SELECT email_hash, first_name_enc, last_name_enc, join_year, role
          FROM members
         WHERE email_hash = ?
    """, (email_hash,))
    row = cur.fetchone()
    conn.close()

    if not row:
        abort(404)

    try:
        firstname = fernet.decrypt(row[1].encode()).decode()
        lastname = fernet.decrypt(row[2].encode()).decode()

        join_year = ""
        if row[3]:
            if isinstance(row[3], bytes):
                join_year = fernet.decrypt(row[3]).decode()
            elif isinstance(row[3], str):
                join_year = fernet.decrypt(row[3].encode()).decode()
            join_year = int(join_year)

        role = fernet.decrypt(row[4]).decode() if row[4] else ""

    except Exception as e:
        current_app.logger.warning(f"Decrypt error: {e}")
        firstname, lastname, join_year, role = "?", "?", "", ""

    member = {
        "email_hash": row[0],
        "firstname": firstname,
        "lastname": lastname,
        "join_year": join_year,
        "role": role,
        "email": "(versteckt)",
    }

    return render_template("member_editor_partial.html", member=member)

@admin_bp.post("/members/save")
@admin_required
def member_save():
    """
    Creates or updates a member in the database.
    If email_hash exists, updates the existing member.
    If not, inserts a new record.
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Form-Felder lesen
    firstname = request.form.get("firstname", "").strip()
    lastname = request.form.get("lastname", "").strip()
    join_year = request.form.get("join_year", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("new_email", "").strip().lower()
    email_hash = request.form.get("email_hash", "").strip()

    # Hash erzeugen, wenn noch keiner existiert
    if not email_hash:
        if not email:
            flash("❌ Keine E-Mail-Adresse angegeben.", "error")
            return members_list()
        email_hash = hashlib.sha256(email.encode()).hexdigest()

    # Verschlüsseln
    first_enc = fernet.encrypt(firstname.encode()).decode()
    last_enc = fernet.encrypt(lastname.encode()).decode()
    join_enc = fernet.encrypt(str(join_year).encode()).decode() if join_year else None
    role_enc = fernet.encrypt(role.encode()).decode() if role else None

    # Prüfen, ob Mitglied bereits existiert
    cur.execute("SELECT COUNT(*) FROM members WHERE email_hash = ?", (email_hash,))
    exists = cur.fetchone()[0] > 0

    if exists:
        # 🔄 Update bestehenden Eintrag
        cur.execute("""
            UPDATE members
            SET first_name_enc = ?, last_name_enc = ?, join_year = ?, role = ?
            WHERE email_hash = ?
        """, (first_enc, last_enc, join_enc, role_enc, email_hash))
        flash("✅ Mitgliedsdaten aktualisiert", "success")
    else:
        # 🆕 Neues Mitglied einfügen
        cur.execute("""
            INSERT INTO members (email_hash, first_name_enc, last_name_enc, join_year, role)
            VALUES (?, ?, ?, ?, ?)
        """, (email_hash, first_enc, last_enc, join_enc, role_enc))
        flash("🎉 Neues Mitglied erfolgreich angelegt", "success")

    conn.commit()
    conn.close()

    # Liste zurückgeben
    return members_list()


@admin_bp.delete("/members/delete/<email_hash>")
@admin_required
def members_delete(email_hash):
    """
    Deletes a member from the database identified by the provided email hash.

    This endpoint is used to remove a member from the database by their hashed email address.
    It ensures that only authorized administrators can perform this operation. After the
    deletion of the member, it retrieves and returns the updated member list.

    Parameters:
        email_hash: str
            The hashed representation of the member's email address to be removed.

    Returns:
        Flask response
            The updated member list as a response after the deletion process completes.

    Raises:
        None
    """
    DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM members WHERE email_hash = ?", (email_hash,))
    conn.commit()
    conn.close()

    current_app.logger.info(f"Member mit Hash {email_hash[:10]}… gelöscht")

    # Nach Löschung: aktualisierte Liste zurückgeben
    return members_list()

@admin_bp.get("/members/hash-preview")
@admin_required
def hash_preview():
    """
    Generate a SHA-256 hash for the provided email address.

    This endpoint processes a given email parameter to generate a SHA-256 hash.
    It will return the hash value as plain text if successful. If no email is
    provided, a 400 Bad Request response is returned. In case of server-side
    errors, a 500 Internal Server Error response is returned.

    Args:
        None

    Returns:
        Tuple[str, int, Dict[str, str]]: A tuple containing the hash result as
        plain text, the HTTP status code, and the content type header.

    Raises:
        None
    """
    email = request.args.get("email", "").strip().lower()

    if not email:
        return ("", 400)  # Kein Input übergeben

    try:
        new_hash = hashlib.sha256(email.encode()).hexdigest()
        return new_hash, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as e:
        current_app.logger.error(f"Hash preview error: {e}")
        return ("", 500)
