# cards.py
# Standard Library
import hashlib
import os
import logging
import io
import base64
from datetime import datetime, date

# Third-Party
from cryptography.fernet import Fernet
from flask import (
    render_template,
    session,
    Blueprint,
    request,
    redirect,
    url_for,
    flash,
    current_app
)
from flask_login import current_user
import qrcode
import sqlite3

# Local
from core.extensions import fernet
from core.token_manager import generate_token, decode_token
from utils.email_utils import send_membership_email, is_valid_email
from .helpers import build_user_data_from_session
from .photo import register_photo_routes

cards_bp = Blueprint('cards', __name__, template_folder='templates')

register_photo_routes(cards_bp)

main_logger = logging.getLogger("main_logger")

@cards_bp.route("/card")
def direct_member_card():
    """
    Route to direct the user to their member card.

    This function checks the user's session data to ensure they are logged in. If the user
    is not logged in, it displays a warning, flashes a message, and redirects them to the
    login page. If the user is logged in, it generates a token for their member card and
    redirects them to the member card view.

    Raises:
        Redirect: Redirects to the login page if the user is not logged in.

    Returns:
        Redirect: Redirects to the member card page with a generated token as a query
        parameter.
    """
    user_data = build_user_data_from_session()
    if not user_data:
        flash("Du musst dich zuerst anmelden.")
        main_logger.warning(
            f"No userinfo in session – likely not logged in (IP: {request.remote_addr})"
        )
        return redirect(url_for("auth.login_page", next=request.url))

    token = generate_token(user_data)
    return redirect(url_for("cards.member_card", token=token))

# ---------------------------------------------------------------------------
# Route: /qr_card – QR‑Code‑Ansicht
# ---------------------------------------------------------------------------

@cards_bp.route("/qr_card")
def qr_card():
    """
    Generates and serves a QR code for a user's member card.

    This view function retrieves user data from the session and verifies if the user
    is logged in. If valid user data is retrieved, a unique token is generated for
    the user, and a QR code is created containing a verification URL. The generated
    QR code, along with other user details, is then rendered and returned in the
    template. Logs are generated at several steps during execution.

    Raises:
        Redirect: Redirects to the login page if the user is not logged in.

    Returns:
        Response: Renders the 'qr_card.html' template with the generated QR code data,
                  verification URL, user details, and current date.
    """
    user_data = build_user_data_from_session()
    if not user_data:
        flash("Du musst dich zuerst anmelden.")
        main_logger.warning(
            f"No userinfo in session – likely not logged in (IP: {request.remote_addr})"
        )
        return redirect(url_for("auth.login_page", next=request.url))

    token = generate_token(user_data)
    verification_url = url_for("cards.member_card", token=token, _external=True)

    img = qrcode.make(verification_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_code_data = base64.b64encode(buf.getvalue()).decode()

    main_logger.info(
        f"QR card displayed for: {user_data['user_id'][:3]}*** (IP: {request.remote_addr})"
    )

    return render_template(
        "qr_card.html",
        token=token,
        verification_url=verification_url,
        qr_code_data=qr_code_data,
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        current_date=date.today().strftime("%d.%m.%Y"),
    )


@cards_bp.route('/verify/<token>')
def member_card(token):
    """
    Displays a member card for a given verification token.

    Verifies and decodes the token, retrieves user information, and checks for
    an existing photo. Renders the appropriate template with user details and
    photo status.

    :param token: Verification token containing encrypted user data
    :type token: str
    :return: Rendered member card template or error page
    :rtype: tuple
    """
    user_data = decode_token(token)

    if not user_data:
        main_logger.warning(f"Expired/invalid membership card token, Viewer IP: {request.remote_addr}")
        return render_template("expired.html"), 403

    viewer_id = (
        session.get("oauth_userinfo", {}).get("email")
        or session.get("email_userinfo", {}).get("email")
    )

    # Check photo ID and existence
    email = user_data["user_id"]
    role = user_data.get("role", "")
    join_year = user_data.get("join_year")
    photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
    photo_path = os.path.join(current_app.config["PHOTO_UPLOAD_FOLDER"], f"{photo_id}.enc")
    photo_exists = os.path.exists(photo_path)

    main_logger.info(
        f"Membership card displayed for User: {user_data['user_id'][:3]}*** by Viewer: {viewer_id or '-'} IP: {request.remote_addr}")

    return render_template(
        "member_card.html",
        user_id=user_data['user_id'],
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        role=role,
        join_year=join_year,
        token=token,
        current_year=datetime.utcnow().year,
        viewer_id=viewer_id,
        photo_id=photo_id,
        photo_exists=photo_exists
    )

@cards_bp.route('/send_email', methods=['POST'])
def send_email():
    """
    Handles email sending of membership information.

    Validates the recipient email and token, then sends the membership
    details via email. Logs the operation and provides user feedback
    through flash messages.

    :return: Redirect to previous page or QR card page
    :rtype: werkzeug.wrappers.Response
    :raises RuntimeError: If email sending fails
    """
    recipient = request.form.get('recipient')
    token = request.form.get('token')

    # Validations
    if not recipient or not token:
        flash('Error: All fields must be filled.', 'error')
        return redirect(url_for('cards.qr_card'))

    if not is_valid_email(recipient):
        flash('Error: Invalid email address.', 'error')
        main_logger.error(f"Invalid email address {recipient} from IP: {request.remote_addr}")
        return redirect(url_for('cards.qr_card'))

    # Validate token and extract user data
    user_data = decode_token(token)
    if not user_data:
        flash('Error: The membership card has expired or is invalid.', 'error')
        main_logger.warning(f"Membership card token invalid/expired when sending to {recipient[:3]}*** from IP: {request.remote_addr}")
        return redirect(url_for('cards.qr_card'))

    # Send email
    success = send_membership_email(recipient, user_data)

    if success:
        main_logger.info(
            f"Membership card sent by email to: {recipient[:3]}*** for User: {user_data.get('user_id', '-')[:3]}*** (IP: {request.remote_addr})")
        flash('The email has been sent successfully. You will be redirected shortly...', 'success')
    else:
        main_logger.error(
            f"Error sending email to: {recipient[:3]}*** for User: {user_data.get('user_id', '-')[:3]}*** (IP: {request.remote_addr})")
        flash('An error occurred while sending the email.', 'error')

    return redirect(request.referrer or url_for('cards.qr_card'))