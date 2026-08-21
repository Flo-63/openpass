"""
===============================================================================
Project   : openpass
Module    : blueprints/main/main.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is the main module for the Flask application. It defines the main
            Blueprint and its routes, including the index and terms pages.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# main.py
import logging
# Third-Party
from flask import (
    Blueprint,
    current_app,
    render_template,
    send_from_directory, request
)
from flask_limiter.util import get_remote_address
import json

# Local
from core.extensions import limiter

main_logger = logging.getLogger("main_logger")
csp_logger = logging.getLogger("csp_logger")

main_bp = Blueprint("main", __name__, template_folder="templates")

# Largest number of characters kept from any single field of a CSP report.
CSP_FIELD_MAX_LEN = 300


def _log_safe(value, max_len: int = CSP_FIELD_MAX_LEN) -> str:
    """
    Renders an untrusted value as a single, length-bounded log field.

    Violation reports are accepted from anyone without authentication, and their fields
    are written straight into the log file. Carriage returns and newlines would let a
    caller close the current line and append further lines of their own choosing –
    entries that are indistinguishable from genuine ones once they are in the file. Any
    control character is therefore escaped rather than emitted verbatim.

    Args:
        value: Field taken from the report body; may be of any JSON type.
        max_len (int): Maximum number of characters to keep.

    Returns:
        str: A one-line, truncated representation safe to concatenate into a log record.
    """
    text = str(value)
    if len(text) > max_len:
        text = text[:max_len] + "…[truncated]"
    # Escape every C0/C1 control character, not just \r and \n.
    return "".join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in text)

@main_bp.route("/")
def index():
    """
    Handles the default route for the main blueprint, rendering the login page.

    Returns
    -------
    werkzeug.wrappers.response.Response
        A response object containing the rendered "login.html" template.
    """
    return render_template("login.html")

@main_bp.route("/terms")
def terms():
    """
    Handles rendering of the terms and conditions page.

    The function is mapped to the '/terms' endpoint of the application and
    returns the rendered 'terms.html' template. It is typically used to
    serve the terms and conditions page of the web application.

    Returns:
        Response: Rendered 'terms.html' template as a Flask response.
    """
    return render_template("terms.html")


@main_bp.route('/csp-report', methods=['POST'])
@limiter.limit(lambda: current_app.config.get("CSP_REPORT_RATE_LIMIT", "60 per hour"),
               key_func=get_remote_address,
               methods=["POST"])
def csp_report():
    """
    Handles Content Security Policy (CSP) violation reports sent to the '/csp-report' endpoint via
    POST method. This function processes the incoming raw JSON report, validates it, and logs the
    details for further analysis. Empty or malformed reports are handled gracefully, and any errors
    during processing are logged.

    Args:
        None

    Returns:
        tuple: An empty response body with a 204 No Content status code.

    Raises:
        None
    """
    try:
        raw = request.get_data(as_text=True) or ''
        if not raw.strip():
            csp_logger.warning("[CSP] Empty report body.")
            return '', 204

        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            # The body is attacker-controlled and unparsed here, so it gets the same
            # one-line treatment as the individual fields below.
            csp_logger.warning(f"[CSP] Invalid JSON format: {_log_safe(raw)}")
            return '', 204

        data = report.get("csp-report", report)
        if not isinstance(data, dict):
            csp_logger.warning("[CSP] Report body is not an object.")
            return '', 204

        csp_logger.warning(
            "[CSP Violation] | "
            f"Document URI: {_log_safe(data.get('document-uri', 'N/A'))} | "
            f"Violated: {_log_safe(data.get('violated-directive', 'N/A'))} | "
            f"Effective: {_log_safe(data.get('effective-directive', 'N/A'))} | "
            f"Blocked URI: {_log_safe(data.get('blocked-uri', 'N/A'))} | "
            f"Source File: {_log_safe(data.get('source-file', 'N/A'))} | "
            f"Line: {_log_safe(data.get('line-number', 'N/A'), 20)} | "
            f"Column: {_log_safe(data.get('column-number', 'N/A'), 20)} | "
            f"Original Policy: {_log_safe(data.get('original-policy', 'N/A'))}"
        )

    except Exception as e:
        csp_logger.exception(f"[CSP] Error in report handling: {e}")

    return '', 204



@main_bp.route('/sw.js')
def service_worker():
    """
    Registers a route for serving the service worker JavaScript file.

    This route allows the web application to serve a service worker script located in
    the `static/js` directory. Service workers are commonly used to enable offline
    functionalities and enhance application performance by caching resources.

    Returns:
        Response: A Flask response object containing the service worker JavaScript file.
    """
    return send_from_directory('static/js', 'sw.js')