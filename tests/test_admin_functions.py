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


class TestAdminRouteProtection:
    """
    Pins down that every route of the admin blueprint requires an allow-listed admin.

    A decorator placed above the route decorator is silently ignored by Flask, which
    once left the CSV import endpoints reachable without any authentication. These
    tests fail loudly if that ever happens again.
    """

    ADMIN_ROUTES = [
        ('get', '/upload_members'),
        ('post', '/upload_members'),
        ('post', '/members/import-validate'),
        ('post', '/members/import-commit'),
        ('post', '/members/import-revalidate'),
        ('post', '/members/sync-validate'),
        ('post', '/members/sync-commit'),
        ('get', '/members'),
        ('get', '/members/list'),
        ('get', '/members/new'),
        ('post', '/members/save'),
        ('get', '/members/hash-preview'),
        ('get', '/members/edit/deadbeef'),
        ('delete', '/members/delete/deadbeef'),
    ]

    def test_every_admin_route_is_registered_behind_the_guard(self, app):
        """
        Ensures the route list above stays in sync with the blueprint.

        A new admin endpoint that nobody added here would otherwise never be checked.
        """
        registered = {
            str(rule) for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith('admin.')
        }
        covered = {path for _, path in self.ADMIN_ROUTES}
        # Rules carrying converters are compared by their template form.
        registered = {r.replace('<email_hash>', 'deadbeef') for r in registered}
        covered = {c.replace('deadbeef', 'deadbeef') for c in covered}
        assert registered <= covered, f"Unprotected/untested admin routes: {registered - covered}"

    def test_anonymous_is_rejected(self, client):
        """Anonymous callers must not reach any admin endpoint."""
        for method, path in self.ADMIN_ROUTES:
            response = getattr(client, method)(path)
            assert response.status_code == 404, f"{method.upper()} {path} -> {response.status_code}"

    def test_authenticated_non_admin_is_rejected(self, client):
        """A signed-in member who is not allow-listed must not reach admin endpoints."""
        client.application.config['ADMIN_EMAILS'] = ['admin@example.com']
        with client.session_transaction() as sess:
            sess['email_userinfo'] = {'email': 'member@example.com'}
            sess['_user_id'] = 'member@example.com'
            sess['_fresh'] = True

        for method, path in self.ADMIN_ROUTES:
            response = getattr(client, method)(path)
            assert response.status_code == 404, f"{method.upper()} {path} -> {response.status_code}"

    def test_import_commit_cannot_wipe_the_database_anonymously(self, client):
        """
        The unauthenticated import endpoint used to drop and rebuild the members table.

        An empty POST was enough to delete every member, so this specific request is
        worth its own test.
        """
        assert client.post('/members/import-commit').status_code == 404

    def test_empty_admin_email_entry_grants_nothing(self, app):
        """A misparsed ADMIN_EMAILS value must never authorise an empty email address."""
        from core.extensions import is_admin_user

        app.config['ADMIN_EMAILS'] = ['']
        with app.test_request_context():
            assert is_admin_user() is False