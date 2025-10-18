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

# Third-Party
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import Flask


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
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret')
    app.config['TOKEN_MAX_AGE_SECONDS'] = int(os.getenv('TOKEN_MAX_AGE_SECONDS', 3600))

    # OAuth configuration
    app.config['OAUTH_NAME'] = os.getenv("OAUTH_NAME", "Rocket.Chat")
    app.config['OAUTH_DISCOVERY_URL'] = os.getenv("OAUTH_DISCOVERY_URL")
    app.config['OAUTH_CLIENT_ID'] = os.getenv("OAUTH_CLIENT_ID", "Qv5BYkBSYb6X789ns")
    app.config['OAUTH_CLIENT_SECRET'] = os.getenv("OAUTH_CLIENT_SECRET", "DTwznxkh29zzEX_qA3KQht8xsvCsictBFjzU0lO2gXo")
    app.config['OAUTH_AUTHORIZE_URL'] = os.getenv("OAUTH_AUTHORIZE_URL", "https://rcbchat.de/oauth/authorize")
    app.config['OAUTH_TOKEN_URL'] = os.getenv("OAUTH_TOKEN_URL", "https://rcbchat.de/oauth/token")
    app.config['OAUTH_API_URL'] = os.getenv("OAUTH_API_URL", "https://rcbchat.de/api/v1/")
    app.config['OAUTH_USERINFO_URL'] = os.getenv('OAUTH_USERINFO_URL')

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
    app.config['ADMIN_EMAILS'] = os.getenv("ADMIN_EMAILS", "").split(",")
    app.config['CSV_DELIMITER'] = os.getenv("CSV_DELIMITER", ";")

    # Rate limiting configuration
    app.config['RATE_LIMIT_STORAGE'] = os.getenv("RATE_LIMIT_STORAGE", "redis://localhost:6379")
    app.config["EMAIL_LOGIN_RATE_LIMIT"] = os.getenv("EMAIL_LOGIN_RATE_LIMIT", "5 per hour")
    app.config["CSP_REPORT_URI"] = os.getenv("CSP_REPORT_URI")

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

    # Key for symmetric photo encryption
    photo_key = os.getenv("PHOTO_ENCRYPTION_KEY")
    if photo_key:
        app.config["PHOTO_ENCRYPTION_KEY"] = bytes.fromhex(photo_key)
    else:
        print("⚠️ No PHOTO_ENCRYPTION_KEY set. AES encryption may fail.")


    fernet_key = os.getenv('FERNET_KEY')

    if fernet_key is None:
        fernet_key = Fernet.generate_key()
        print("⚠️ WARNING: No FERNET_KEY set. Using random key for testing.")
    elif isinstance(fernet_key, str):
        fernet_key = fernet_key.encode()  # Umwandeln in bytes, nur falls nötig

    app.config['FERNET_KEY'] = fernet_key

