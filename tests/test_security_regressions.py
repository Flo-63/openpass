"""
===============================================================================
Project   : openpass
Module    : tests/test_security_regressions.py
Created   : 2026-08-21
Author    : Florian
Purpose   : Regression tests for the findings of the 2026-08 security audit.
            Every test in this file fails against the tree as it stood before the
            corresponding fix. Each test names the finding it guards.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

import io
import os
import json
import struct
import zlib

import pytest

from core.token_manager import decode_token, verify_email_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_png(width: int, height: int) -> bytes:
    """
    Builds a valid greyscale PNG of the requested size.

    A uniform image compresses to a tiny payload, which is exactly what makes the
    decompression ratio dangerous: the bytes on the wire say nothing about the memory
    the decoded image needs.

    Args:
        width (int): Image width in pixels.
        height (int): Image height in pixels.

    Returns:
        bytes: Encoded PNG data.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def member_client(app, client):
    """
    Returns a test client with a logged-in member session.

    Args:
        app: The Flask application fixture.
        client: The Flask test client fixture.

    Returns:
        FlaskClient: Client carrying a session that passes the photo endpoints' checks.
    """
    with client.session_transaction() as session:
        session["email_userinfo"] = {
            "email": "regression@example.com",
            "first_name": "Reg",
            "last_name": "Ression",
        }
    return client


# ---------------------------------------------------------------------------
# K1 - the production Fernet key must not be readable from the source tree
# ---------------------------------------------------------------------------
class TestNoHardcodedKeys:
    """Guards against a secret literal returning to a versioned file."""

    def test_dbcheck_script_has_no_key_literal(self):
        """
        Fails if utils/scripts/dbcheck.py carries a Fernet key literal again.

        The production key used to sit in this file and therefore in the public git
        history, where it decrypted the whole members database.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "utils" / "scripts" / "dbcheck.py"
        ).read_text(encoding="utf-8")

        assert "FERNET_KEY = b'" not in source
        assert 'FERNET_KEY = b"' not in source
        assert "os.getenv" in source, "the script must read the key from the environment"

    def test_no_fernet_key_literal_anywhere_in_the_tree(self):
        """
        Scans every versioned Python file for something shaped like a Fernet key.

        A Fernet key is 44 characters of urlsafe base64 ending in '='. Assigning such a
        literal to a name containing KEY is what this test refuses.
        """
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        pattern = re.compile(
            r"""(?i)(fernet|secret|photo_encryption)_key\s*=\s*b?['"][A-Za-z0-9_\-=]{32,}['"]"""
        )
        offenders = []
        for path in root.rglob("*.py"):
            parts = set(path.parts)
            if parts & {".venv", "venv", "node_modules", "__pycache__", ".git"}:
                continue
            if path.name == "test_security_regressions.py":
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(root)}:{number}")

        assert not offenders, f"key literals found: {offenders}"


# ---------------------------------------------------------------------------
# H2 / M5 - upload resolution bound, and the bomb error must be handled
# ---------------------------------------------------------------------------
class TestPhotoUploadLimits:
    """Covers the memory exhaustion and the unhandled DecompressionBombError."""

    def test_oversized_image_is_rejected_without_decoding(self, app, member_client):
        """
        A 13000x13000 PNG is 160 KB on the wire and ~500 MB decoded.

        Before the fix this was accepted and allocated the full buffer. It must now be
        refused with a redirect and a flash message, like any other invalid upload.
        """
        payload = make_png(13000, 13000)
        assert len(payload) < app.config["MAX_CONTENT_LENGTH"], (
            "the point of this test is that the byte limit does not catch it"
        )

        response = member_client.post(
            "/handle_photo_upload",
            data={"photo": (io.BytesIO(payload), "bomb.png")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert "/upload_photo" in response.headers["Location"]

    def test_decompression_bomb_does_not_surface_as_500(self, member_client):
        """
        An image above Pillow's own threshold raises DecompressionBombError.

        That class inherits from Exception rather than OSError or ValueError, so the
        original except clause let it escape as an unhandled 500.
        """
        payload = make_png(16000, 16000)

        response = member_client.post(
            "/handle_photo_upload",
            data={"photo": (io.BytesIO(payload), "bomb.png")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302, "must be rejected cleanly, not crash"

    def test_reasonable_image_is_still_accepted(self, member_client):
        """A normal photo must keep working - the limit must not reject everything."""
        payload = make_png(800, 600)

        response = member_client.post(
            "/handle_photo_upload",
            data={"photo": (io.BytesIO(payload), "portrait.png")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert "/qr_card" in response.headers["Location"]


# ---------------------------------------------------------------------------
# M1 - HSTS
# ---------------------------------------------------------------------------
class TestSecurityHeaders:
    """Covers the missing Strict-Transport-Security header."""

    def test_hsts_present_on_https(self, app, client):
        """The header must be sent over a secure connection."""
        response = client.get("/", base_url="https://localhost")

        header = response.headers.get("Strict-Transport-Security")
        assert header is not None, "HSTS header missing"
        assert "max-age=" in header
        assert int(header.split("max-age=")[1].split(";")[0]) > 0

    def test_hsts_absent_on_plain_http(self, client):
        """
        The header must not be sent over plain HTTP.

        Browsers ignore it there anyway, and emitting it in local development would pin
        localhost to HTTPS for the configured duration.
        """
        response = client.get("/", base_url="http://localhost")

        assert response.headers.get("Strict-Transport-Security") is None

    def test_subdomains_not_pinned_by_default(self, client):
        """includeSubDomains must stay opt-in - it cannot be withdrawn quickly."""
        response = client.get("/", base_url="https://localhost")

        assert "includeSubDomains" not in response.headers.get(
            "Strict-Transport-Security", ""
        )

    def test_baseline_headers_still_present(self, client):
        """The headers that already worked must not regress."""
        response = client.get("/")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ---------------------------------------------------------------------------
# M2 - CSP source list
# ---------------------------------------------------------------------------
class TestContentSecurityPolicy:
    """Covers the CDN allow-list that could be used to sidestep the nonce."""

    def _policy(self, client):
        response = client.get("/")
        return response.headers.get(
            "Content-Security-Policy"
        ) or response.headers.get("Content-Security-Policy-Report-Only", "")

    def test_script_src_allows_no_public_cdn(self, client):
        """
        Every script the app serves comes from 'self'.

        A CDN in script-src is a documented way around a nonce-based policy, because
        several hosted libraries can be coerced into executing attacker-supplied markup.
        """
        policy = self._policy(client)
        script_src = [d for d in policy.split(";") if d.strip().startswith("script-src")]

        assert script_src, "script-src directive missing"
        for directive in script_src:
            for host in (
                "cdnjs.cloudflare.com",
                "code.jquery.com",
                "cdn.plot.ly",
                "kit.fontawesome.com",
                "stackpath.bootstrapcdn.com",
                "accounts.google.com",
            ):
                assert host not in directive, f"{host} still allowed in {directive!r}"

    def test_script_src_keeps_nonce(self, client):
        """The nonce must survive the trim, or every inline script breaks."""
        assert "'nonce-" in self._policy(client)

    def test_no_empty_directive_entries(self, client):
        """
        An unset OAuth domain used to leave a stray separator in the header.

        Two spaces in a row mean an empty source expression was joined into the policy.
        """
        assert "  " not in self._policy(client)


# ---------------------------------------------------------------------------
# M3 - CSP report log injection
# ---------------------------------------------------------------------------
class TestCspReportLogInjection:
    """Covers forged log lines written through the unauthenticated report endpoint."""

    def test_newlines_are_escaped(self, app, client, caplog):
        """
        A report field containing a newline must not produce a second log line.

        Before the fix the injected text landed in csp.log on its own line, formatted
        exactly like a genuine entry from another logger.
        """
        forged = (
            "http://evil.test\n"
            "2026-01-01 00:00:00 | CRITICAL | auth_logger | FORGED admin login"
        )

        with caplog.at_level("WARNING", logger="csp_logger"):
            response = client.post(
                "/csp-report", json={"csp-report": {"document-uri": forged}}
            )

        assert response.status_code == 204
        records = [r for r in caplog.records if r.name == "csp_logger"]
        assert records, "the report should still be logged"
        for record in records:
            message = record.getMessage()
            assert "\n" not in message, "newline reached the log record"
            assert "\r" not in message

    def test_oversized_field_is_truncated(self, client, caplog):
        """A single field must not be able to flood the log file."""
        with caplog.at_level("WARNING", logger="csp_logger"):
            client.post(
                "/csp-report", json={"csp-report": {"blocked-uri": "A" * 50_000}}
            )

        records = [r for r in caplog.records if r.name == "csp_logger"]
        assert records
        assert all(len(r.getMessage()) < 5_000 for r in records)

    def test_non_dict_report_body_is_handled(self, client):
        """A JSON body that is not an object must not raise."""
        response = client.post("/csp-report", json=["not", "an", "object"])
        assert response.status_code == 204

    def test_endpoint_remains_csrf_exempt(self, app, client):
        """
        Browsers send violation reports without a CSRF token.

        Re-enabling CSRF on this endpoint would silently discard every real report.
        """
        app.config["WTF_CSRF_ENABLED"] = True
        try:
            response = client.post(
                "/csp-report", json={"csp-report": {"document-uri": "http://x.test"}}
            )
            assert response.status_code == 204
        finally:
            app.config["WTF_CSRF_ENABLED"] = False


# ---------------------------------------------------------------------------
# M4 - full email hashes in the auth log
# ---------------------------------------------------------------------------
class TestLogHashMasking:
    """Covers the full SHA-256 digest that used to sit next to a masked address."""

    def test_mask_hash_truncates(self, app):
        """
        The helper must not return the full digest.

        Takes the `app` fixture even though it does not use it: importing the auth
        blueprint binds `limiter` at module import time, so the application has to
        exist before this module is imported for the first time.
        """
        from blueprints.auth.email import _mask_hash

        digest = "a" * 64
        masked = _mask_hash(digest)

        assert len(masked) < 20
        assert digest not in masked

    def test_login_request_does_not_log_full_hash(self, app, client, caplog, monkeypatch):
        """
        Requesting a login link must not write the complete hash.

        The address is masked to `abc***` in the same line; a full digest beside it
        identifies the member exactly, which undoes the masking.
        """
        import hashlib
        import os
        import sqlite3

        from core.extensions import fernet
        from utils import email_utils

        email = "member@example.com"
        full_hash = hashlib.sha256(email.encode()).hexdigest()

        # The handler reads the member before it logs, so the row has to exist.
        db_path = os.path.join(app.instance_path, app.config["MEMBER_DB"])
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS members (
                   email_hash TEXT PRIMARY KEY,
                   first_name_enc TEXT NOT NULL,
                   last_name_enc TEXT NOT NULL,
                   join_year BLOB,
                   role BLOB)"""
        )
        conn.execute(
            "INSERT OR REPLACE INTO members VALUES (?, ?, ?, NULL, NULL)",
            (
                full_hash,
                fernet.encrypt(b"Mit").decode(),
                fernet.encrypt(b"Glied").decode(),
            ),
        )
        conn.commit()
        conn.close()

        # Do not actually try to reach a mail server.
        monkeypatch.setattr(email_utils, "send_login_email", lambda *a, **k: True)
        monkeypatch.setattr(
            "blueprints.auth.email.send_login_email", lambda *a, **k: True
        )

        with caplog.at_level("INFO", logger="auth_logger"):
            response = client.post("/request_email_login", data={"email": email})

        assert response.status_code == 302
        messages = [r.getMessage() for r in caplog.records]
        assert any("Login link sent" in m for m in messages), (
            f"the log line under test was not emitted: {messages}"
        )
        for message in messages:
            assert full_hash not in message


# ---------------------------------------------------------------------------
# N1 - missing token must not raise
# ---------------------------------------------------------------------------
class TestMissingToken:
    """Covers the unhandled TypeError on a token-less request."""

    def test_decode_token_handles_none(self, app):
        """decode_token(None) must return None, not raise."""
        with app.test_request_context():
            assert decode_token(None) is None
            assert decode_token("") is None

    def test_verify_email_token_handles_none(self, app):
        """The email token verifier must behave the same way."""
        with app.test_request_context():
            assert verify_email_token(None) is None

    def test_photo_endpoint_without_token_is_forbidden_not_500(self, client):
        """
        /photo/<id> without a token parameter must answer 403.

        It previously raised TypeError deep inside itsdangerous and returned 500.
        """
        response = client.get("/photo/0123456789abcdef")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# F2 - admin detection must agree between template and guard
# ---------------------------------------------------------------------------
class TestAdminDetectionConsistency:
    """Covers the case-sensitivity mismatch between the guard and the template flag."""

    def test_mixed_case_admin_is_recognised_in_templates(self, app):
        """
        An administrator whose provider reports a capitalised address must be shown
        the admin link, exactly as the guard lets them through.
        """
        from core.context_processors import inject_is_admin
        from core.extensions import is_admin_user

        app.config["ADMIN_EMAILS"] = ["admin@example.com"]

        with app.test_request_context():
            with app.test_client().session_transaction() as session:
                session["email_userinfo"] = {"email": "Admin@Example.COM"}

            from flask_login import login_user
            from core.extensions import SimpleUser

            login_user(SimpleUser("Admin@Example.COM", email="Admin@Example.COM"))

            assert is_admin_user() is True
            assert inject_is_admin() == {"is_admin": True}

    def test_non_admin_is_not_flagged(self, app):
        """The flag must stay false for everyone else."""
        from core.context_processors import inject_is_admin

        app.config["ADMIN_EMAILS"] = ["admin@example.com"]

        with app.test_request_context():
            assert inject_is_admin() == {"is_admin": False}


# ---------------------------------------------------------------------------
# F1 - the next parameter must reach the OAuth entry point
# ---------------------------------------------------------------------------
class TestNextParameter:
    """Covers the redirect target that was dropped on the way to the login page."""

    def test_local_next_is_carried_into_the_oauth_link(self, client):
        """A local path must appear in the OAuth link on the login page."""
        response = client.get("/login?next=/qr_card")

        assert response.status_code == 200
        assert b"next=%2Fqr_card" in response.data or b"next=/qr_card" in response.data

    def test_absolute_next_is_refused(self, client):
        """An off-site URL must never reach the link - that would be an open redirect."""
        response = client.get("/login?next=https://evil.test/phish")

        assert b"evil.test" not in response.data

    def test_protocol_relative_next_is_refused(self, client):
        """`//evil.test` is an absolute URL to a browser."""
        response = client.get("/login?next=//evil.test/phish")

        assert b"evil.test" not in response.data


# ---------------------------------------------------------------------------
# N2 - gitignore patterns must actually match
# ---------------------------------------------------------------------------
class TestGitignorePatterns:
    """Covers the inline comments that turned two rules into dead patterns."""

    def test_no_inline_comments_in_gitignore(self):
        """
        Git only treats '#' as a comment at the start of a line.

        Anywhere else the text joins the pattern, which then matches nothing.
        """
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / ".gitignore"
        offenders = []
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "#" in line:
                offenders.append(f"{number}: {line!r}")

        assert not offenders, f"inline comments make these patterns dead: {offenders}"


# ---------------------------------------------------------------------------
# N4 - SMTP must not block indefinitely
# ---------------------------------------------------------------------------
class TestSmtpTimeout:
    """Covers the unbounded wait on the mail server."""

    def test_membership_mail_passes_a_timeout(self, app, monkeypatch):
        """smtplib.SMTP must be called with a positive timeout."""
        import smtplib

        from utils import email_utils

        captured = {}

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                captured["timeout"] = timeout

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def starttls(self):
                pass

            def login(self, *args):
                pass

            def send_message(self, msg):
                pass

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

        with app.app_context():
            app.config.update(SMTP_SERVER="localhost", SMTP_PORT=25,
                              MAIL_SENDER_ADDRESS="noreply@example.com")
            email_utils.send_membership_email(
                "recipient@example.com",
                {"first_name": "A", "last_name": "B", "user_id": "a@example.com"},
            )

        assert captured.get("timeout"), "SMTP was called without a timeout"
        assert captured["timeout"] > 0


# ---------------------------------------------------------------------------
# N5 - unused dependencies must stay out
# ---------------------------------------------------------------------------
class TestDependencySurface:
    """Covers packages that were pinned but never imported."""

    def test_unused_packages_are_not_pinned(self):
        """
        SQLAlchemy and gevent are not used anywhere in the project.

        `requests` is deliberately not in this list: Authlib loads it at runtime.
        """
        from pathlib import Path

        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text(encoding="utf-8").lower()

        for package in ("sqlalchemy==", "flask-sqlalchemy==", "gevent=="):
            assert package not in requirements, f"{package} is back in requirements.txt"


# ---------------------------------------------------------------------------
# N6 - ProxyFix must be applied exactly once, with x_for
# ---------------------------------------------------------------------------
class TestProxyFix:
    """Covers the per-IP rate limit key."""

    def test_wsgi_module_does_not_wrap_again(self):
        """
        wsgi.py must not add a second ProxyFix.

        The duplicate omitted x_for, which is the shape of the bug that collapses every
        per-IP limit into one shared counter.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "wsgi.py"
        ).read_text(encoding="utf-8")

        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        assert "ProxyFix(" not in code

    def test_client_ip_comes_from_the_last_forwarded_entry(self, app):
        """
        The trusted proxy appends the true client IP last.

        Entries a client sets itself sit earlier in the list and must be ignored.
        """
        from flask import request

        @app.route("/__probe_remote_addr")
        def _probe():
            return request.remote_addr or ""

        client = app.test_client()
        response = client.get(
            "/__probe_remote_addr",
            headers={"X-Forwarded-For": "spoofed, 198.51.100.7, 203.0.113.9"},
            environ_base={"REMOTE_ADDR": "172.18.0.5"},
        )

        assert response.get_data(as_text=True) == "203.0.113.9"


# ---------------------------------------------------------------------------
# N3 - configurable replay protection
# ---------------------------------------------------------------------------
class TestReplayProtectionMode:
    """Covers the fail-open behaviour when Redis is unreachable."""

    def test_default_mode_allows_login_when_redis_is_down(self, app):
        """
        The default must stay permissive.

        A Redis outage would otherwise lock every member out of the application.
        """
        from blueprints.auth import email as email_module

        with app.test_request_context():
            app.config["EMAIL_LOGIN_REPLAY"] = "warn"
            app.config["RATE_LIMIT_STORAGE"] = "redis://127.0.0.1:1"  # nothing listens
            assert email_module._consume_login_token("some-token") is True

    def test_require_mode_refuses_login_when_redis_is_down(self, app):
        """Operators who prefer the strict trade-off must be able to select it."""
        from blueprints.auth import email as email_module

        with app.test_request_context():
            app.config["EMAIL_LOGIN_REPLAY"] = "require"
            app.config["RATE_LIMIT_STORAGE"] = "redis://127.0.0.1:1"
            assert email_module._consume_login_token("some-token") is False


# ---------------------------------------------------------------------------
# K1 - the rotation tool that makes the leaked key replaceable
# ---------------------------------------------------------------------------
class TestFernetKeyRotation:
    """Covers utils/scripts/rotate_fernet_key.py."""

    def _build_db(self, path):
        """Creates a members table that mixes TEXT and BLOB storage, as production does."""
        import sqlite3

        from cryptography.fernet import Fernet

        old_key = Fernet.generate_key()
        f = Fernet(old_key)
        conn = sqlite3.connect(path)
        conn.execute(
            """CREATE TABLE members (
                   email_hash TEXT PRIMARY KEY,
                   first_name_enc TEXT NOT NULL,
                   last_name_enc TEXT NOT NULL,
                   join_year BLOB,
                   role BLOB)"""
        )
        rows = [
            # the import path writes join_year/role as bytes ...
            ("aa" * 32, f.encrypt(b"Anna").decode(), f.encrypt(b"Alster").decode(),
             f.encrypt(b"2011"), f.encrypt(b"Vorstand")),
            # ... the editor path writes them as str ...
            ("bb" * 32, f.encrypt(b"Bo").decode(), f.encrypt(b"Berg").decode(),
             f.encrypt(b"2015").decode(), f.encrypt(b"").decode()),
            # ... and a row with NULLs.
            ("cc" * 32, f.encrypt(b"Cem").decode(), f.encrypt(b"Cetin").decode(),
             None, None),
        ]
        conn.executemany("INSERT INTO members VALUES (?,?,?,?,?)", rows)
        conn.commit()
        conn.close()
        return old_key

    def _run(self, db, old_key, new_key, *extra):
        import subprocess
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[1] / "utils" / "scripts" / "rotate_fernet_key.py"
        env = dict(os.environ,
                   FERNET_KEY_OLD=old_key.decode(),
                   FERNET_KEY_NEW=new_key.decode())
        return subprocess.run([sys.executable, str(script), "--db", str(db), *extra],
                              env=env, capture_output=True, text=True)

    def test_rotation_preserves_plaintext_and_storage_types(self, tmp_path):
        """
        Every value must read back identically under the new key, and each value must
        keep the TEXT/BLOB type it had - both readers in the app depend on that.
        """
        import sqlite3

        from cryptography.fernet import Fernet

        db = tmp_path / "members.db"
        old_key = self._build_db(db)
        new_key = Fernet.generate_key()

        def snapshot(key):
            f = Fernet(key)
            out = []
            conn = sqlite3.connect(db)
            for row in conn.execute(
                "SELECT email_hash, first_name_enc, last_name_enc, join_year, role "
                "FROM members ORDER BY email_hash"
            ):
                rec = [row[0]]
                for v in row[1:]:
                    if v is None:
                        rec.append((None, "NULL"))
                    else:
                        plain = f.decrypt(v.encode() if isinstance(v, str) else v)
                        rec.append((plain, type(v).__name__))
                out.append(tuple(rec))
            conn.close()
            return out

        before = snapshot(old_key)
        result = self._run(db, old_key, new_key, "--no-backup")
        assert result.returncode == 0, result.stderr
        after = snapshot(new_key)

        assert before == after, "plaintext or storage type changed during rotation"

    def test_old_key_no_longer_decrypts(self, tmp_path):
        """After rotation the leaked key must be worthless against the database."""
        import sqlite3

        from cryptography.fernet import Fernet, InvalidToken

        db = tmp_path / "members.db"
        old_key = self._build_db(db)
        new_key = Fernet.generate_key()
        assert self._run(db, old_key, new_key, "--no-backup").returncode == 0

        conn = sqlite3.connect(db)
        token = conn.execute("SELECT first_name_enc FROM members LIMIT 1").fetchone()[0]
        conn.close()

        with pytest.raises(InvalidToken):
            Fernet(old_key).decrypt(token.encode())

    def test_rerun_is_idempotent(self, tmp_path):
        """An interrupted run must be safe to repeat."""
        from cryptography.fernet import Fernet

        db = tmp_path / "members.db"
        old_key = self._build_db(db)
        new_key = Fernet.generate_key()

        assert self._run(db, old_key, new_key, "--no-backup").returncode == 0
        second = self._run(db, old_key, new_key, "--no-backup")
        assert second.returncode == 0
        assert "neu verschluesselt: 0" in second.stdout
        assert "schon neu:" in second.stdout

    def test_dry_run_changes_nothing(self, tmp_path):
        """--dry-run must leave the file byte-identical."""
        import hashlib

        from cryptography.fernet import Fernet

        db = tmp_path / "members.db"
        old_key = self._build_db(db)
        new_key = Fernet.generate_key()

        before = hashlib.sha256(db.read_bytes()).hexdigest()
        assert self._run(db, old_key, new_key, "--dry-run").returncode == 0
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before

    def test_wrong_old_key_aborts_without_writing(self, tmp_path):
        """
        A mistyped old key must abort before touching the database.

        Writing half a table under a key that cannot decrypt the rest would be
        unrecoverable without the backup.
        """
        import hashlib

        from cryptography.fernet import Fernet

        db = tmp_path / "members.db"
        self._build_db(db)
        wrong, new_key = Fernet.generate_key(), Fernet.generate_key()

        before = hashlib.sha256(db.read_bytes()).hexdigest()
        result = self._run(db, wrong, new_key, "--no-backup")

        assert result.returncode == 1
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before
        assert "nicht veraendert" in result.stderr


# ---------------------------------------------------------------------------
# Import order: the limiter must be usable before an application exists
# ---------------------------------------------------------------------------
class TestLimiterImportOrder:
    """
    Guards the module-level rate limiter against regressing to a None placeholder.

    The blueprint modules apply `@limiter.limit(...)` while they are being imported.
    As long as `core.extensions.limiter` started out as None and was replaced inside
    create_app, importing any blueprint before the app existed raised
    "'NoneType' object has no attribute 'limit'" — which is exactly what a script or a
    test does. It also meant a rebind left blueprints holding a stale instance.
    """

    def test_blueprints_import_without_an_application(self):
        """Importing every blueprint in a fresh interpreter must not raise."""
        import subprocess
        import sys
        from pathlib import Path

        code = (
            "import blueprints.auth.auth, blueprints.cards.cards, "
            "blueprints.main.main, blueprints.admin.admin; "
            "print('ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True,
            env=dict(os.environ, OPENPASS_DEV_INSECURE="1"),
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_limiter_is_never_none(self):
        """The exported name must be a real Limiter as soon as the module loads."""
        from flask_limiter import Limiter

        from core.extensions import limiter

        assert limiter is not None
        assert isinstance(limiter, Limiter)

    def test_create_app_does_not_rebind_the_limiter(self, app):
        """
        create_app must bind the shared instance, not replace it.

        A replacement would leave every already-imported blueprint decorated against
        the previous limiter, so its limits would silently stop being enforced.
        """
        from core import extensions as ext
        from blueprints.auth import email as email_module

        assert email_module.limiter is ext.limiter

    def test_configured_storage_reaches_the_limiter(self, app):
        """RATE_LIMIT_STORAGE must still select the backend after the refactor."""
        assert app.config["RATELIMIT_STORAGE_URI"] == app.config["RATE_LIMIT_STORAGE"]

    def test_limits_are_still_enforced(self, app):
        """
        A tightened limit must actually produce a 429.

        Without this the refactor could silently disarm rate limiting everywhere.
        """
        app.config["CSP_REPORT_RATE_LIMIT"] = "2 per hour"
        client = app.test_client()

        codes = [
            client.post("/csp-report",
                        json={"csp-report": {"document-uri": f"http://x{i}.test"}}).status_code
            for i in range(4)
        ]

        assert codes[:2] == [204, 204], codes
        assert 429 in codes[2:], codes


# ---------------------------------------------------------------------------
# Backups of the members database must never be committable
# ---------------------------------------------------------------------------
class TestBackupsAreIgnored:
    """
    Guards the ignore rules around member data.

    `instance/*.db` does not match the file the rotation script writes, which is
    `members.db.<timestamp>.bak` — a complete copy of the members database. Without an
    explicit rule it shows up as an untracked file and a `git add -A` would commit it.
    """

    def _ignored(self, path):
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        return subprocess.run(["git", "check-ignore", "-q", path],
                              cwd=str(root)).returncode == 0

    @pytest.mark.parametrize("path", [
        "instance/members.db",
        "instance/members.db.bak",
        "instance/members.db.20260821T162247Z.bak",
        "instance/backup.sqlite",
        "instance/members.db-wal",
        "instance/members.db-journal",
    ])
    def test_member_data_files_are_ignored(self, path):
        """No file that can hold member data may be offered for commit."""
        assert self._ignored(path), f"{path} would be committable"

    def test_seed_database_stays_versioned(self):
        """
        The dummy seed must remain tracked.

        The Dockerfile copies instance/admin_members.db into the image as the initial
        members.db, so ignoring it would break the build.
        """
        assert not self._ignored("instance/admin_members.db")

    def test_no_real_member_database_is_tracked(self):
        """The working database must not be in the index."""
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.run(["git", "ls-files", "instance/"],
                                 cwd=str(root), capture_output=True,
                                 text=True).stdout.split()
        assert "instance/members.db" not in tracked
        assert not [p for p in tracked if p.endswith(".bak")]
