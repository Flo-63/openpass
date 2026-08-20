"""
===============================================================================
Project   : openpass
Module    : blueprints/cards/photo.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides photo-related functionality for the OpenPass application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""


# Standard Library
import hashlib
import logging
import os
from io import BytesIO
from pathlib import Path

# Third-Party
# from Crypto.Cipher import AES
# from Crypto.Util.Padding import pad, unpad

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from PIL import Image, UnidentifiedImageError


from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for
)
from flask_login import (
    current_user,
    login_required
)

# Local
from core.token_manager import (
    decode_token,
    generate_token
)

main_logger = logging.getLogger("main_logger")

UPLOAD_DIR = lambda: current_app.config["PHOTO_UPLOAD_FOLDER"]

# Magic prefix marking a photo encrypted with AES-GCM under PHOTO_ENCRYPTION_KEY.
# Files without it were written by the earlier scheme (AES-CBC under a key derived from
# the member's email address) and are still readable, so existing uploads survive.
PHOTO_MAGIC = b"OPG1"
PHOTO_NONCE_BYTES = 12

# Largest edge length kept when re-encoding an uploaded photo.
MAX_PHOTO_EDGE = 1600


def _photo_cipher_key() -> bytes:
    """
    Returns the configured symmetric key for photo encryption.

    Raises:
        RuntimeError: If `PHOTO_ENCRYPTION_KEY` is not configured.
    """
    key = current_app.config.get("PHOTO_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("PHOTO_ENCRYPTION_KEY is not configured.")
    return key


def _encrypt_photo(plaintext: bytes, photo_id: str) -> bytes:
    """
    Encrypts photo bytes with AES-GCM under the application's photo key.

    The photo id is bound in as additional authenticated data, so a file cannot be
    swapped for another member's photo without detection.

    Args:
        plaintext (bytes): Raw (already normalised) image bytes.
        photo_id (str): Identifier the photo is stored under.

    Returns:
        bytes: Magic prefix, nonce and ciphertext, ready to be written to disk.
    """
    nonce = os.urandom(PHOTO_NONCE_BYTES)
    ciphertext = AESGCM(_photo_cipher_key()).encrypt(nonce, plaintext, photo_id.encode())
    return PHOTO_MAGIC + nonce + ciphertext


def _decrypt_photo(blob: bytes, photo_id: str, email: str) -> bytes:
    """
    Decrypts a stored photo, transparently handling the legacy format.

    Args:
        blob (bytes): Full file contents.
        photo_id (str): Identifier the photo is stored under (AAD for the current format).
        email (str): Member email, used only to derive the legacy key.

    Returns:
        bytes: Decrypted image bytes.
    """
    if blob.startswith(PHOTO_MAGIC):
        nonce = blob[len(PHOTO_MAGIC):len(PHOTO_MAGIC) + PHOTO_NONCE_BYTES]
        ciphertext = blob[len(PHOTO_MAGIC) + PHOTO_NONCE_BYTES:]
        return AESGCM(_photo_cipher_key()).decrypt(nonce, ciphertext, photo_id.encode())

    # Legacy format: AES-CBC with a key derived from the email address.
    main_logger.info(f"Reading legacy-encrypted photo (ID: {photo_id}); re-upload to migrate.")
    legacy_key = hashlib.sha256(email.strip().lower().encode()).digest()
    iv, ciphertext = blob[:16], blob[16:]
    cipher = Cipher(algorithms.AES(legacy_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _normalise_image(raw: bytes) -> bytes:
    """
    Validates that the upload really is an image and re-encodes it as JPEG.

    Re-encoding through Pillow rejects anything that is not a decodable image, strips
    embedded metadata (including EXIF GPS coordinates) and bounds the stored resolution.

    Args:
        raw (bytes): Uploaded bytes.

    Returns:
        bytes: Normalised JPEG bytes.

    Raises:
        ValueError: If the upload cannot be decoded as an image.
    """
    try:
        with Image.open(BytesIO(raw)) as probe:
            probe.verify()  # structural check; consumes the file object
        with Image.open(BytesIO(raw)) as img:
            img = img.convert("RGB")
            img.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE))
            out = BytesIO()
            img.save(out, format="JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Uploaded file is not a readable image.") from exc

    return out.getvalue()

def register_photo_routes(bp):
    """
    Registers photo-related routes for a Flask Blueprint.

    Includes routes for uploading, handling, deleting, and retrieving encrypted
    photo files for authenticated users.

    Attributes:
        bp (flask.Blueprint): The blueprint to which routes are registered.

    Routes:
        - "/handle_photo_upload": POST route to process photo uploads with encryption.
        - "/upload_photo": GET route to render the photo upload page.
        - "/delete_photo": POST route to handle deletion of user's encrypted photo.
        - "/photo/<photo_id>": GET route to retrieve and decrypt a user's photo.
    """
    @bp.route("/handle_photo_upload", methods=["POST"])
    def handle_photo_upload():
        """
        Processes photo upload with encryption.

        Handles file upload, encrypts using email-derived key, and stores securely.
        Generates unique filename from email hash.

        :return: Redirect to QR card page
        :rtype: werkzeug.wrappers.Response
        :raises HTTPException: On missing email or upload failure
        """
        file = request.files.get("photo")
        if not file:
            flash("No file selected.", "error")
            return redirect(url_for("cards.upload_photo"))

        # Determine photo_id (filename) from email
        userinfo = session.get("oauth_userinfo") or session.get("email_userinfo")
        email = userinfo.get("email") if userinfo else None

        if not email:
            main_logger.error(f"handle_photo_upload: No email in session (IP: {request.remote_addr})")
            abort(400, description="No email address found in your user profile.")

        photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]

        # Validate and normalise before anything is written to disk.
        try:
            image_data = _normalise_image(file.read())
        except ValueError:
            main_logger.warning(
                f"Rejected non-image upload for user: {email[:3]}*** (IP: {request.remote_addr})"
            )
            flash("Please upload a valid image file (JPEG or PNG).", "error")
            return redirect(url_for("cards.upload_photo"))

        encrypted_data = _encrypt_photo(image_data, photo_id)

        # Save file
        file_path = os.path.join(UPLOAD_DIR(), f"{photo_id}.enc")
        with open(file_path, "wb") as f:
            f.write(encrypted_data)

        flash("Your photo has been uploaded successfully.", "success")
        main_logger.info(
            f"Photo successfully uploaded for user: {email[:3]}*** (ID: {photo_id}, IP: {request.remote_addr})")
        return redirect(url_for("cards.qr_card"))

    @bp.route("/upload_photo")
    def upload_photo():
        """
        Renders photo upload page.

        Verifies user and prepares upload form with secure token.

        :return: Rendered upload page
        :rtype: flask.Response
        :raises Abort: If user email not found
        """
        userinfo = session.get("oauth_userinfo") or session.get("email_userinfo")
        email = userinfo.get("email") if userinfo else None

        if not email:
            main_logger.error(f"upload_photo: No email in session (IP: {request.remote_addr})")
            abort(400, description="No email address found in your user profile.")
            
        photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
        photo_path = Path(UPLOAD_DIR()) / f"{photo_id}.enc"
        # Token includes photo_id for verification in get_photo
        photo_token = generate_token({
           "user_id": email,
           "photo_id": photo_id
        })
        return render_template("upload_photo.html",
                             photo_id=photo_id,
                             photo_exists=photo_path.exists(),
                             photo_token=photo_token)

    @bp.route("/delete_photo", methods=["POST"])
    def delete_photo():
        """
        Handles photo deletion.

        Removes user's encrypted photo if it exists.

        :return: Redirect to upload page
        :rtype: werkzeug.wrappers.Response
        :raises HTTPException: If user not found
        """
        userinfo = session.get("oauth_userinfo") or session.get("email_userinfo")
        email = userinfo.get("email") if userinfo else None
        if not email:
            main_logger.error("User has no email address.")
            abort(400, description="No email address found in your user profile.")
            
        photo_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
        photo_path = Path(UPLOAD_DIR()) / f"{photo_id}.enc"

        if photo_path.exists():
            photo_path.unlink()
            main_logger.info(f"Photo deleted for user: {email[:3]}*** (ID: {photo_id}, IP: {request.remote_addr})")
            flash("Your photo has been deleted.", "info")
        else:
            main_logger.warning(
                f"No photo to delete for user: {email[:3]}*** (ID: {photo_id}, IP: {request.remote_addr})")
            flash("No photo found.", "warning")

        return redirect(url_for("cards.upload_photo"))

    @bp.route("/photo/<photo_id>", endpoint="get_photo")
    def get_photo(photo_id):
        """
        Retrieves and decrypts user photo.

        Verifies access token, locates encrypted file, and returns decrypted image.

        :param photo_id: Unique photo identifier
        :type photo_id: str
        :return: Decrypted photo file
        :rtype: werkzeug.wrappers.Response
        :raises HTTPException: On invalid token or missing file
        """
        token = request.args.get("token")
        user_data = decode_token(token)

        if not user_data or user_data.get("photo_id") != photo_id:
            main_logger.warning(
                f"get_photo: Invalid/expired token for Photo-ID {photo_id} from IP: {request.remote_addr}")
            abort(403)

        email = user_data["user_id"]
        path = os.path.join(current_app.config["PHOTO_UPLOAD_FOLDER"], f"{photo_id}.enc")
        if not os.path.isfile(path):
            main_logger.warning(
                f"get_photo: Photo not found (ID: {photo_id}) for user: {email[:3]}*** IP: {request.remote_addr}")
            abort(404)

        try:
            with open(path, "rb") as f:
                blob = f.read()

            decrypted = _decrypt_photo(blob, photo_id, email)

            return send_file(
                BytesIO(decrypted),
                mimetype="image/jpeg",
                as_attachment=False,
                download_name="photo.jpg"
            )
        except Exception as e:
            main_logger.error(
                f"get_photo: Decryption failed for user: {email[:3]}*** (ID: {photo_id}, IP: {request.remote_addr}) - Error: {e}")
            abort(500)