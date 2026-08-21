"""
===============================================================================
Project   : openpass
Module    : blueprints/auth/oauth.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module will provide  OAuth authentication routes for the application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


# Standard Library
import os
import logging
from urllib.parse import urlparse

# Third-Party
from flask import (
    session,
    current_app,
    request,
    url_for,
    redirect
)
from flask_login import current_user, logout_user, login_user

# Local
from core.extensions import SimpleUser


auth_logger = logging.getLogger("auth_logger")


def _safe_next_url(candidate, fallback):
    """
    Returns `candidate` only if it is a local path, otherwise `fallback`.

    The `next` parameter is attacker-controlled and is followed after a successful
    login, so an absolute URL would turn the login flow into an open redirect that
    lends the application's domain to a phishing page.

    Args:
        candidate: The requested redirect target.
        fallback: Target to use when the candidate is missing or not local.

    Returns:
        str: A safe redirect target.
    """
    if not candidate:
        return fallback

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith("/") or candidate.startswith("//"):
        auth_logger.warning(f"Rejected non-local next URL: {candidate!r} (IP: {request.remote_addr})")
        return fallback

    return candidate

def register_oauth_routes(bp):
    """
    Registers OAuth authentication routes.

    Sets up two main routes:
    1. /login/oauth: Starts OAuth login flow
    2. /authorized: Handles OAuth callback

    :param bp: Blueprint for route registration
    :type bp: flask.Blueprint
    :return: None
    """
    @bp.route("/login/oauth")
    def login_oauth():
        """
        Initiates OAuth login sequence.

        Logs out current user if authenticated, generates session state,
        and redirects to OAuth provider.

        :return: Redirect to OAuth provider
        :rtype: flask.Response
        :raises KeyError: On missing session values
        """
        if current_user.is_authenticated:
            auth_logger.info(
                f"User {getattr(current_user, 'id', '?')} logged out before OAuth login (IP: {request.remote_addr})")
            logout_user()
            session.clear()

        oauth_client = current_app.oauth_client
        state = os.urandom(16).hex()
        session['oauth_state'] = state

        next_url = _safe_next_url(
            request.args.get("next"), url_for("cards.direct_member_card")
        )
        session["next_url"] = next_url

        auth_logger.info(f"OAuth login started, Session-State: {state}, IP: {request.remote_addr}, next: {next_url}")

        redirect_uri = url_for('auth.authorized', _external=True, _scheme='https')
        return oauth_client.authorize_redirect(redirect_uri, state=state)

    @bp.route("/authorized")
    def authorized():
        """
        Processes OAuth callback.

        Validates state parameter, exchanges code for token,
        retrieves user info and completes login.

        :return: Redirect to next URL or error page
        :rtype: flask.Response
        :raises Exception: On authorization failure
        """
        state_from_request = request.args.get("state")
        expected_state = session.pop("oauth_state", None)
        next_url = session.pop("next_url", None)

        if state_from_request != expected_state:
            auth_logger.warning(
                f"OAuth state mismatch! Expected: {expected_state}, received: {state_from_request}, IP: {request.remote_addr}")
            return "Authorization failed.", 400

        try:
            token = current_app.oauth_client.authorize_access_token()
            if not token:
                auth_logger.error(f"OAuth token missing or invalid, IP: {request.remote_addr}")
                return "Authorization failed.", 400

            userinfo = current_app.oauth_client.userinfo()
            if not userinfo:
                auth_logger.error(f"OAuth userinfo missing/empty, IP: {request.remote_addr}")
                return "Authorization failed.", 400

        except Exception as e:
            auth_logger.exception(f"Exception in authorize callback, IP: {request.remote_addr}")
            return "Authorization failed.", 400

        user_id = userinfo.get("preferred_username") or userinfo.get("username") or userinfo.get("sub")
        if not user_id:
            auth_logger.error(f"User ID missing in OAuth userinfo! Data: {repr(userinfo)}, IP: {request.remote_addr}")
            return "Authorization failed.", 400

        # The email address is the identity anchor for role lookup, photo access and
        # admin authorisation. Whether an unverified address is fatal depends on the
        # identity provider: Rocket.Chat reports email_verified=false whenever its own
        # email verification is switched off, so rejecting outright would lock out
        # every member. OAUTH_EMAIL_VERIFICATION selects the behaviour.
        email = (userinfo.get("email") or "").strip().lower()
        if email and userinfo.get("email_verified") is not True:
            mode = current_app.config.get("OAUTH_EMAIL_VERIFICATION", "warn")
            if mode == "require":
                auth_logger.warning(
                    f"Rejected OAuth login: email not verified by provider for "
                    f"{email[:3]}*** (claim: {userinfo.get('email_verified')!r}), "
                    f"IP: {request.remote_addr}"
                )
                return "Authorization failed.", 400
            if mode == "warn":
                auth_logger.warning(
                    f"OAuth login with an email the provider does not vouch for: "
                    f"{email[:3]}*** (claim: {userinfo.get('email_verified')!r}). "
                    f"Anyone who can set this address at the identity provider can "
                    f"assume this member's role and photo. Enable email verification "
                    f"at the provider, then set OAUTH_EMAIL_VERIFICATION=require."
                )

        # Only persist the profile once it has passed validation.
        session["oauth_userinfo"] = userinfo

        first_name = userinfo.get("given_name") or userinfo.get("name")
        last_name = userinfo.get("family_name")

        user = SimpleUser(user_id, first_name, last_name, email=email or None)
        session.permanent = True
        login_user(user)

        auth_logger.info(f"OAuth login successful for user: {str(user_id)[:3]}***, IP: {request.remote_addr}")

        return redirect(_safe_next_url(next_url, url_for("cards.direct_member_card")))