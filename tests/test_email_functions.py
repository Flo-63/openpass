from unittest.mock import Mock, patch

import pytest
from utils.email_utils import send_membership_email

# Gültige Testdaten
_VALID_USER = {
    "first_name": "John",
    "last_name": "Doe",
    "user_id": 123,
}


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────
@pytest.fixture
def mail_app(app):
    """Erweitert die Standard‑App um Mail‑Konfiguration."""
    app.config.update(
        BRANDING={
            "club_name": "Test Club",
            "contact_email": "contact@testclub.com",
            "theme_color": "#123456",
        },
        MAIL_SENDER_NAME="Test Sender",
        MAIL_SENDER_ADDRESS="noreply@testclub.com",
        SMTP_USERNAME="test_user",
        SMTP_PASSWORD="test_password",
        SMTP_SERVER="smtp.testclub.com",
        SMTP_PORT=587,
    )
    return app


# ─────────────────────────────────────────────
# Test‑Klasse
# ─────────────────────────────────────────────
class TestSendMembershipEmail:
    """
    Test suite for email sending functionality related to membership emails.

    This class contains multiple test cases to verify the behavior of the
    `send_membership_email` function under various scenarios. These include
    email transmission success, handling of missing user data, invalid sender
    addresses, missing logo files, and SMTP-related errors. All tests utilize
    the pytest framework and mock utilities to simulate and validate the
    application's email-sending behavior.

    Methods:
        test_success: Verifies the successful sending of an email, with a logo present.
        test_missing_user_data: Tests the behavior when mandatory user data is missing.
        test_invalid_sender_address: Checks behavior when the sender email address is invalid.
        test_logo_not_found: Verifies email is sent even when the logo file is missing.
        test_smtp_error: Tests the function's handling of SMTP exceptions.
    """
    def test_success(self, mail_app):
        """
        Tests the successful sending of an email using the `send_membership_email` function.
        This test ensures the email utility correctly interacts with the mock SMTP server,
        establishes a secure connection, logs in with credentials, and sends the email.

        Parameters:
        mail_app: Flask
            An instance of the Flask application configured for testing email functionality.
        """
        with mail_app.app_context(), \
             patch("utils.email_utils.smtplib.SMTP") as mock_smtp, \
             patch("utils.email_utils.Path.exists", return_value=True):

            smtp_inst = mock_smtp.return_value.__enter__.return_value
            smtp_inst.send_message = Mock()

            assert send_membership_email("user@example.com", _VALID_USER)
            smtp_inst.starttls.assert_called_once()
            smtp_inst.login.assert_called_once_with("test_user", "test_password")
            smtp_inst.send_message.assert_called_once()

    def test_missing_user_data(self, mail_app):
        """
        This function tests the behavior of the `send_membership_email` function when the user data is incomplete.
        It verifies that the function correctly handles cases where mandatory user information is missing
        and ensures the function returns `False` under such conditions.

        Parameters:
        mail_app: Flask
            The Flask application instance used in the test.`app_context` is utilized to provide the app context
            necessary for executing the test.

        Returns:
        None
        """
        with mail_app.app_context():
            partial_user = {"first_name": "John", "last_name": "Doe"}  # user_id fehlt
            assert send_membership_email("user@example.com", partial_user) is False

    def test_invalid_sender_address(self, mail_app):
        """
        Tests the scenario where an invalid sender email address is configured in the
        mail application.

        Parameters:
        self
            The test instance itself.
        mail_app
            A configured mail application instance for use in testing.
        """
        mail_app.config["MAIL_SENDER_ADDRESS"] = "invalid"
        with mail_app.app_context():
            assert send_membership_email("user@example.com", _VALID_USER) is False

    def test_logo_not_found(self, mail_app):
        """
        Tests the scenario where the logo file required for the email cannot be found, and ensures
        that the email is still sent successfully despite the missing logo.

        Parameters:
        mail_app: Flask
            A Flask application instance configured for the mail system.

        Raises:
        AssertionError
            If the membership email is not sent or the send_message method is not called exactly once.
        """
        with mail_app.app_context(), \
             patch("utils.email_utils.smtplib.SMTP") as mock_smtp, \
             patch("utils.email_utils.Path.exists", return_value=False):

            smtp_inst = mock_smtp.return_value.__enter__.return_value
            smtp_inst.send_message = Mock()

            assert send_membership_email("user@example.com", _VALID_USER)
            smtp_inst.send_message.assert_called_once()

    def test_smtp_error(self, mail_app):
        """
        Tests the behavior of the email sending function when an SMTP error occurs.

        This test verifies that the send_membership_email function will correctly handle
        a situation where an SMTP-related error is raised, ensuring that the function
        fails gracefully and returns the appropriate response.

        Args:
            mail_app (Flask): Instance of a Flask application configured for tests.

        Raises:
            Exception: Mimics an SMTP error with a custom error message "SMTP fail".
        """
        with mail_app.app_context(), \
             patch("utils.email_utils.smtplib.SMTP", side_effect=Exception("SMTP fail")):
            assert send_membership_email("user@example.com", _VALID_USER) is False


