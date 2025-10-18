"""
===============================================================================
Project   : openpass
Module    : blueprints/cards/cards.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides routes for managing member cards.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


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
    Handles the route to provide a direct link for accessing the member card.
    This function checks the current session for logged-in user data and ensures
    authentication. If authenticated, it generates a token and redirects the user
    to their member card. Otherwise, it redirects unauthorized users to the login
    page.

    Raises:
        None

    Parameters:
        None

    Returns:
        Response: Redirects to either the member card with a valid token or the
        login page if the user is not authenticated.
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
    Generates and renders a personal QR code card for the authenticated user.

    This function creates a QR code that encodes a unique verification URL for the user, who
    must be logged in to access this feature. If the user is not logged in, they will be redirected
    to the login page. The QR code, along with user-specific data, is rendered and presented in
    an HTML template.

    Returns:
        str: Rendered HTML response containing the QR code and user details.

    Raises:
        Redirect: Redirects to the login page if the user is not authenticated.
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
    Handles the display of a member card based on a provided token. Validates the token and fetches
    the associated user data to render the member card on the frontend.

    Parameters:
    token : str
        The token used to identify and validate the membership card.

    Raises:
    403
        Returned if the provided token is expired or invalid.

    Returns:
    tuple
        A rendered HTML page and an HTTP status code. Returns the "expired.html" template and a
        403 status code if the provided token is expired or invalid. Otherwise, returns the
        "member_card.html" template with the user data used for rendering and a 200 status code.
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
    Handles sending emails with membership cards based on user inputs and validations.

    The function processes incoming POST requests to send a membership card via email
    to the specified recipient. It validates the incoming data, ensures the provided
    email is correct and the token is valid, and, if successful, sends an email with
    the necessary information. Error handling and logging are incorporated to
    properly manage and document potential issues that arise during the process.

    Raises:
        None (All errors are handled within the function scope using redirections and message flashes)

    Parameters:
        None (All parameters are derived from the POST request's data)

    Returns:
        Werkzeug Response: Redirect response to the caller page or another specified endpoint
    """
    recipient = request.form.get('recipient')
    token = request.form.get('token')

    # Validations
    if not recipient or not token:
        flash('Fehler: Bitte alle Felder ausfüllen!', 'error')
        return redirect(url_for('cards.qr_card'))

    if not is_valid_email(recipient):
        flash('Error: Ungültige email Adresse.', 'error')
        main_logger.error(f"Invalid email address {recipient} from IP: {request.remote_addr}")
        return redirect(url_for('cards.qr_card'))

    # Validate token and extract user data
    user_data = decode_token(token)
    if not user_data:
        flash('Fehler: Der Ausweis ist abgelaufen oder ungültig.', 'error')
        main_logger.warning(f"Membership card token invalid/expired when sending to {recipient[:3]}*** from IP: {request.remote_addr}")
        return redirect(url_for('cards.qr_card'))

    # Send email
    success = send_membership_email(recipient, user_data)

    if success:
        main_logger.info(
            f"Membership card sent by email to: {recipient[:3]}*** for User: {user_data.get('user_id', '-')[:3]}*** (IP: {request.remote_addr})")
        flash('Die email wurde erfolgreich versendet. Du wirst gleich weitergeleitet...', 'success')
    else:
        main_logger.error(
            f"Error sending email to: {recipient[:3]}*** for User: {user_data.get('user_id', '-')[:3]}*** (IP: {request.remote_addr})")
        flash('Beim Versenden der email ist ein Fehler aufgetreten', 'error')

    return redirect(request.referrer or url_for('cards.qr_card'))