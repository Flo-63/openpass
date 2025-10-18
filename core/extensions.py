"""
===============================================================================
Project   : openpass
Module    : core/extensions.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is a module that contains extensions for the Flask application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

# extensions.py
# Standard Library
import logging
import sqlite3
import hashlib
import os
from functools import wraps

# Third-Party
from flask import current_app, abort, session, request
from flask_mail import Mail
from flask_login import LoginManager, UserMixin, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet

# Initialize extensions that will be bound later in app.py / app factory
mail = Mail()
login_manager = LoginManager()
limiter = None

fernet = None

auth_logger = logging.getLogger("auth_logger")

class SimpleUser(UserMixin):
    """
    Represents a simplified user entity with basic user attributes.

    This class is designed to provide a lightweight representation of a user,
    including attributes such as ID, first name, last name, email, and role. It is
    intended to be used in applications where only basic user information is
    needed. It also inherits from UserMixin to maintain compatibility with Flask
    user mechanisms and tools.
    """
    def __init__(self, user_id, first_name=None, last_name=None, email=None, role=None):
        self.id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    """
    Loads a user object by retrieving and verifying user information from a session and database.

    This function acts as a user loader for integration with Flask-Login. It fetches user
    details from session data, extracts the user's email, and subsequently attempts to
    retrieve the user's role from a database (if available). Sensitive information, such as
    roles and email hashes, is decrypted to securely load relevant user details.

    Parameters:
    user_id : str
        The unique identifier of the user, typically provided by the authentication
        backend or system.

    Returns:
    SimpleUser
        An instance of the SimpleUser class containing user details such as unique ID, first
        name, last name, email, and role.

    Raises:
    Exception
        A generic exception is handled and ignored during the database operations or decryption
        process, ensuring the function always returns a valid SimpleUser object even if errors
        occur.
    """
    # Get email from session
    email = None
    info = None
    if "email_userinfo" in session:
        info = session["email_userinfo"]
    elif "oauth_userinfo" in session:
        info = session["oauth_userinfo"]

    if info:
        email = info.get("email")
    role = ""
    if email:
        try:
            # Get user role from database
            DB_PATH = os.path.join("instance", current_app.config["MEMBER_DB"])
            fernet = Fernet(current_app.config["FERNET_KEY"])
            email_hash = hashlib.sha256(email.encode()).hexdigest()
            with sqlite3.connect(DB_PATH) as con:
                cur = con.cursor()
                row = cur.execute(
                    "SELECT role FROM members WHERE email_hash=?", (email_hash,)
                ).fetchone()
                if row and row[0]:
                    # Decrypt stored role
                    role = fernet.decrypt(row[0]).decode()
        except Exception:
            role = ""
    return SimpleUser(
        user_id=info.get("username") or info.get("email") or user_id if info else user_id,
        first_name=info.get("first_name") or info.get("given_name") if info else None,
        last_name=info.get("last_name") or info.get("family_name") if info else None,
        email=email,
        role=role
    )


def admin_required(view_func):
    """
    Decorator to restrict access to a view function to administrators.

    This decorator ensures that only users with email addresses
    listed in the application's configuration (`ADMIN_EMAILS`) can
    access the decorated view function. Unauthorized access attempts
    are logged and a 403 Forbidden HTTP error is raised.

    Args:
        view_func (Callable): The view function to be decorated.

    Returns:
        Callable: A wrapped function that enforces administrator-only access.

    Raises:
        HTTPException: Raises a 403 Forbidden error if the user's email is not
        listed as an administrator.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        allowed = current_app.config.get("ADMIN_EMAILS", [])
        if current_user.email not in allowed:
            email_masked = current_user.email[:3] + "***" if current_user.email else "<unknown>"
            auth_logger.warning(
                f"Attempted access to admin function with email {email_masked} (IP: {request.remote_addr})"
            )
            abort(403, description="Your email address is not registered as an administrator.")

        return view_func(*args, **kwargs)
    return wrapper