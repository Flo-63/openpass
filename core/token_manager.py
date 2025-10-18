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
import logging
import os

# Third-Party
from flask import current_app
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer
)

# Initialize logger for authentication-related events
auth_logger = logging.getLogger("auth_logger")

def generate_token(user_data: dict):
    """
    Generates a secure token for the given user data by serializing it with a secret
    key and a custom salt. The function ensures that the input is a dictionary,
    providing a reliable mechanism for encoding user-specific information.

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

    # Create serializer with application secret key and custom salt
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt="#AllezRCB")

    return s.dumps(user_data)

def decode_token(token):
    """
    Decodes a provided token using a URL-safe timed serializer. The function attempts to
    verify the validity of the token by checking for expiration time and signature. If the
    token is invalid or expired, corresponding actions are logged and None is returned.

    Args:
        token: str
            The token to be decoded.

    Returns:
        str or None:
            The decoded token if valid, or None if the token is invalid or expired.

    Raises:
        SignatureExpired:
            Raised if the token has expired based on the configured expiration time.
        BadSignature:
            Raised if the token's signature is invalid.
    """
    # Get token expiration time from app config
    max_age = current_app.config.get("TOKEN_MAX_AGE_SECONDS")
    # Initialize serializer with same secret key and salt used for token generation
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt="#AllezRCB")
    try:
        return s.loads(token, max_age=max_age)
    except SignatureExpired:
        auth_logger.info(f"Token expired: {token[:12]}...")
        return None
    except BadSignature:
        auth_logger.warning(f"Invalid token: {token[:12]}...")
        return None

def get_serializer():
    """
    Retrieve a serializer initialized with a secret key and a specific salt for email-based login.

    This function fetches the secret key from the environment variables and uses it to create a
    new `URLSafeTimedSerializer` with a salt specific for email login functionality. If the
    required secret key is not found in the environment variables, an error will be logged.

    Raises:
        KeyError: If the 'SECRET_KEY' environment variable is not present or accessible.

    Returns:
        URLSafeTimedSerializer: A serializer configured with the secret key and specific salt.
    """
    # Retrieve secret key from environment variables
    secret = os.getenv("SECRET_KEY")
    if not secret:
        auth_logger.error("get_serializer: SECRET_KEY not set!", exc_info=True)
    # Create and return serializer with email-specific salt
    return URLSafeTimedSerializer(secret, salt="email-login")

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