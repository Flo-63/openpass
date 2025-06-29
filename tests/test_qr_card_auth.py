# tests/test_qr_card_auth.py
import pytest
from unittest.mock import patch
from flask import url_for
from core.token_manager import generate_token
from cryptography.fernet import Fernet


class TestCards:
    """
    A class for testing various card-related functionalities in a web application.

    This class contains test cases to validate the behavior of QR card access, member card display,
    token generation and validation, and email processing within the application's context.
    It ensures proper functionality and handles edge cases, such as expired tokens, missing tokens,
    and invalid tokens. The tests utilize client-server interactions and simulate differing
    scenarios for authentication and functionality validation.
    """
    def test_qr_card_requires_login(self, client):
        """
        Tests that accessing the '/qr_card' endpoint requires the user to be logged in.
        It verifies that an unauthenticated request is redirected to the login page.

        Args:
            self: Test case instance required by the testing framework.
            client: Test client used to simulate HTTP requests in the application.

        Raises:
            AssertionError: If the response status code is not 302 or if the 'login'
            string is not present in the response location URL.
        """
        response = client.get('/qr_card')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_member_card_valid_token(self, client, app):  # app-Fixture hinzugefügt
        """
        Tests the verification of a valid token for a member card. This test ensures that when a valid
        token is provided, the server responds with status code 200 and includes the user's first name
        in the response data.

        Args:
            self: Represents the instance of the test class.
            client: Test client used to send HTTP requests to the application.
            app: Flask application fixture providing the application context.

        Raises:
            AssertionError: If the response does not have status code 200 or the user's first name is
            not found in the response data.
        """
        user_data = {
            "user_id": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "Member"
        }

        with app.app_context():
            token = generate_token(user_data)
            response = client.get(f'/verify/{token}')
            assert response.status_code == 200
            assert user_data['first_name'].encode() in response.data

    def test_invalid_token(self, client):
        """
        Tests the server's response to an invalid token request.

        This test ensures that when a request with an invalid token is performed,
        the server returns a 403 Forbidden status code.

        Args:
            client: A test client instance used to simulate HTTP requests in the
                testing framework.

        Raises:
            AssertionError: If the status code of the response is not 403.
        """
        response = client.get('/verify/ungültiger_token')
        assert response.status_code == 403

    def test_empty_token(self, client):
        """
        Tests the behavior of the server when a request is made to the '/verify/'
        endpoint without providing a token.

        Parameters:
            client: The test client used to simulate HTTP requests.

        Raises:
            AssertionError: If the response status code does not equal 404.
        """
        response = client.get('/verify/')
        assert response.status_code == 404

    def test_expired_token(self, client, monkeypatch):
        """
        Tests the behavior of the API when provided with an expired token. This test ensures
        that the server properly handles expired tokens by returning an appropriate HTTP
        response status code.

        Arguments:
            client: The test client used to simulate HTTP requests.
            monkeypatch: A pytest fixture that allows dynamic modification of imported
                objects, enabling the simulation of specific conditions or behaviors.

        Raises:
            SignatureExpired: Simulates the exception that is raised when a token
                has expired.
        """
        from itsdangerous import SignatureExpired
        import core.token_manager

        # Simuliere abgelaufenen Token
        monkeypatch.setattr(core.token_manager, "decode_token",
                            lambda token: (_ for _ in ()).throw(SignatureExpired("Token abgelaufen")))

        response = client.get('/verify/some_token')
        assert response.status_code == 403

    from itsdangerous import URLSafeTimedSerializer  # Import muss am Anfang der Datei stehen

    def test_send_email_invalid_token(self, client, app, monkeypatch):
        """
        Tests the behavior of the '/send_email' endpoint when an invalid token is provided.

        This function ensures that when a POST request is made to the '/send_email' endpoint with an
        invalid token, the application correctly redirects to the expected page and returns the
        appropriate HTTP status code.

        Args:
            client: The test client for making requests to the Flask application.
            app: The Flask application instance used during testing.
            monkeypatch: A testing utility to dynamically modify or override behaviors.

        Raises:
            AssertionError: If the test does not meet the expected conditions.
        """
        with app.test_client() as test_client:
            with app.app_context():
                response = test_client.post('/send_email', data={
                    'recipient': 'test@example.com',
                    'token': 'ungültiger_token'
                })

                assert response.status_code == 302
                assert url_for('cards.qr_card') in response.location

    def test_verify_invalid_token(self, client):
        """
        Tests the behavior of a verification endpoint when provided with an
        invalid token. Ensures the correct response is returned for a token
        that is not valid.

        Args:
            self: Represents the instance of the test case.
            client: A test client instance used to simulate requests to
                the application.

        Raises:
            AssertionError: If the response does not have the status code 403
                or the expected text does not appear in the response data.
        """
        response = client.get('/verify/invalid-token')
        assert response.status_code == 403
        assert b'expired' in response.data

    def test_verify_missing_token(self, client):
        """
        This function tests the behavior of the '/verify/' endpoint when no token is
        provided. It ensures that the endpoint returns the correct HTTP status code
        indicating that the resource was not found.

        Args:
            client: A test client instance used to send HTTP requests to the
                application.

        Raises:
            AssertionError: If the actual status code does not match the expected
                status code.

        Returns:
            None
        """
        response = client.get('/verify/')
        assert response.status_code == 404