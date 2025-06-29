# email.py
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

def register_email_routes(bp):
    """
    Registers email authentication routes.

    Sets up routes for email-based login, verification, and rate limiting.
    Handles token generation, database queries, and session management.

    :param bp: Blueprint for route registration
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
        DB_PATH = os.path.join("instance", current_app.config["MEMBER_DB"])

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

        auth_logger.info(f"Login link sent to: {email[:3]}*** (hash: {email_hash}) from IP: {request.remote_addr}")
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
        email = verify_email_token(token)

        if not email:
            auth_logger.warning(f"Login attempt with invalid or expired token from IP: {request.remote_addr}")
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
                f"Login attempt for non-existent email (hash: {email_hash}) from IP: {request.remote_addr}")
            flash("Email address is no longer valid.")
            return redirect(url_for("auth.login_page"))

        first_name = fernet.decrypt(row[0].encode()).decode()
        last_name = fernet.decrypt(row[1].encode()).decode()

        user = SimpleUser(email, first_name, last_name)
        login_user(user)

        session.pop("next_url", None)
        session.pop("oauth_state", None)
        session["email_userinfo"] = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }

        auth_logger.info(
            f"Email login successful for: {email[:3]}*** (hash: {email_hash}) from IP: {request.remote_addr}")

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