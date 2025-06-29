# oauth.py
# Standard Library
import os
import logging

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

        next_url = request.args.get("next", url_for("cards.direct_member_card"))
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

            session["oauth_userinfo"] = userinfo

        except Exception as e:
            auth_logger.exception(f"Exception in authorize callback, IP: {request.remote_addr}")
            return "Authorization failed.", 400

        user_id = userinfo.get("preferred_username") or userinfo.get("username") or userinfo.get("sub")
        if not user_id:
            auth_logger.error(f"User ID missing in OAuth userinfo! Data: {repr(userinfo)}, IP: {request.remote_addr}")
            return "Authorization failed.", 400

        first_name = userinfo.get("given_name") or userinfo.get("name")
        last_name = userinfo.get("family_name")

        user = SimpleUser(user_id, first_name, last_name)
        login_user(user)

        auth_logger.info(f"OAuth login successful for user: {str(user_id)[:3]}***, IP: {request.remote_addr}")

        return redirect(next_url or url_for("cards.direct_member_card"))