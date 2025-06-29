import io
from flask_login import login_user
from core.extensions import SimpleUser
from flask import url_for
from werkzeug.exceptions import NotFound


class TestAdminFunctions:
    """
    Tests functionalities related to administrative actions and user permissions.

    This class is intended to validate the behavior of administrative features
    like route access checks and member CSV uploads. It includes tests for:
    - Verifying that users without adequate permissions cannot access
      admin-specific routes such as '/upload_members'.
    - Testing the process of uploading a well-formed member CSV file by authorized
      administrators, ensuring proper handling, storing, and feedback mechanisms.
    """
    def test_admin_access_without_permission(self, client):
        """
        Tests the admin access to the '/upload_members' route for a user without
        sufficient permissions.

        Attributes:
            client (FlaskClient): The test client object used to simulate HTTP
            requests to the application.

        Args:
            self (TestCase): The test case instance that this method is a part of.
            client (FlaskClient): The Flask test client used to simulate requests.

        Raises:
            NotFound: Exception is raised when the '/upload_members' route is
            accessed without proper permissions, simulating a 404 error response.
        """
        with client as c:
            with c.session_transaction() as sess:
                sess['email_userinfo'] = {'email': 'user@example.com'}
                user = SimpleUser('user@example.com', email='user@example.com')
                with c.application.test_request_context():
                    login_user(user)
                    sess['_user_id'] = user.get_id()
            try:
                assert c.get('/upload_members').status_code == 404
            except NotFound:
                pass

    def test_member_csv_upload(self, client):
        """
        Tests the functionality for uploading a member CSV file via the specified client.
        This test is designed to ensure that authenticated administrators can upload a
        properly formatted CSV file and that the server processes the data correctly,
        redirects upon success, and provides appropriate feedback messages.

        Parameters:
            client: A test client instance used to simulate HTTP requests during the test.

        Raises:
            AssertionError: If the response status code is not as expected (302) or if
            the follow-up content does not contain the expected success message.
        """
        with client as c:
            c.application.config['ADMIN_EMAILS'] = ['admin@example.com']
            with c.session_transaction() as sess:
                sess['email_userinfo'] = {'email': 'admin@example.com'}
                user = SimpleUser('admin@example.com', email='admin@example.com')
                with c.application.test_request_context():
                    login_user(user)
                    sess['_user_id'] = user.get_id()

            csv_content = (
                'email,firstname,lastname,role,joindate\n'
                'test@example.com,Test,User,Member,2024-01-01\n'
            )
            data = {'csv_file': (io.BytesIO(csv_content.encode()), 'members.csv')}
            response = c.post('/upload_members', data=data, content_type='multipart/form-data')
            assert response.status_code == 302
            follow_up = c.get(response.location)
            assert b'members successfully saved' in follow_up.data