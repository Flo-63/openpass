"""
===============================================================================
Project   : openpass
Module    : app.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module defines the main application instance for the openpass
            project. It initializes and configures a Flask application with HTTP
            server middleware, CSRF protection, request limiter, OAuth support,
            encryption, logging, and various blueprints for handling different
            application routes and functionalities. The function also ensures
            secure cookies and integrates various Flask extensions for enhancing
            application behavior.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# app.py
# Standard Library
import logging

# Third-Party
from cryptography.fernet import Fernet
from flask import Flask, render_template, request, send_from_directory, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Local/Application
from core import extensions as ext
from core.config import load_config
from core.loggers import configure_logging
from core.middleware import csp_middleware
from core.oauth_client import init_oauth


csrf = CSRFProtect()


def create_app():
    """
    Creates and configures the Flask application instance.

    This function sets up the core configurations and integrations for the Flask
    application, including proxy handling, configuration loading, branding-related
    routes and context processors, CSRF protection, rate limiting, encryption,
    extensions initialization, logging, CSP middleware, and application blueprints
    registration. The application is secured with session cookies configured for
    security and optional OAuth integration is also initialized.

    Returns:
        Flask: A fully configured Flask application instance.

    Raises:
        RuntimeError: If the required `FERNET_KEY` configuration is not set.
    """
    app = Flask(__name__)

    # Vertrauen in Proxy-Header für HTTPS und Host
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # load config
    load_config(app)

    from core.branding import load_branding, branding_file, branding_css
    load_branding(app)

    # Branding-Routen registrieren
    app.add_url_rule("/branding/<path:filename>", view_func=branding_file)
    app.add_url_rule("/branding/css/<path:filename>", view_func=branding_css)

    #register branding injection
    # Branding-Kontextprozessoren registrieren
    from core.context_processors import inject_branding, inject_branding_colors
    app.context_processor(inject_branding)
    app.context_processor(inject_branding_colors)

    # CSRF-Schutz aktivieren
    csrf.init_app(app)

    # Request Limiter Schutz
    ext.limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],
        storage_uri=app.config.get("RATE_LIMIT_STORAGE", "redis://localhost:6379")
    )
    ext.limiter.init_app(app)


    # Mail extension initialisieren
    ext.mail.init_app(app)


    # Verschlüsselung
    fernet_key = app.config.get("FERNET_KEY")
    if not fernet_key:
        raise RuntimeError("FERNET_KEY ist nicht gesetzt!")
    ext.fernet = Fernet(fernet_key)

    # Flask Login Manager
    ext.login_manager.init_app(app)
    ext.login_manager.login_view = "auth.login_page"

    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # OAuth atuhlib client für RC
    init_oauth(app)

    # Logger initialisieren (main, import, csp, auth)
    configure_logging(app)

    # CSP Middleware aktivieren
    app = csp_middleware(app, report_only=True)

    # Blueprints registrieren (auth, cards, profile)
    from blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    from blueprints.cards import cards_bp
    app.register_blueprint(cards_bp)

    from blueprints.admin.admin import admin_bp
    app.register_blueprint(admin_bp)

    from blueprints.main import main_bp
    app.register_blueprint(main_bp)

    csrf.exempt(app.view_functions['main.csp_report'])

    # Error Handler für flask limiter - Anzeige sinnvoller Info an User
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """
        Handles a rate limit error (HTTP status code 429) by rendering a specific
        template with a retry time. The function attempts to extract the retry
        time from the exception description. If unsuccessful, it falls back to
        a default retry time.

        :param e: The exception object representing the rate limit error. It is
            expected to have attributes such as `description` to parse the retry
            time, if available.
        :return: A rendered HTML template for the error page, including the retry
            time, and an HTTP status code of 429.
        """
        retry_after = 60  # fallback
        if hasattr(e, "description") and "in" in str(e.description):
            try:
                retry_after = int(str(e.description).split("in")[-1].split(" ")[1])
            except Exception:
                pass
        return render_template("rate_limited.html", retry_after=retry_after), 429

    return app



def setup_logging(app):
    """
    Configures logging for the given application based on its debug mode.

    If the application is not in debug mode, it utilizes the Gunicorn logging
    setup to configure the application logger. If the application is in debug
    mode, a basic debug-level logging is configured.

    Args:
        app: The application object for which logging is to be configured.

    Returns:
        None
    """
    if not app.debug:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    else:
        logging.basicConfig(level=logging.DEBUG)


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=5000)