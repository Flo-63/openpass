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
    Registers a route for serving the service worker JavaScript file.

    This route allows the web application to serve a service worker script located in
    the `static/js` directory. Service workers are commonly used to enable offline
    functionalities and enhance application performance by caching resources.

    Returns:
        Response: A Flask response object containing the service worker JavaScript file.
    """
    return send_from_directory('static/js', 'sw.js')