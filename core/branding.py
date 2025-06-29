import os
import json
from flask import current_app, send_from_directory, render_template_string, abort, Response
from jinja2 import TemplateNotFound
from core.context_processors import inject_branding_colors

def load_branding(app):
    """
    Loads branding configuration from a JSON file and assigns it to the application's
    configuration. If the file cannot be loaded, an empty dictionary is assigned
    instead and a warning is logged.

    Args:
        app: The Flask application instance for which the branding configuration
             will be loaded.

    Raises:
        None directly, but warnings will be logged in case of any issues during the
        file loading process.
    """
    path = os.path.join(app.root_path, "branding", "branding.json")
    try:
        with open(path, encoding="utf-8") as f:
            app.config["BRANDING"] = json.load(f)
    except Exception as e:
        app.logger.warning(f"Branding-Datei konnte nicht geladen werden: {e}")
        app.config["BRANDING"] = {}

def branding_file(filename):
    """
    Handles requests for branding-related static files, serving the requested file from
    the branding directory.

    Parameters:
        filename (str): The name of the file to be served, provided in the
        request as part of the URL path.

    Returns:
        Response: A Flask response object that serves the requested file from
        the branding directory or appropriate error response if access is denied.
    """
    # Optional: Zugriff nur für eingeloggte Benutzer

    branding_path = os.path.join(current_app.root_path, "branding")
    return send_from_directory(branding_path, filename)


def branding_css(filename):
    """
    Renders and serves a CSS file based on a branding-specific template if it exists, otherwise
    returns a default "File not found" response. This function dynamically applies branding color
    customizations to the CSS using templates and the Flask `render_template_string` functionality.

    Parameters
    ----------
    filename : str
        Name of the CSS file to be rendered and served. If it does not end with ".css",
        the extension ".css" will be appended automatically.

    Returns
    -------
    flask.Response
        A Flask Response object with the rendered CSS content and `text/css` mimetype.
        Returns a 404 response if the requested template file is not found or does not exist.

    Raises
    ------
    TypeError
        If an invalid `filename` argument is passed or if the `filename` argument is not of the
        expected type.
    """
    if not filename.endswith(".css"):
        filename += ".css"

    path = os.path.join(current_app.root_path, "static", "css", f"{filename}.j2")
    if not os.path.exists(path):
        return Response("/* File not found */", status=404, mimetype="text/css")

    with open(path, encoding="utf-8") as f:
        template_source = f.read()

    rendered = render_template_string(template_source, **inject_branding_colors())
    return Response(rendered, mimetype="text/css")
