from flask_login import current_user

class TestAuth:
    """
    Contains test cases for authentication-related functionality.

    This class provides a collection of unit test cases to validate the behavior of
    various authentication-related functionalities in the application, such as
    logging in, logging out, and accessing developer-specific endpoints. These
    tests ensure consistency and correctness in authentication workflows.
    """
    def test_login_page(self, client):
        """
        Tests the login page for proper response and content.

        Ensures that the login page returns a 200 status code and contains the
        expected branding title and content.

        Args:
            self: Represents the instance of the test case.
            client: A testing client used to send HTTP requests.

        Returns:
            None
        """
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data
        # Branding‑Titel wurde von „RCB Ausweis“ auf „OpenPass“ geändert
        assert b'OpenPass' in response.data

    def test_logout(self, client):
        """
        Tests the logging out functionality ensuring that an authenticated user
        is properly logged out and redirected to the login page.

        Parameters:
            self: The instance of the test case class.
            client: A test client instance used to simulate requests to the application.

        Returns:
            None
        """
        with client:
            client.post('/dev_login', data={'email': 'test@example.com'})
            response = client.get('/logout')
            assert response.status_code == 302
            assert 'login' in response.location
            assert not current_user.is_authenticated

    def test_dev_login_disabled_in_production(self, client, app):
        """
        Test to ensure that the developer login feature is disabled in production mode.
        This test verifies that when the application is not in debug mode, accessing the
        developer login URL results in a forbidden HTTP status code.

        Args:
            client: A test client for simulating requests to the application.
            app: The application instance being tested.

        Raises:
            AssertionError: If the response status code is not 403.
        """
        app.debug = False
        response = client.get('/dev_login')
        assert response.status_code == 403

    def test_dev_login_enabled_in_debug(self, client, app):
        """
        Tests if the developer login endpoint is enabled when the application is in
        debug mode. The application debug mode is set to `True`, and then the test
        verifies that a GET request to the `/dev_login` endpoint returns a response
        with a status code of 200.

        Parameters:
        client : flask.testing.FlaskClient
            A test client used to simulate HTTP requests to the application.
        app : flask.Flask
            The Flask application being tested.

        Raises:
        AssertionError
            If the status code of the `/dev_login` endpoint is not 200 when
            the application debug mode is enabled.
        """
        app.debug = True
        response = client.get('/dev_login')
        assert response.status_code == 200

    def test_dev_login_post(self, client, app):
        """
        Tests the developer login functionality via POST request.

        This test method verifies that a POST request to the '/dev_login' endpoint
        with a valid email results in a redirection to the '/card' endpoint.

        Args:
            client: A test client instance for making HTTP requests.
            app: The Flask application context used for the test.

        Raises:
            AssertionError: If the response status code is not 302 or
            if the redirection location does not include '/card'.
        """
        app.debug = True
        response = client.post('/dev_login', data={'email': 'test@example.com'})
        assert response.status_code == 302
        assert '/card' in response.location