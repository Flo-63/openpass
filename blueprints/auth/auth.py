"""
===============================================================================
Project   : openpass
Module    : blueprints/auth/auth.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides authentication-related functionality for the openpass application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


# Standard Library
import logging

# Third-Party
from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_login import login_user, logout_user, current_user
from flask_wtf.csrf import generate_csrf

# Local
from core.extensions import SimpleUser
from .email import register_email_routes
from .oauth import register_oauth_routes

# Module Constants and Configurations
auth_logger = logging.getLogger("auth_logger")
auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Route Registrations
register_oauth_routes(auth_bp)
register_email_routes(auth_bp)

@auth_bp.route("/login", methods=["GET"])
def login_page():
    """
    Handles the login page route. This route is designed to securely handle existing
    user sessions by logging out any currently logged-in user and clearing the
    session entirely, ensuring a clean state before rendering the login page.

    Returns:
        A rendered HTML template for the login page.
    """
    logout_user()      # sicher, auch wenn niemand eingeloggt ist
    session.clear()    # alles raus, auch Custom-Keys
    return render_template("login.html")

@auth_bp.route('/logout')
def logout():
    """
    Logs out the current user, clears the session, and redirects to the login page.

    This function handles user logout by invalidating the current session, clearing
    any session data, and logging the logout details including the user ID and
    requesting IP address. After the logout process is complete, it redirects
    the user to the login page.

    Returns:
        Response: A redirect response to the login page.
    """
    user_id = getattr(current_user, 'id', 'unknown')
    logout_user()
    session.clear()
    auth_logger.info(f"Logout completed for user: {user_id} from IP: {request.remote_addr}")
    return redirect(url_for('auth.login_page'))

@auth_bp.route("/dev_login", methods=["GET", "POST"])
def dev_login():
    """
    Handles developer login functionality for debugging purposes. This route is only accessible
    when the application is running in debug mode. It provides a simple HTML form for login and
    generates a session for a mock user upon form submission.

    The functionality includes:
    - Verifying that the application is in debug mode before proceeding.
    - Accepting an email as input via form submission.
    - Generating a developer user session and logging the action.

    Raises warnings and restricts access if invoked outside of debug mode. Also facilitates CSRF
    protection for form submission.

    Returns:
        str: HTML form for GET request.
        flask.Response: Redirect to specific user area or error/response for POST request.
    """
    if not current_app.debug:
        auth_logger.warning(f"Unauthorized access to /dev_login from IP: {request.remote_addr}")
        return "Not allowed", 403

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            return "Email required", 400

        user = SimpleUser(email, "Dev", "User", email)
        login_user(user)

        session["email_userinfo"] = {
            "email": email,
            "first_name": "Dev",
            "last_name": "User"
        }
        auth_logger.info(f"Dev login completed for: {email[:4]}*** from IP: {request.remote_addr}")
        return redirect(url_for("cards.direct_member_card"))

    csrf_token = generate_csrf()
    return f'''
    <form method="post">
        <input type="hidden" name="csrf_token" value="{csrf_token}">
        <label>Email:</label>
        <input type="email" name="email" required>
        <button type="submit">Login</button>
    </form>
    '''