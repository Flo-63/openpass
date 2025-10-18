"""
===============================================================================
Project   : openpass
Module    : blueprints/cards/helpers.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides helper functions for managing membership cards.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


import hashlib
import os
import logging
import sqlite3

# Third-Party
from flask import session, current_app

# Local
from core.extensions import fernet

# Gemeinsamer Logger (wird auch in cards.py benutzt)
main_logger = logging.getLogger("main_logger")


def _get_session_userinfo():
    """
    Retrieves user information from the session.

    This function checks the session for user information stored under the keys
    "oauth_userinfo" or "email_userinfo". It returns the value associated with
    the first found key or None if neither key is present.

    Returns:
        dict or None: The user information retrieved from the session, or None if
        no such information is available.
    """
    return session.get("oauth_userinfo") or session.get("email_userinfo")


def _normalize_name(userinfo):
    """
    Normalizes the user's name by extracting and synthesizing first and last name
    from the provided user information dictionary. If first and last names are
    not explicitly provided, attempts to derive them from the 'name' field.

    Parameters:
        userinfo (dict): Dictionary containing user information which can include
                         keys like 'first_name', 'last_name', and 'name'.

    Returns:
        tuple: A tuple containing two strings, the normalized first and last names.
    """
    first = userinfo.get("first_name") or ""
    last = userinfo.get("last_name") or ""
    if not first or not last:
        parts = userinfo.get("name", "").strip().split()
        first = parts[0] if parts else "Unknown"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def _fetch_role_and_year(email):
    """
    Fetches the role and join year of a member from the database based on the provided email.

    The function computes a hash of the provided email and queries the members database to
    retrieve the associated role and join year. The retrieved data is decrypted if necessary
    before being returned. If database access or decryption fails, default values are returned.

    Parameters:
        email (str): The email address of the member.

    Returns:
        tuple: A tuple containing two elements:
            - role (str): The decrypted role of the member, or an empty string if unavailable.
            - join_year (Optional[str]): The decrypted join year of the member, or None if unavailable.
    """
    role = ""
    join_year = None
    try:
        db_path = os.path.join(current_app.instance_path, current_app.config["MEMBER_DB"])
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        with sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT role, join_year FROM members WHERE email_hash=?", (email_hash,)
            ).fetchone()
            if row:
                if row[0]:
                    try:
                        role = fernet.decrypt(row[0]).decode()
                    except Exception:
                        role = ""
                if row[1]:
                    try:
                        token_bytes = row[1].encode() if isinstance(row[1], str) else row[1]
                        join_year = fernet.decrypt(token_bytes).decode()
                    except Exception:
                        join_year = None
    except Exception as err:
        main_logger.error(f"DB access failed for {email}: {err}")
    return role, join_year


def build_user_data_from_session():
    """
    Builds user data from the session information.

    Fetches and processes user information from the session data to construct a
    dictionary containing user-specific information such as user ID, first name,
    last name, role, photo ID, and join year.

    Returns:
        dict | None: A dictionary containing user data if session data exists and
        is valid. Returns None if the session data or required information is
        unavailable.

    Raises:
        No explicit exceptions are raised, but errors might occur if session data
        is improperly structured or processing functions fail.
    """
    userinfo = _get_session_userinfo()
    if not userinfo:
        return None

    email = userinfo.get("email")
    if not email:
        return None

    first_name, last_name = _normalize_name(userinfo)
    role, join_year = _fetch_role_and_year(email)
    photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]

    return {
        "user_id": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "photo_id": photo_id,
        "join_year": join_year,
    }