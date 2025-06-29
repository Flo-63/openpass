# test_photo.py
import pytest
from io import BytesIO
import hashlib
import os
from pathlib import Path


class TestPhoto:
    """
    TestPhoto class contains the implementation of test cases for handling photo-related operations in a web application.

    The class includes tests for scenarios such as uploading a photo, attempting uploads without providing a file,
    deleting photos, and retrieving photos. Additionally, it defines fixtures like mock photo creation and user session
    setup required for the test cases. The class ensures functionality and error handling of photo operations via various
    test cases.
    """
    @pytest.fixture
    def mock_photo(self):
        """
        Provides a pytest fixture for creating a mock photo object for testing purposes.

        Yields:
            Tuple[BytesIO, str]: A tuple containing a BytesIO object with mock image data
            and a string representing the file name.
        """
        return (BytesIO(b"test image data"), 'test.jpg')

    @pytest.fixture
    def user_session(self, client):
        """
        Provides a pytest fixture for creating a user session with predefined session data.

        This fixture sets up a user session using a client session transaction. The
        session is modified to include an 'email_userinfo' dictionary containing an
        email address representing a logged-in user.

        Attributes:
            client (Client): The client fixture provided by pytest to simulate
                requests in tests.

        Returns:
            SessionMixin: The modified session object with predefined 'email_userinfo'
            data.
        """
        with client.session_transaction() as session:
            session['email_userinfo'] = {'email': 'test@example.com'}
        return session

    def test_photo_upload(self, client, mock_photo, user_session):
        """
        Tests the photo upload functionality of the application by sending a mock photo
        using a POST request and checking the response status code to ensure it redirects
        correctly.

        Parameters:
        client : object
            The test client used to simulate HTTP requests to the application.
        mock_photo : file-like object
            A mocked photo file object used as part of the test data in the request.
        user_session : object
            The session tied to the authenticated user performing the test.

        Returns:
        None
        """
        data = {
            'photo': mock_photo
        }
        response = client.post('/handle_photo_upload',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code == 302

    def test_photo_upload_without_file(self, client, user_session):
        """
        Tests the behavior of the photo upload endpoint when no file is provided.

        The test verifies that the server correctly handles a POST request to the
        photo upload endpoint without a file being selected, and ensures the
        appropriate redirection and error message display behavior.

        Parameters:
        self : TestCase
            The instance of the test class.
        client : FlaskClient
            The Flask test client used to simulate HTTP requests to the server.
        user_session : object
            The session information or user context required for the request.

        Raises:
        AssertionError
            If the response status code or the content does not match the expected
            outcome.
        """
        response = client.post('/handle_photo_upload')
        assert response.status_code == 302
        response = client.post('/handle_photo_upload', follow_redirects=True)
        assert b'No file selected' in response.data

    def test_photo_delete(self, client, user_session):
        """
        Test the photo delete functionality.

        This test ensures that a POST request to the '/delete_photo' endpoint results in a
        redirect response, which indicates the deletion request was processed successfully.

        Parameters:
            client: The test client instance used to simulate HTTP requests.
            user_session: The session object representing an authenticated user.

        Raises:
            AssertionError: If the response status code is not 302.
        """
        response = client.post('/delete_photo')
        assert response.status_code == 302

    def test_photo_retrieve(self, client, mock_photo, user_session, app):
        """
        Tests the functionality of photo retrieval in an application by simulating a session, uploading a photo, generating a
        token, and attempting to retrieve the photo using a secure link. The test checks the correctness of the overall flow
        and ensures that the retrieved photo has the expected status code and content type.

        Parameters:
            self: Test class instance containing the test case context. Used for class-level variables and utilities.
            client: Instance of the Flask test client to simulate and test HTTP requests and responses within the application.
            mock_photo: A mock representation of the photo to be uploaded, simulating user-provided photo input.
            user_session: User session data to simulate authenticated access during the test.
            app: Flask application instance providing the application context for executing the test.

        Returns:
            None
        """
        with app.app_context():
            # Session-Daten setzen
            with client.session_transaction() as sess:
                sess['email_userinfo'] = {'email': 'test@example.com'}

            # Erst Foto hochladen
            upload_response = client.post('/handle_photo_upload',
                                          data={'photo': mock_photo},
                                          content_type='multipart/form-data')
            assert upload_response.status_code == 302

            # Email und Photo-ID vorbereiten
            test_email = 'test@example.com'
            photo_id = hashlib.sha256(test_email.strip().lower().encode()).hexdigest()[:16]

            # Token generieren
            from core.token_manager import generate_token
            token = generate_token({
                'user_id': test_email,
                'photo_id': photo_id
            })

            # Debug-Ausgaben
            print(f"\nDEBUG INFO:")
            print(f"Photo ID: {photo_id}")
            print(f"Token: {token}")
            print(f"Request URL: /photo/{photo_id}?token={token}")

            # Foto abrufen mit Token als Query-Parameter
            response = client.get(f'/photo/{photo_id}?token={token}')

            # Debug-Ausgaben für Fehleranalyse
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {response.headers}")
            if hasattr(response, 'data'):
                print(f"Response data length: {len(response.data)}")

            assert response.status_code == 200
            assert response.content_type.startswith('image/')









