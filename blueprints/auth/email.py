"""
===============================================================================
Project   : openpass
Module    : blueprints/auth/email.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides email-based authentication functionality for the openpass application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


# Standard Library
import hashlib
import logging
import os
import sqlite3

# Third-Party
from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_limiter.util import get_remote_address
from flask_login import login_user

# Local
from core.extensions import (
    fernet,
    limiter,
    SimpleUser
)
from core.token_manager import (
    generate_email_token,
    verify_email_token
)
from utils.email_utils import send_login_email

auth_logger = logging.getLogger("auth_logger")

# Lifetime of an email login token, in seconds. Kept in sync with the max_age used by
# verify_email_token so that the replay marker outlives the token itself.
EMAIL_TOKEN_MAX_AGE = 900


def _mask_hash(email_hash: str) -> str:
    """
    Shortens an email hash for logging.

    The full SHA-256 of an address identifies a member exactly: email addresses carry
    little entropy, so anyone holding the log and a list of candidate addresses can
    reverse it by trial. Logging the full digest next to a `abc***` masked address
    therefore undoes the masking. A short prefix is still enough to correlate entries
    within a log file.

    Args:
        email_hash (str): Full hex digest.

    Returns:
        str: The first ten characters, marked as truncated.
    """
    return f"{email_hash[:10]}…"


def _consume_login_token(token: str) -> bool:
    """
    Marks an email login token as used and reports whether it was still unused.

    Signed tokens are inherently replayable: anyone who obtains the link (from a
    forwarded mail, a mail server log or browser history) can redeem it repeatedly
    until it expires. A single-use marker in the shared Redis store closes that window
    and makes the promise in the login mail ("kann nur einmal verwendet werden") true.

    When the marker cannot be recorded because Redis is unreachable, the behaviour is
    selected by `EMAIL_LOGIN_REPLAY`: `warn` (the default) allows the login and logs
    loudly, `require` refuses it. The default stays permissive because a Redis outage
    would otherwise lock every member out of the application.

    Args:
        token (str): The raw token from the login link.

    Returns:
        bool: True if the token may be redeemed.
    """
    marker = f"openpass:email-login-used:{hashlib.sha256(token.encode()).hexdigest()}"
    try:
        from redis import Redis

        client = Redis.from_url(current_app.config["RATE_LIMIT_STORAGE"])
        # SET NX is atomic: only the first redemption gets the key.
        return bool(client.set(marker, b"1", nx=True, ex=EMAIL_TOKEN_MAX_AGE))
    except Exception as err:
        mode = current_app.config.get("EMAIL_LOGIN_REPLAY", "warn")
        if mode == "require":
            auth_logger.error(
                f"Could not record single-use login token and EMAIL_LOGIN_REPLAY=require "
                f"– refusing the login: {err}"
            )
            return False
        auth_logger.error(
            f"Could not record single-use login token, replay protection SKIPPED for "
            f"this login: {err}. Login links stay replayable for up to "
            f"{EMAIL_TOKEN_MAX_AGE}s while Redis is unavailable. Set "
            f"EMAIL_LOGIN_REPLAY=require to refuse logins instead."
        )
        return True

def register_email_routes(bp):
    """
    Registers email-related routes to a Flask Blueprint.

    Defines routes to handle email login functionality, including request handling,
    verification, rate limiting, and related confirmations. Provides endpoints
    to manage email login flow securely and efficiently, incorporating rate-limiting
    policies and user authentication mechanisms.

    :param bp: The Flask Blueprint to which the email-related routes will be added.
    :type bp: flask.Blueprint
    """
    @bp.route("/request_email_login", methods=["POST"])
    @limiter.limit(lambda: current_app.config.get("EMAIL_LOGIN_RATE_LIMIT", "1 per hour"),
                   key_func=get_remote_address,
                   per_method=True,
                   methods=["POST"])
    def request_email_login():
        """
        Processes email login requests.

        Validates email, generates login token, and sends secure login link.
        Retrieves and decrypts user data from database.

        :return: Redirect to confirmation page
        :rtype: werkzeug.wrappers.Response
        :raises: BadRequest, sqlite3.Error, InvalidToken
        """
        email = request.form.get("email", "").strip().lower()
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        DB_PATH = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT first_name_enc, last_name_enc FROM members WHERE email_hash = ?", (email_hash,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return redirect(url_for("auth.email_sent"))

        first_name = fernet.decrypt(row[0].encode()).decode()
        last_name = fernet.decrypt(row[1].encode()).decode()

        token = generate_email_token(email)
        link = url_for("auth.email_login", token=token, _external=True, _scheme="https")

        auth_logger.info(f"Login link sent to: {email[:3]}*** (hash: {_mask_hash(email_hash)}) from IP: {request.remote_addr}")
        success = send_login_email(email, first_name, last_name, link)
        if not success:
            auth_logger.error(f"Login-Mailversand an {email[:3]}*** fehlgeschlagen.")

        return redirect(url_for("auth.email_sent"))

    @bp.route("/email_login")
    def email_login():
        """
        Processes email login verification.

        Verifies token, authenticates user, and sets up session.
        Handles invalid tokens and outdated email references.

        :return: Redirect to appropriate page
        :rtype: werkzeug.wrappers.Response
        """
        token = request.args.get("token")
        email = verify_email_token(token, max_age=EMAIL_TOKEN_MAX_AGE)

        if not email:
            auth_logger.warning(f"Login attempt with invalid or expired token from IP: {request.remote_addr}")
            flash("The link is invalid or has expired.")
            return redirect(url_for("auth.login_page"))

        if not _consume_login_token(token):
            auth_logger.warning(
                f"Replayed email login token for {email[:3]}*** from IP: {request.remote_addr}"
            )
            flash("The link is invalid or has expired.")
            return redirect(url_for("auth.login_page"))

        email_hash = hashlib.sha256(email.encode()).hexdigest()
        DB_PATH = os.path.join("instance", current_app.config["MEMBER_DB"])

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT first_name_enc, last_name_enc FROM members WHERE email_hash = ?", (email_hash,))
        row = cur.fetchone()
        conn.close()

        if not row:
            auth_logger.warning(
                f"Login attempt for non-existent email (hash: {_mask_hash(email_hash)}) from IP: {request.remote_addr}")
            flash("Email address is no longer valid.")
            return redirect(url_for("auth.login_page"))

        first_name = fernet.decrypt(row[0].encode()).decode()
        last_name = fernet.decrypt(row[1].encode()).decode()

        user = SimpleUser(email, first_name, last_name, email=email)
        session.permanent = True
        login_user(user)

        session.pop("next_url", None)
        session.pop("oauth_state", None)
        session["email_userinfo"] = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }

        auth_logger.info(
            f"Email login successful for: {email[:3]}*** (hash: {_mask_hash(email_hash)}) from IP: {request.remote_addr}")

        return redirect(url_for("cards.direct_member_card"))

    @bp.route("/email_sent")
    def email_sent():
        """
        Shows email sent confirmation page.

        :return: Rendered confirmation template
        :rtype: str
        """
        return render_template("email_sent.html")

    @bp.route("/can_request_email_login")
    @limiter.limit(lambda: current_app.config.get("STATUS_RATE_LIMIT", "60 per hour"),
                   key_func=get_remote_address)
    def can_request_email_login():
        """
        Checks if email login requests are allowed.

        Verifies rate limits based on IP address.

        :return: JSON response with allowance status
        :rtype: flask.Response
        """
        ip = get_remote_address()
        endpoint = "auth.request_email_login"
        key = f"rate-limit/{ip}/{endpoint}"
        expiry = limiter.storage.get_expiry(key)

        if expiry is None or expiry <= 0:
            return jsonify({"allowed": True})
        else:
            return jsonify({"allowed": False, "retry_after": expiry})

    @bp.route("/email_check_limit", methods=["POST"])
    def email_check_limit():
        """
        Manages rate limiting for email checks.

        Tracks request frequency from IP addresses.

        :return: Response indicating rate limit status
        :rtype: flask.Response
        """
        import time
        from redis import Redis

        r = Redis.from_url(current_app.config["RATE_LIMIT_STORAGE"])

        ip = get_remote_address()
        key = f"rate-limit/{ip}/auth.request_email_login"
        redis_key = f"LIMITER:fixed-window:{key}:{int(time.time() // 3600)}"

        ttl = r.ttl(redis_key)

        if ttl > 0:
            auth_logger.warning(f"Rate limit active for IP: {ip}, TTL: {ttl} sec., Redis key: {redis_key}")
            return "", 429
        return jsonify({"allowed": True})

    @bp.route("/rate_limited", methods=["GET"])
    def rate_limited_page():
        """
        Shows rate limit exceeded page.

        :return: Rendered rate limit template
        :rtype: str
        """
        return render_template("rate_limited.html")