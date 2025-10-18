"""
===============================================================================
Project   : openpass
Module    : core/oauth_client.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides OAuth client initialization and configuration
            for the Flask application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


# Standard Library
import logging

# Third-Party
from authlib.integrations.flask_client import OAuth

# Initialize logger for OAuth-related events
logger = logging.getLogger("main_logger")

# Create OAuth instance
oauth = OAuth()

def init_oauth(app):
    """
    Initializes the OAuth framework and registers an OAuth client using either OpenID
    Connect (OIDC) discovery or manual configuration. The method configures the
    necessary OAuth parameters, sets up the redirect URI, and attaches the OAuth
    client to the Flask application instance.

    Raises:
        Exception: If there is an error during the initialization of the OAuth framework
        or registration of the OAuth client.

    Args:
        app (Flask): A Flask application instance to attach the OAuth client to. The app
        configuration must include relevant OAuth parameters such as client ID, client
        secret, and URLs for authorization and token exchange. The method also requires
        the SERVER_NAME and optionally the PREFERRED_URL_SCHEME configuration to
        construct the redirect URI.
    """
    # Construct the redirect URI using app configuration
    redirect_uri = f"{app.config.get('PREFERRED_URL_SCHEME', 'https')}://{app.config.get('SERVER_NAME', '')}/authorized"
    # Get OAuth provider name from config or use default
    provider_name = app.config.get("OAUTH_NAME", "oauth")

    try:
        # Initialize OAuth framework with Flask app
        oauth.init_app(app)
    except Exception as e:
        logger.error("Error initializing OAuth framework: %s", e, exc_info=True)
        raise

    # Check if OpenID Connect discovery URL is configured
    discovery_url = app.config.get("OAUTH_DISCOVERY_URL")
    if discovery_url:
        logger.debug(f"OIDC Discovery URL detected: {discovery_url}")
        try:
            # Register OAuth client using OpenID Connect discovery
            client = oauth.register(
                name="oauth",
                server_metadata_url=discovery_url,
                client_id=app.config["OAUTH_CLIENT_ID"],
                client_secret=app.config["OAUTH_CLIENT_SECRET"],
                client_kwargs={"scope": "openid email profile"},  # Standard OpenID Connect scopes
            )
            logger.info("OIDC Discovery successfully used.")
        except Exception as e:
            logger.error("OIDC Discovery registration failed: %s", e, exc_info=True)
            raise
    else:
        logger.warning("No OAUTH_DISCOVERY_URL found, falling back to manual configuration.")
        # Verify presence of critical configuration parameters
        for param in ("OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_AUTHORIZE_URL", "OAUTH_TOKEN_URL", "OAUTH_USERINFO_URL"):
            if not app.config.get(param):
                logger.error(f"Critical OAuth parameter missing: {param}")
        try:
            # Register OAuth client using manual configuration
            client = oauth.register(
                name=provider_name,
                client_id=app.config["OAUTH_CLIENT_ID"],
                client_secret=app.config["OAUTH_CLIENT_SECRET"],
                authorize_url=app.config["OAUTH_AUTHORIZE_URL"],
                access_token_url=app.config["OAUTH_TOKEN_URL"],
                userinfo_endpoint=app.config["OAUTH_USERINFO_URL"],
                redirect_uri=redirect_uri,
                client_kwargs={"scope": "openid email profile"},  # Standard OpenID Connect scopes
            )
            logger.info("Manual OAuth2 configuration successfully applied.")
        except Exception as e:
            logger.error("Manual OAuth2 registration failed: %s", e, exc_info=True)
            raise

    logger.debug(f"OAuth client ({provider_name}) successfully registered with redirect URI: {redirect_uri}")
    # Attach OAuth client to Flask app instance for later use
    app.oauth_client = client