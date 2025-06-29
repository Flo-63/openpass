import pytest
from flask import url_for
from core.token_manager import generate_token

class TestMemberCard:
    """
    A test class for validating the functionality of member card data processing.

    Contains test methods to ensure correct behavior in rendering member card data
    with various input scenarios, such as valid user data and fallback mechanisms
    for missing or alternative name fields.
    """
    def test_member_card_valid_data(self, client):
        """
        Tests the member card verification functionality with valid user data. The test creates a
        user token with user details, simulates a request to verify the token, and checks if the
        response contains the expected user information.

        Args:
            client: Flask test client used to simulate application requests.

        Raises:
            AssertionError: If the verification response does not contain the expected user details.
        """
        user_data = {
            "user_id": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "Mitglied",
            "photo_id": "dummy"
        }
        with client.application.app_context():
            token = generate_token(user_data)

        response = client.get(f"/verify/{token}")
        html = response.data.decode()
        assert "Test" in html
        assert "User" in html

    def test_member_card_name_fallback(self, client):
        """
        Test the fallback mechanism for displaying a user's name in the member card.

        This function validates that a user's display name appears correctly in the HTML response
        when the `/verify` endpoint is called with a valid token. It ensures that the fallback
        displays the expected value of the `display_name` attribute.

        Args:
            client: A test client instance used to send requests to the application.
        """
        user_data = {
            "user_id": "test@example.com",
            "display_name": "Test User",
            "role": "Mitglied",
            "photo_id": "dummy",
            "first_name": "Test",
            "last_name": "User"
        }
        with client.application.app_context():
            token = generate_token(user_data)

        response = client.get(f"/verify/{token}")
        html = response.data.decode()
        assert "Test User" in html
