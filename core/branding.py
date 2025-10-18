"""
===============================================================================
Project   : openpass
Module    : core/branding.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


import os
import json
from flask import current_app, send_from_directory, render_template_string, abort, Response
from jinja2 import TemplateNotFound
from core.context_processors import inject_branding_colors

def load_branding(app):
    """
    Loads branding information from a JSON file into the application's configuration.

    This function attempts to load branding information from the "branding.json" file
    located in the "branding" directory within the application's root path. If the file
    is successfully read and parsed, its contents are stored in the `BRANDING` key of
    the application's configuration. In the event of an error (e.g., the file does not
    exist, or it contains invalid JSON), a warning is logged, and the `BRANDING` key
    in the configuration is set to an empty dictionary.

    Parameters:
    app (Flask): The Flask application object whose configuration will be updated
        with the branding information.

    Raises:
    None

    Returns:
    None
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
    Returns a file from the branding directory of the application.

    This function is used to access files located in the 'branding' directory
    within the application. It takes a filename as input and serves that file
    if it exists in the specified directory.

    Args:
        filename (str): Name of the file to retrieve.

    Returns:
        Response: A response object representing the file to be sent.

    Raises:
        werkzeug.exceptions.NotFound: If the file does not exist in the directory.
        werkzeug.exceptions.Forbidden: If access to the branding directory is
        restricted.
    """
    # Optional: Zugriff nur für eingeloggte Benutzer

    branding_path = os.path.join(current_app.root_path, "branding")
    return send_from_directory(branding_path, filename)


def branding_css(filename):
    """
    Renders and serves a CSS file by injecting branding colors into it.

    This function takes a CSS filename, ensures it has the proper file extension,
    and attempts to locate the corresponding Jinja2 template file within the
    static CSS folder. If the file is found, it reads the template and renders it
    using the application’s branding color variables. The result is then returned
    as a CSS response. If the file is not found, a 404 response with an error
    message is returned.

    Args:
        filename: str. The name of the CSS file to render. If the provided filename
            does not end with ".css", the extension will be appended automatically.

    Returns:
        Response. A Flask Response object containing the rendered CSS file or a
        404 error message if the file does not exist.

    Raises:
        None.
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
