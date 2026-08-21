import pytest


class _FakeOAuthClient:
    """Minimal stand-in for the Authlib client used in the callback."""

    def __init__(self, userinfo):
        self._userinfo = userinfo

    def authorize_access_token(self):
        return {"access_token": "dummy"}

    def userinfo(self):
        return self._userinfo


class TestOAuthEmailVerification:
    """
    Covers how the callback treats an email address the provider does not vouch for.

    Rocket.Chat reports email_verified=false whenever its own email verification is
    switched off. Rejecting that outright locks out every member, so the behaviour is
    configurable — and each mode is pinned here.
    """

    def _callback(self, app, mode, userinfo):
        app.config["OAUTH_EMAIL_VERIFICATION"] = mode
        app.oauth_client = _FakeOAuthClient(userinfo)
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["oauth_state"] = "teststate"
        return client.get("/authorized?state=teststate")

    UNVERIFIED = {
        "preferred_username": "flo",
        "email": "flo@example.org",
        "email_verified": False,
        "given_name": "Flo",
    }

    def test_warn_mode_allows_login(self, app):
        """Default mode must not break the login flow for an unverified address."""
        response = self._callback(app, "warn", self.UNVERIFIED)
        assert response.status_code == 302, response.data[:200]

    def test_off_mode_allows_login(self, app):
        response = self._callback(app, "off", self.UNVERIFIED)
        assert response.status_code == 302, response.data[:200]

    def test_require_mode_rejects_unverified(self, app):
        response = self._callback(app, "require", self.UNVERIFIED)
        assert response.status_code == 400

    def test_require_mode_accepts_verified(self, app):
        verified = dict(self.UNVERIFIED, email_verified=True)
        response = self._callback(app, "require", verified)
        assert response.status_code == 302, response.data[:200]

    def test_default_mode_is_warn(self, app):
        """A deploy that sets nothing must keep logging in."""
        assert app.config["OAUTH_EMAIL_VERIFICATION"] == "warn"


class TestOAuthRoutes:
    """
    Class for testing OAuth routes.

    This class contains test cases to ensure the proper functioning of OAuth login
    and callback endpoints. Each test examines a specific scenario to validate the
    behavior and responses of the OAuth-related workflows. This includes testing
    the start of the OAuth login process, handling of invalid states in the
    callback, and scenarios where the token is missing in the process.

    Attributes:
        None
    """
    def test_oauth_login_start(self, client):
        """
        Tests the initiation of the OAuth login process.

        This function tests if the OAuth login flow starts correctly by sending
        a GET request to the designated OAuth login endpoint. It verifies the
        response status code and checks the session for the presence of the
        OAuth state.

        Parameters:
        client
            Flask test client used to simulate HTTP requests.

        Returns:
        None
        """
        response = client.get('/login/oauth')
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert 'oauth_state' in sess

    def test_oauth_callback_invalid_state(self, client):
        """
        Tests the handling of an OAuth callback with an invalid state.

        This function simulates an HTTP GET request to the OAuth callback endpoint
        with an invalid state parameter and asserts that the server returns the
        expected HTTP 400 Bad Request status code.

        Args:
            client: A test client instance used to simulate HTTP requests.

        Returns:
            None
        """
        response = client.get('/authorized?state=invalid')
        assert response.status_code == 400

    def test_oauth_callback_missing_token(self, client):
        """
        Tests the scenario where the OAuth callback is invoked without a token and
        ensures that the response status code is 400, as expected.

        Args:
            client: The test client used to simulate requests in the application.

        Returns:
            None
        """
        with client.session_transaction() as session:
            session['oauth_state'] = 'test_state'
        response = client.get('/authorized?state=test_state')
        assert response.status_code == 400