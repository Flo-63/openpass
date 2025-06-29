from flask import current_app

def inject_branding():
    """
    Injects branding configuration into the response.

    This function retrieves branding information configured in the
    Flask application and returns it as a dictionary. It reads the
    "BRANDING" entry from the application configuration and includes it
    in the response if available.

    Returns:
        dict: A dictionary containing the branding configuration.
    """
    return {"branding": current_app.config.get("BRANDING", {})}

def inject_branding_colors():
    """
    Provides branding color variables to templates by injecting them into the template
    context. The function retrieves branding configurations from the application config
    and defines default values for each branding color if the configurations are not
    available.

    Returns
    -------
    dict
        A dictionary containing branding colors available as variables in the template
        context. Keys include the following:
        - theme_color
        - theme_color_dark
        - background_light
        - background_dark
        - text_primary
        - text_secondary
        - alert_color
        - success_color
        - warning_color
        - info_color
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