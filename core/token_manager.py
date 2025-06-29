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
    Generates a secure token for a given user data dictionary. The function uses a URLSafeTimedSerializer
    to serialize and secure the provided user data. The secret key and salt values are sourced from the
    application's configuration.

    :param user_data: A dictionary containing user-specific data to be serialized into the token.
    :type user_data: dict
    :return: A serialized and secure token created from the provided user data.
    :rtype: str
    :raises TypeError: If the provided `user_data` is not of type dictionary.
    """
    if not isinstance(user_data, dict):
        auth_logger.error(f"generate_token: user_data is not a dict! Value: {repr(user_data)}", exc_info=True)
        raise TypeError("user_data must be a dictionary")

    # Create serializer with application secret key and custom salt
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt="#AllezRCB")

    return s.dumps(user_data)

def decode_token(token):
    """
    Decode a token using a URLSafeTimedSerializer.

    This function attempts to decode a given token using a secret key and a salt
    defined in the application configuration. It verifies that the token has not
    expired and checks its validity. If the token has expired, the function logs an
    informational message. If the token is invalid, it logs a warning message.

    :param token: The token to be decoded.
    :type token: str
    :return: The decoded token data if valid, otherwise None.
    :rtype: dict or None
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
    Returns a URLSafeTimedSerializer instance initialized with the application's SECRET_KEY.

    This function retrieves the SECRET_KEY environment variable for initializing the serializer.
    If the SECRET_KEY is not set, it logs an error message using the application's logging system.

    :raises RuntimeError: Raised if the SECRET_KEY environment variable is not set.
    :return: A URLSafeTimedSerializer instance configured with the retrieved SECRET_KEY and 
        a predefined salt.
    :rtype: URLSafeTimedSerializer
    """
    # Retrieve secret key from environment variables
    secret = os.getenv("SECRET_KEY")
    if not secret:
        auth_logger.error("get_serializer: SECRET_KEY not set!", exc_info=True)
    # Create and return serializer with email-specific salt
    return URLSafeTimedSerializer(secret, salt="email-login")

def generate_email_token(email: str):
    """
    Generate a token for the given email using a serializer.

    This function creates a secure token for the provided email address by
    using a serializer. The token can be utilized for email verification,
    password reset, or other email-based authentication workflows.

    :param email: The email address for which to generate the token.
    :type email: str
    :return: A serialized token representing the provided email address.
    :rtype: str
    """
    s = get_serializer()
    return s.dumps(email)

def verify_email_token(token, max_age=900):
    """
    Verifies the validity of an email verification token.

    This function takes an email verification token and checks its validity
    by attempting to decode it using a serializer. The function validates
    the token within a specified timeframe and handles several potential
    issues like expiration or invalidity. It returns the email address
    associated with the token if successful; otherwise, it logs the issue
    appropriately and returns None.

    :param token: The email verification token to be validated.
    :type token: str
    :param max_age: The maximum age (in seconds) for which the token is valid.
                   Defaults to 900 seconds (15 minutes).
    :type max_age: int, optional
    :return: The email address retrieved from the token if valid, or None.
    :rtype: Union[str, None]
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