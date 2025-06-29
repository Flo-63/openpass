# main.py
import logging
# Third-Party
from flask import (
    Blueprint,
    render_template,
    send_from_directory, request
)
import json

main_logger = logging.getLogger("main_logger")
csp_logger = logging.getLogger("csp_logger")

main_bp = Blueprint("main", __name__, template_folder="templates")

@main_bp.route("/")
def index():
    """
    Route handler for the main index route.

    This function defines the behavior for the main route of the Blueprint.
    It renders the login page template when accessed.

    :return: Rendered HTML template for the login page
    :rtype: str
    """
    return render_template("login.html")

@main_bp.route("/terms")
def terms():
    """
    Route handler for the terms and conditions page.

    This function maps the URL endpoint "/terms" to display the "terms.html" template.
    It serves as a route handler in a Flask web application, rendering the Terms 
    and Conditions page for the application.

    :return: The rendered "terms.html" template
    :rtype: str
    """
    return render_template("terms.html")


@main_bp.route('/csp-report', methods=['POST'])
def csp_report():
    """
    Robust handler for CSP violation reports.
    Logs useful information and never raises an exception.
    Always returns 204 No Content, even if input is broken.
    """
    try:
        raw = request.get_data(as_text=True) or ''
        if not raw.strip():
            csp_logger.warning("[CSP] Empty report body.")
            return '', 204

        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            csp_logger.warning(f"[CSP] Invalid JSON format:\n{raw}")
            return '', 204

        data = report.get("csp-report", report)

        csp_logger.warning(
            "[CSP Violation] | "
            f"Document URI: {data.get('document-uri', 'N/A')} | "
            f"Violated: {data.get('violated-directive', 'N/A')} | "
            f"Effective: {data.get('effective-directive', 'N/A')} | "
            f"Blocked URI: {data.get('blocked-uri', 'N/A')} | "
            f"Source File: {data.get('source-file', 'N/A')} | "
            f"Line: {data.get('line-number', 'N/A')} | "
            f"Column: {data.get('column-number', 'N/A')} | "
            f"Original Policy: {data.get('original-policy', 'N/A')}"
        )

    except Exception as e:
        csp_logger.exception(f"[CSP] Error in report handling: {e}")

    return '', 204



@main_bp.route('/sw.js')
def service_worker():
    """
    Serves the service worker JavaScript file.

    Enables progressive web app features by serving the service worker
    script from the static directory. This allows features like offline
    caching and background synchronization.

    :return: Service worker JavaScript file response
    :rtype: flask.wrappers.Response
    """
    return send_from_directory('static/js', 'sw.js')