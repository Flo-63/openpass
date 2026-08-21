"""
===============================================================================
Project   : openpass
Module    : core/config.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is a configuration module for the openpass application. It
    provides functions to load and manage application settings from environment
    variables and set default values if variables are not provided. The module
    initializes various settings required for application functionality, including
    OAuth configurations, SMTP settings, logging settings, file upload paths, and
    encryption keys. Additionally, it ensures necessary directories are created for
    file uploads.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# Standard Library
import os
import secrets
import warnings
from datetime import timedelta

# Third-Party
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import Flask

# Opt-in escape hatch for local development without a .env file. When set, missing
# secrets are replaced by *random, per-process* values instead of aborting the start.
# Random values keep sessions and tokens unforgeable; they simply do not survive a
# restart. Never set this in production.
DEV_INSECURE = os.getenv("OPENPASS_DEV_INSECURE") == "1"


def _require_secret(name: str) -> str:
    """
    Reads a mandatory secret from the environment.

    Fails loudly when the secret is absent instead of falling back to a value that is
    readable in the source tree. A well-known fallback secret would let anyone forge
    session cookies and membership tokens, so an unset secret must stop the boot.

    Args:
        name (str): Name of the environment variable holding the secret.

    Returns:
        str: The configured secret, or a random per-process value when
        `OPENPASS_DEV_INSECURE=1` is set.

    Raises:
        RuntimeError: If the secret is not set and the development escape hatch is off.
    """
    value = os.getenv(name)
    if value:
        return value

    if DEV_INSECURE:
        generated = secrets.token_urlsafe(48)
        warnings.warn(
            f"{name} is not set – using a random value for this process only "
            f"(OPENPASS_DEV_INSECURE=1). Sessions and tokens are invalidated on restart.",
            RuntimeWarning,
            stacklevel=2,
        )
        return generated

    raise RuntimeError(
        f"{name} is not set. Configure it via the environment (see .env.example). "
        f"For local development only, set OPENPASS_DEV_INSECURE=1 to generate an "
        f"ephemeral value instead."
    )


def _parse_admin_emails(raw: str) -> list[str]:
    """
    Parses the comma-separated `ADMIN_EMAILS` value into a normalised allow-list.

    Entries are stripped and lower-cased, and empty entries are dropped. Dropping empty
    entries matters: a trailing comma or an unset variable would otherwise produce a
    list containing the empty string, which any user with an empty email address would
    match.

    Args:
        raw (str): Raw comma-separated value from the environment.

    Returns:
        list[str]: Normalised, non-empty administrator email addresses.
    """
    return [entry.strip().lower() for entry in (raw or "").split(",") if entry.strip()]


def load_config(app: Flask) -> None:
    """
    Loads and configures application settings from environment variables, with default
    fallbacks for core functionality, OAuth, email, database, logging, encryption, and
    rate limiting. This function ensures the Flask application's configuration is initialized
    based on its environment, setting up defaults when environment variables are missing.

    Parameters:
        app (Flask): The Flask application instance whose configuration is to be set.

    Raises:
        None

    Returns:
        None
    """
    if 'IS_CONTAINER' not in os.environ:
        load_dotenv()

    # Core application settings
    app.config['SECRET_KEY'] = _require_secret('SECRET_KEY')
    app.config['TOKEN_MAX_AGE_SECONDS'] = int(os.getenv('TOKEN_MAX_AGE_SECONDS', 3600))

    # Session hardening: signed session cookies carry no expiry of their own, so a
    # captured cookie would otherwise stay valid forever. Making the session permanent
    # puts an absolute expiry into the cookie payload that the server enforces.
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
        seconds=int(os.getenv('SESSION_LIFETIME_SECONDS', 12 * 3600))
    )
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', '1') == '1'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Upload limits – applies to every request body, including photo uploads.
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_BYTES', 8 * 1024 * 1024))

    # Upload limits, part two: MAX_CONTENT_LENGTH bounds the bytes on the wire, not the
    # pixels they decode to. A uniformly coloured PNG of 13000x13000 fits in 160 KB and
    # expands to roughly 500 MB once converted to RGB, which is enough to push a small
    # worker into the OOM killer. Bound the decoded resolution as well.
    app.config['MAX_PHOTO_PIXELS'] = int(os.getenv('MAX_PHOTO_PIXELS', 50_000_000))

    # OAuth configuration – no defaults: credentials must never live in the source tree.
    app.config['OAUTH_NAME'] = os.getenv("OAUTH_NAME", "Rocket.Chat")
    app.config['OAUTH_DISCOVERY_URL'] = os.getenv("OAUTH_DISCOVERY_URL")
    app.config['OAUTH_CLIENT_ID'] = os.getenv("OAUTH_CLIENT_ID")
    app.config['OAUTH_CLIENT_SECRET'] = os.getenv("OAUTH_CLIENT_SECRET")
    app.config['OAUTH_AUTHORIZE_URL'] = os.getenv("OAUTH_AUTHORIZE_URL")
    app.config['OAUTH_TOKEN_URL'] = os.getenv("OAUTH_TOKEN_URL")
    app.config['OAUTH_API_URL'] = os.getenv("OAUTH_API_URL")
    app.config['OAUTH_USERINFO_URL'] = os.getenv('OAUTH_USERINFO_URL')
    # How to treat an identity provider that does not vouch for the email address.
    # The address is the identity anchor for role lookup, photo access and admin
    # authorisation, so trusting an unverified one means trusting whatever the user
    # typed into their chat profile.
    #   require – reject the login unless email_verified is true
    #   warn    – allow, but log every unverified login (default)
    #   off     – allow silently
    # Rocket.Chat reports email_verified=false whenever Accounts_EmailVerification is
    # disabled, so "require" only becomes usable once verification is on at the IdP.
    verification_mode = os.getenv('OAUTH_EMAIL_VERIFICATION', 'warn').strip().lower()
    if verification_mode not in ('require', 'warn', 'off'):
        warnings.warn(
            f"OAUTH_EMAIL_VERIFICATION={verification_mode!r} is not one of "
            f"require/warn/off – falling back to 'warn'.",
            RuntimeWarning,
            stacklevel=2,
        )
        verification_mode = 'warn'
    app.config['OAUTH_EMAIL_VERIFICATION'] = verification_mode

    # URL and server configuration
    app.config['PREFERRED_URL_SCHEME'] = os.getenv('PREFERRED_URL_SCHEME')
    app.config['SERVER_NAME'] = os.getenv('SERVER_NAME')

    # Email configuration
    app.config['SMTP_SERVER'] = os.getenv('SMTP_SERVER')
    app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', 587))
    app.config['SMTP_USERNAME'] = os.getenv('SMTP_USERNAME')
    app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD')
    app.config['MAIL_SENDER_NAME'] = os.getenv('MAIL_SENDER_NAME')
    app.config['MAIL_SENDER_ADDRESS'] = os.getenv('MAIL_SENDER_ADDRESS')

    # Database and admin configuration
    app.config['MEMBER_DB'] = os.getenv("MEMBER_DB", "members.db")
    app.config['ADMIN_EMAILS'] = _parse_admin_emails(os.getenv("ADMIN_EMAILS", ""))
    app.config['CSV_DELIMITER'] = os.getenv("CSV_DELIMITER", ";")

    # Rate limiting configuration
    app.config['RATE_LIMIT_STORAGE'] = os.getenv("RATE_LIMIT_STORAGE", "redis://localhost:6379")
    app.config["EMAIL_LOGIN_RATE_LIMIT"] = os.getenv("EMAIL_LOGIN_RATE_LIMIT", "5 per hour")
    app.config["SEND_CARD_RATE_LIMIT"] = os.getenv("SEND_CARD_RATE_LIMIT", "10 per hour")
    app.config["CSP_REPORT_URI"] = os.getenv("CSP_REPORT_URI")
    # Send the CSP as an enforcing header instead of report-only. Off by default
    # because the current front-end needs additional directives (see core/middleware.py)
    # – switch on once logs/csp.log is clean.
    app.config["CSP_ENFORCE"] = os.getenv("CSP_ENFORCE", "0") == "1"

    # Logging configuration
    app.config['LOG_PATH'] = os.getenv('LOG_PATH', os.path.join(os.path.dirname(__file__), '../logs'))
    app.config['SERVER_LOG_PATH'] = os.getenv('SERVER_LOG_PATH', app.config['LOG_PATH'])

    # Log levels for different components
    app.config['LOG_LEVEL'] = os.getenv('LOG_LEVEL', 'INFO')
    app.config['CONSOLE_LOG_LEVEL'] = os.getenv('CONSOLE_LOG_LEVEL', 'INFO')
    app.config['IMPORT_LOG_LEVEL'] = os.getenv('IMPORT_LOG_LEVEL', 'INFO')
    app.config['AUTH_LOG_LEVEL'] = os.getenv('AUTH_LOG_LEVEL', 'INFO')
    app.config['TASK_LOG_LEVEL'] = os.getenv('TASK_LOG_LEVEL', 'INFO')
    app.config['CSP_LOG_LEVEL'] = os.getenv('CSP_LOG_LEVEL', 'WARNING')

    # Storage location for encrypted photos
    app.config['PHOTO_UPLOAD_FOLDER'] = os.path.abspath(os.path.join(os.getcwd(), "uploads", "photos"))
    os.makedirs(app.config["PHOTO_UPLOAD_FOLDER"], exist_ok=True)

    # Key for symmetric photo encryption. Must be a real secret: deriving it from the
    # member's email address (as an earlier version did) provides no confidentiality,
    # because the email address is not secret and the stored filename is derived from it.
    photo_key = os.getenv("PHOTO_ENCRYPTION_KEY")
    if not photo_key and DEV_INSECURE:
        photo_key = secrets.token_bytes(32).hex()
        warnings.warn(
            "PHOTO_ENCRYPTION_KEY is not set – using a random value for this process "
            "only (OPENPASS_DEV_INSECURE=1). Previously stored photos stay readable, "
            "newly uploaded ones become unreadable after a restart.",
            RuntimeWarning,
            stacklevel=2,
        )
    if not photo_key:
        raise RuntimeError(
            "PHOTO_ENCRYPTION_KEY is not set. Generate one with `openssl rand -hex 32` "
            "and configure it via the environment (see .env.example)."
        )

    try:
        photo_key_bytes = bytes.fromhex(photo_key)
    except ValueError as exc:
        raise RuntimeError("PHOTO_ENCRYPTION_KEY must be hex-encoded.") from exc
    if len(photo_key_bytes) != 32:
        raise RuntimeError(
            f"PHOTO_ENCRYPTION_KEY must be 32 bytes (64 hex characters), "
            f"got {len(photo_key_bytes)}."
        )
    app.config["PHOTO_ENCRYPTION_KEY"] = photo_key_bytes

    fernet_key = os.getenv('FERNET_KEY')

    if not fernet_key:
        if not DEV_INSECURE:
            raise RuntimeError(
                "FERNET_KEY is not set. Generate one with "
                "`python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"` and configure it via the "
                "environment (see .env.example)."
            )
        fernet_key = Fernet.generate_key()
        warnings.warn(
            "FERNET_KEY is not set – using a random key for this process only "
            "(OPENPASS_DEV_INSECURE=1). Existing member data will not decrypt.",
            RuntimeWarning,
            stacklevel=2,
        )
    if isinstance(fernet_key, str):
        fernet_key = fernet_key.encode()  # Umwandeln in bytes, nur falls nötig

    app.config['FERNET_KEY'] = fernet_key

