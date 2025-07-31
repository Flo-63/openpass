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
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


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

def register_photo_routes(bp):
    """
    Registers routes for handling photo uploads, deletions, and retrievals.

    Sets up secure photo management endpoints including upload, deletion,
    and retrieval with encryption and authorization controls.

    :param bp: Blueprint to register routes with
    :type bp: flask.Blueprint
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

        # Generate AES key from email
        key = hashlib.sha256(email.strip().lower().encode()).digest()
        iv = os.urandom(16)

        # cipher = AES.new(key, AES.MODE_CBC, iv)

        # encrypted_data = iv + cipher.encrypt(pad(file.read(), AES.block_size))

        # Padding (PKCS7, AES = 128 Bit Block)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(file.read()) + padder.finalize()

        # Verschlüsselung
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = iv + encryptor.update(padded_data) + encryptor.finalize()

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

        key = hashlib.sha256(email.strip().lower().encode()).digest()

        try:
            with open(path, "rb") as f:
                iv = f.read(16)
                ciphered = f.read()

            # cipher = AES.new(key, AES.MODE_CBC, iv)
            # decrypted = unpad(cipher.decrypt(ciphered), AES.block_size)

            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_padded = decryptor.update(ciphered) + decryptor.finalize()

            # Unpadding
            unpadder = padding.PKCS7(128).unpadder()
            decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

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