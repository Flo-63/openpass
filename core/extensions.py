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
    Representation of a simple user with optional personal and role information.

    This class is a simplified user object that can be used for systems requiring
    basic user management features. It includes user identification and optional
    fields such as first name, last name, email, and role. It also inherits from
    UserMixin to easily integrate with systems or frameworks that recognize this
    mixin.

    :ivar id: Unique identifier for the user.
    :type id: Any
    :ivar first_name: Optional first name of the user.
    :type first_name: Optional[str]
    :ivar last_name: Optional last name of the user.
    :type last_name: Optional[str]
    :ivar email: Optional email address of the user.
    :type email: Optional[str]
    :ivar role: Optional role assigned to the user.
    :type role: Optional[Any]
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
    Loads and retrieves user information based on the provided user ID or session data.
    The function checks the session data for user information, such as email, retrieves
    role information from a database if an email is available, and constructs a `SimpleUser`
    object with the gathered information.

    The function is registered as a user loader for a Flask-Login instance.

    :param user_id: The ID of the user to be loaded.
    :type user_id: str
    :returns: A `SimpleUser` object containing user information such as username, first name,
        last name, email, and role. Returns a `SimpleUser` with default or derived values
        if no session or database information is available.
    :rtype: SimpleUser
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
    A decorator function to restrict access to certain views to only users whose
    email addresses are listed as administrators in the application configuration.
    If the email of the current user does not match any email in the allowed admin
    emails, access is denied with an HTTP 403 error.

    :param view_func: The view function to be wrapped by the decorator.
    :type view_func: callable
    :return: The wrapped function with added access control for admin users.
    :rtype: callable

    Example usage:
    @admin_required
    def admin_dashboard():
        return render_template('admin/dashboard.html')
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