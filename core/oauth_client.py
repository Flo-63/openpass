# oauth_client.py
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
    Initializes the OAuth framework for the given Flask application.

    This function sets up an OAuth client for the Flask web application using
    provided configuration parameters. It attempts to register the client using
    either an OAuth discovery URL (if available) or manual configuration details.
    Once registered, the client is attached to the application instance as 
    `app.oauth_client`. Detailed logging is performed throughout the initialization
    process to capture success/failure and provide debug information.

    :param flask.Flask app: The Flask application object to which the OAuth
        configuration and client registration should be applied.

    :return: None

    Configuration Parameters Required:
    - PREFERRED_URL_SCHEME: Protocol scheme (default: 'https')
    - SERVER_NAME: Server domain name
    - OAUTH_NAME: Provider name (default: 'oauth')
    - OAUTH_DISCOVERY_URL: OpenID Connect discovery URL (optional)
    - OAUTH_CLIENT_ID: OAuth client identifier
    - OAUTH_CLIENT_SECRET: OAuth client secret
    - OAUTH_AUTHORIZE_URL: Authorization endpoint URL (if no discovery URL)
    - OAUTH_TOKEN_URL: Token endpoint URL (if no discovery URL)
    - OAUTH_USERINFO_URL: User info endpoint URL (if no discovery URL)
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