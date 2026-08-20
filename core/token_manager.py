"""
===============================================================================
Project   : openpass
Module    : core/token_manager.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides functionality for generating and validating secure tokens for user authentication.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# Standard Library
import json
import logging

# Third-Party
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer
)

# Local
from core import extensions as ext

# Initialize logger for authentication-related events
auth_logger = logging.getLogger("auth_logger")


def _get_fernet() -> Fernet:
    """
    Returns the application's Fernet instance for payload encryption.

    Falls back to constructing one from `FERNET_KEY` when the shared instance has not
    been bound yet (for example when a token is generated outside the app factory).

    Returns:
        Fernet: The cipher used to encrypt token payloads.
    """
    if ext.fernet is not None:
        return ext.fernet
    return Fernet(current_app.config["FERNET_KEY"])


def generate_token(user_data: dict):
    """
    Generates a secure token for the given user data.

    The payload is encrypted with Fernet before it is signed. `URLSafeTimedSerializer`
    only signs – it does not encrypt – so a plain payload would expose the member's
    email address, role and join year to anyone who scans the QR code the token is
    embedded in. Encrypting first keeps the signature (and therefore the max-age check)
    intact while making the payload opaque to the bearer.

    Parameters:
    user_data: dict
        A dictionary containing the user data to be serialized into a secure token.

    Returns:
    str
        A serialized token string generated from the provided user data.

    Raises:
    TypeError
        If the input user_data is not a dictionary.
    """
    if not isinstance(user_data, dict):
        auth_logger.error(f"generate_token: user_data is not a dict! Value: {repr(user_data)}", exc_info=True)
        raise TypeError("user_data must be a dictionary")

    payload = _get_fernet().encrypt(json.dumps(user_data).encode()).decode()

    # Create serializer with application secret key and custom salt
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt="#AllezRCB")

    return s.dumps(payload)

def decode_token(token):
    """
    Decodes a provided token using a URL-safe timed serializer.

    Verifies the signature and age of the token, then decrypts the payload. Tokens
    issued before payload encryption was introduced carried the dictionary directly;
    those are still accepted so that membership cards already in circulation keep
    working until they expire.

    Args:
        token: str
            The token to be decoded.

    Returns:
        dict or None:
            The decoded user data if valid, or None if the token is invalid or expired.
    """
    # Get token expiration time from app config
    max_age = current_app.config.get("TOKEN_MAX_AGE_SECONDS")
    # Initialize serializer with same secret key and salt used for token generation
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt="#AllezRCB")
    try:
        payload = s.loads(token, max_age=max_age)
    except SignatureExpired:
        auth_logger.info(f"Token expired: {str(token)[:12]}...")
        return None
    except BadSignature:
        auth_logger.warning(f"Invalid token: {str(token)[:12]}...")
        return None

    # Legacy token: payload was stored unencrypted.
    if isinstance(payload, dict):
        auth_logger.info("Accepted legacy token with unencrypted payload.")
        return payload

    try:
        return json.loads(_get_fernet().decrypt(payload.encode()).decode())
    except (InvalidToken, ValueError, AttributeError):
        auth_logger.warning(f"Token payload could not be decrypted: {str(token)[:12]}...")
        return None

def get_serializer():
    """
    Retrieve a serializer initialized with a secret key and a specific salt for email-based login.

    Reads the secret from the application configuration rather than straight from the
    environment, so that email-login tokens are derived from exactly the same key as
    session cookies and membership tokens. `load_config` already guarantees the key is
    present, so no fallback is needed here.

    Returns:
        URLSafeTimedSerializer: A serializer configured with the secret key and specific salt.
    """
    # Create and return serializer with email-specific salt
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="email-login")

def generate_email_token(email: str):
    """
    Generates a token for the specified email address.

    This function utilizes a serializer to create a secure, encoded
    token for the given email. The token can be used for various
    purposes such as email verification or authentication.

    Args:
        email (str): The email address to generate a token for.

    Returns:
        str: A serialized token corresponding to the provided email.
    """
    s = get_serializer()
    return s.dumps(email)

def verify_email_token(token, max_age=900):
    """
    Verify an email token for authenticity and validity within a specific time frame.

    This method verifies the authenticity of the provided email token and checks its validity
    according to the maximum age allowed. It also provides logging for various outcomes, such
    as expired tokens, invalid tokens, or unexpected errors during the verification process.

    Parameters:
    token: str
        The email token to be verified.
    max_age: int
        The maximum age of the token in seconds. Defaults to 900 seconds.

    Returns:
    str or None
        Returns the email address if the token is successfully verified.
        Returns None if the token is expired, invalid, or an error occurs during verification.
    """
    s = get_serializer()
    try:
        email = s.loads(token, max_age=max_age)
        # Debug logging disabled
        # auth_logger.debug(f"Email token successfully verified for: {email[:4]}***")
        return email
    except SignatureExpired:
        auth_logger.info(f"Email token expired: {token[:12]}...")
        return None
    except BadSignature:
        auth_logger.warning(f"Invalid email token: {token[:12]}...")
        return None
    except Exception as e:
        auth_logger.error(f"Unexpected error during email token verification: {e}", exc_info=True)
        return None