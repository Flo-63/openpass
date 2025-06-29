# auth.py
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
    Renders the login page.

    Handles GET requests to display the authentication interface.
    Returns the login page template for user authentication.

    :return: Rendered login page
    :rtype: str
    :raises TemplateNotFound: If login template is missing
    """
    logout_user()      # sicher, auch wenn niemand eingeloggt ist
    session.clear()    # alles raus, auch Custom-Keys
    return render_template("login.html")

@auth_bp.route('/logout')
def logout():
    """
    Processes user logout.

    Terminates user session, clears session data, and logs the action.
    Records the logout event with user ID (if available) and IP address.

    :return: Redirect to login page
    :rtype: werkzeug.wrappers.Response
    """
    user_id = getattr(current_user, 'id', 'unknown')
    logout_user()
    session.clear()
    auth_logger.info(f"Logout completed for user: {user_id} from IP: {request.remote_addr}")
    return redirect(url_for('auth.login_page'))

@auth_bp.route("/dev_login", methods=["GET", "POST"])
def dev_login():
    """
    Handles development environment login.

    Provides a simplified login mechanism for development purposes.
    Only accessible when application is in debug mode.
    GET: Shows login form
    POST: Processes login attempt

    :return: Login form or redirect on success
    :rtype: Union[str, werkzeug.wrappers.Response]
    :raises HTTPException: 403 if not in debug mode, 400 if email missing
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