# tests/conftest.py

import os
import sys
import pytest
import tempfile
from pathlib import Path
from flask_login import login_user
from core.extensions import SimpleUser


# Füge das Projektverzeichnis zum Python-Path hinzu
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)


@pytest.fixture
def app():
    """
    Fixture for setting up a Flask application for testing purposes.

    This fixture initializes a Flask app configured for testing. It provides a
    temporary database and other necessary configurations for test cases. After
    yielding the app, it ensures proper cleanup of temporary resources to avoid
    side effects between tests.

    Yields:
        Flask: The Flask application instance configured for testing.
    """
    from app import create_app

    # Temporäre Testdatenbank
    db_fd, db_path = tempfile.mkstemp()

    test_config = {
        'TESTING': True,
        'MEMBER_DB': db_path,
        'WTF_CSRF_ENABLED': False,
        'PHOTO_UPLOAD_FOLDER': tempfile.mkdtemp(),
        'SECRET_KEY': 'test_key_for_secure_token_generation',  # Wichtig für generate_token
        'FERNET_KEY': b'test_key_for_testing_only_needs_32_b',
        'TOKEN_MAX_AGE_SECONDS': 3600  # Optional: Setzt die Token-Gültigkeit für Tests
    }

    app = create_app()
    app.config.update(test_config)

    yield app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """
    Creates a test client for a Flask application.

    This fixture provides a simulated test client for the Flask application, enabling the
    execution of HTTP requests to test endpoints without starting an actual server. The
    client is persisted within the test scope and ensures isolation for testing purposes.

    Parameters
    ----------
    app : flask.Flask
        The Flask application instance for which the test client is to be created.

    Returns
    -------
    werkzeug.test.Client
        An instance of a Flask test client that can be used to simulate requests to the
        application.
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    A pytest fixture to provide a test CLI runner for the given Flask app.

    This fixture sets up a command-line runner for the Flask testing
    environment, enabling the execution of CLI commands during tests.

    Args:
        app: The Flask application instance for which the test CLI runner is
            configured.

    Returns:
        A CLI runner instance bound to the provided Flask app.
    """
    return app.test_cli_runner()


@pytest.fixture
def user_session(client):
    """
    Creates a test user session for use in pytest-based tests.

    This fixture initializes a session with a predefined user email
    and associated metadata. It mimics an authenticated user session
    by setting session data and returns a dictionary containing the
    user's email and a generated unique photo identifier based on
    their email.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        The Flask test client used to simulate requests and manage the
        session context.

    Returns
    -------
    dict
        A dictionary containing the user's email and a unique photo
        identifier computed as a hash of the email string.
    """
    with client.session_transaction() as session:
        session['email_userinfo'] = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
    return {
        'email': 'test@example.com',
        'photo_id': hashlib.sha256('test@example.com'.encode()).hexdigest()[:16]
    }


@pytest.fixture
def admin_login(client):
    """
    Creates a pytest fixture for establishing an admin login session.

    This fixture configures a session with preset admin user credentials and updates the client application
    configuration to recognize the specified admin email. It simplifies testing admin-related functionality
    by pre-authenticating as an admin user.

    Yields
    ------
    dict
        The session dictionary after modification for admin user authentication.
    """
    with client.session_transaction() as session:
        session['email_userinfo'] = {'email': 'admin@example.com'}
    # Admin in der App-Konfiguration hinzufügen
    client.application.config['ADMIN_EMAILS'] = ['admin@example.com']
    return session
