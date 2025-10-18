"""
===============================================================================
Project   : openpass
Module    : core/context_processors.py
Created   : 2025-10-17
Author    : Florian
Purpose   : In this module, context processors are defined to inject branding
    information and branding colors into the Flask application's template context.
    These processors are used to dynamically provide branding-related data to
    templates, enhancing the customization and appearance of the application's
    user interface.
@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""



from flask import current_app

def inject_branding():
    """
    Injects branding information from the application's configuration.

    This function retrieves the branding configuration from the current Flask
    application context. The branding information is stored in the application's
    configuration under the key 'BRANDING'. If the key does not exist, an empty
    dictionary is returned.

    Returns:
        dict: A dictionary containing the branding configuration, or an empty
        dictionary if the branding configuration is not set.
    """
    return {"branding": current_app.config.get("BRANDING", {})}

def inject_branding_colors():
    """
    Fetches and returns a dictionary containing branding colors based on the application's
    configuration. If specific branding colors are not defined in the configuration, default
    values are provided.

    Returns
    -------
    dict
        A dictionary containing keys for various branding colors such as theme colors,
        background colors, text colors, and alert/success/warning/info colors. Default values
        are used for any missing configuration.
    """
    branding = current_app.config.get("BRANDING", {})
    return {
        "theme_color": branding.get("theme_color", "#1C91FF"),
        "theme_color_dark": branding.get("theme_color_dark", "#1176cc"),
        "background_light": branding.get("background_light", "#f3f3f3"),
        "background_dark": branding.get("background_dark", "#1a1a1a"),
        "text_primary": branding.get("text_primary", "#333333"),
        "text_secondary": branding.get("text_secondary", "#777777"),
        "alert_color": branding.get("alert_color", "#E74C3C"),
        "success_color": branding.get("success_color", "#2ECC71"),
        "warning_color": branding.get("warning_color", "#F39C12"),
        "info_color": branding.get("info_color", "#3498DB")
    }