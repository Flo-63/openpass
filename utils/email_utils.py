# email_utils.py
# Standard Library
import logging
import mimetypes
import re
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path

# Third-Party
from flask import current_app

main_logger = logging.getLogger("main_logger")


def send_membership_email(to_address, user_data):
    """
    Sends a membership confirmation email to the specified recipient with the provided user data.

    This function sends an email confirming the recipient's membership details using an HTML email
    format. It includes user-specific details such as the first name, last name, and club branding
    information. If any mandatory information is missing in the user data, or in case of email
    sending failure, the function will log the error and return False.

    Args:
        to_address (str): The recipient's email address.
        user_data (dict): A dictionary containing user-specific data. It must include the fields:
            'first_name' (str), 'last_name' (str), and 'user_id'.

    Returns:
        bool: True if the email was successfully sent, otherwise False.

    Raises:
        Exception: Catches any errors that occur during the SMTP connection, email content generation,
            or message sending and logs the exception.
    """
    main_logger.debug(f"Starte E-Mail-Versand an {to_address} für Nutzer: {user_data['first_name'], user_data['last_name']}")

    branding = current_app.config.get("BRANDING", {})
    verein = branding.get("club_name", "Dein Verein")
    kontakt = branding.get("contact_email", "kontakt@euerverein.de")
    farbe = branding.get("theme_color", "#1C91FF")

    for key in ['first_name', 'last_name', 'user_id']:
        if key not in user_data:
            main_logger.error(f"user_data fehlt erforderliches Feld: '{key}'")
            return False

    try:
        from datetime import datetime
        year_end = f"31.12.{datetime.utcnow().year}"

        # HTML-Inhalt
        html_content = f"""
        <!doctype html>
        <html lang="de">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="background-color:#f5f9ff; font-family: Calibri, sans-serif;">
        <table width="100%" bgcolor="#f5f9ff"><tr><td align="center">
        <table width="600" bgcolor="#ffffff" style="border-radius:8px; overflow:hidden; box-shadow:0 0 10px rgba(0,0,0,0.1); margin:10px;">
            <tr><td bgcolor="{farbe}" style="padding:20px; text-align:center;">
                <img src="cid:logo123" alt="{verein}" style="height:60px !important;">
            </td></tr>
            <tr><td style="padding:30px; color:#333;">
                <h2 style="color:{farbe};">Mitgliedsbestätigung</h2>
                <p>Sehr geehrte Damen und Herren,</p>
                <p>hiermit bestätigen wir, dass folgende Person als Mitglied beim {verein} registriert ist:</p>
                <p style="font-size:18px; font-weight:bold;">{user_data['first_name']} {user_data['last_name']}</p>
                <p>Diese Bestätigung gilt bis zum {year_end}.</p>
                <p>Mit sportlichen Grüßen<br><strong>{verein}</strong></p>
            </td></tr>
            <tr><td bgcolor="#eeeeee" style="padding:15px; font-size:0.8em; color:#777; text-align:center;">
                Diese Nachricht wurde automatisch generiert. Bitte nicht direkt antworten.
            </td></tr>
        </table></td></tr></table></body></html>
        """

        sender_name = current_app.config.get('MAIL_SENDER_NAME', verein)
        sender_address = current_app.config.get('MAIL_SENDER_ADDRESS', f'noreply@{kontakt.split("@")[-1]}')

        if '@' not in sender_address:
            main_logger.error(f"Ungültige Absenderadresse: {sender_address}")
            return False

        username, domain = sender_address.split("@")

        msg = EmailMessage()
        msg['Subject'] = f"Mitgliedsbestätigung – {verein}"
        msg['From'] = Address(display_name=sender_name, username=username, domain=domain)
        msg['To'] = to_address
        msg.set_content(f"Deine Mitgliedsbestätigung vom {verein} (nur Textversion).")
        msg.add_alternative(html_content, subtype='html')

        smtp_user = current_app.config["SMTP_USERNAME"]
        smtp_pass = current_app.config["SMTP_PASSWORD"]

        with smtplib.SMTP(current_app.config['SMTP_SERVER'], current_app.config['SMTP_PORT']) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            logo_path = Path(current_app.root_path) / "branding" / "logo.png"

            if logo_path.exists():
                with open(logo_path, "rb") as img:
                    img_data = img.read()
                maintype, subtype = mimetypes.guess_type(logo_path)[0].split('/')
                msg.get_payload()[1].add_related(img_data, maintype=maintype, subtype=subtype, cid="logo123")
            else:
                main_logger.warning(f"Logo-Datei 'logo.png' für E-Mail nicht gefunden.")

            server.send_message(msg)

        main_logger.info(f"E-Mail erfolgreich an {to_address[:3]}*** gesendet.")
        return True

    except Exception as e:
        main_logger.error(f"Fehler beim Versand an {to_address[:3]}***: {e}")
        return False

def send_login_email(to_address, first_name, last_name, login_link):
    """
    Sends a login email to a specified recipient containing a login link, custom branding,
    and details about the expiration of the link. The HTML email contains a personalized
    message including the user's first and last name, and the content is configured based
    on the application's branding settings.

    Parameters:
        to_address (str): The email address to which the login email is sent.
        first_name (str): The first name of the email recipient.
        last_name (str): The last name of the email recipient.
        login_link (str): The unique link for the user to log in.

    Returns:
        bool: True if the email was successfully sent, False otherwise.

    Raises:
        Exception: Any unhandled exceptions occurring during the email sending process.

    """
    main_logger.debug(f"Starte Login-Mailversand an {to_address[:3]}*** für {first_name} {last_name}")

    try:
        expiration_time = "15 Minuten"

        # Branding-Informationen laden
        branding = current_app.config.get("BRANDING", {})
        verein = branding.get("club_name", "Dein Verein")
        kurzname = branding.get("short_name", "DeinVerein")
        kontakt = branding.get("contact_email", "kontakt@euerverein.de")
        farbe = branding.get("theme_color", "#1C91FF")

        # HTML-Inhalt
        html_content = f"""
        <!doctype html>
        <html lang="de">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="background-color:#f5f9ff; font-family: Calibri, sans-serif;">
        <table width="100%" bgcolor="#f5f9ff"><tr><td align="center">
        <table width="600" bgcolor="#ffffff" style="border-radius:8px; overflow:hidden; box-shadow:0 0 10px rgba(0,0,0,0.1); margin:10px;">
            <tr><td bgcolor="{farbe}" style="padding:20px; text-align:center;">
                <img src="cid:logo123" alt="{verein}" style="height:60px !important;">
            </td></tr>
            <tr><td style="padding:30px; color:#333;">
                <h2 style="color:{farbe};">Dein Login-Link</h2>
                <p>Hallo {first_name},</p>
                <p>du kannst dich über folgenden Link direkt beim digitalen Mitgliedsausweis anmelden:</p>
                <p style="margin:20px 0; text-align:center;">
                    <a href="{login_link}" style="display:inline-block; background-color:{farbe}; color:#fff; padding:12px 20px; text-decoration:none; border-radius:5px;">
                        Jetzt einloggen
                    </a>
                </p>
                <p>Der Link ist ca. {expiration_time} gültig und kann nur einmal verwendet werden.</p>
                <p>Falls du diese Mail nicht selbst angefordert hast, melde Dich bitte bei uns unter <a href="mailto:{kontakt}">{kontakt}</a>.</p>

                <p>Mit sportlichen Grüßen<br><strong>{verein}</strong></p>
            </td></tr>
            <tr><td bgcolor="#eeeeee" style="padding:15px; font-size:0.8em; color:#777; text-align:center;">
                Diese Nachricht wurde automatisch generiert. Bitte nicht direkt antworten.
            </td></tr>
        </table></td></tr></table></body></html>
        """

        # Absenderinformationen
        sender_name = current_app.config.get('MAIL_SENDER_NAME', verein)
        sender_address = current_app.config.get('MAIL_SENDER_ADDRESS', f'noreply@{kontakt.split("@")[-1]}')

        if '@' not in sender_address:
            main_logger.error(f"Ungültige Absenderadresse: {sender_address}")
            return False

        username, domain = sender_address.split("@")

        msg = EmailMessage()
        msg['Subject'] = f"Dein Login-Link – {kurzname} Mitgliedsausweis"
        msg['From'] = Address(display_name=sender_name, username=username, domain=domain)
        msg['To'] = to_address
        msg.set_content("Dies ist dein Login-Link für den digitalen Mitgliedsausweis (Textversion).")
        msg.add_alternative(html_content, subtype='html')

        smtp_user = current_app.config["SMTP_USERNAME"]
        smtp_pass = current_app.config["SMTP_PASSWORD"]

        with smtplib.SMTP(current_app.config['SMTP_SERVER'], current_app.config['SMTP_PORT']) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            # Logo einbetten
            logo_path = Path(current_app.root_path) / "branding" / "logo.png"
            if logo_path.exists():
                with open(logo_path, "rb") as img:
                    img_data = img.read()
                mime_type = mimetypes.guess_type(logo_path)[0]
                if mime_type:
                    maintype, subtype = mime_type.split("/")
                    msg.get_payload()[1].add_related(img_data, maintype=maintype, subtype=subtype, cid="logo123")
                else:
                    main_logger.warning("Konnte MIME-Typ für Logo nicht bestimmen.")
            else:
                main_logger.warning("Logo-Datei für E-Mail nicht gefunden.")

            server.send_message(msg)

        main_logger.info(f"E-Mail erfolgreich an {to_address[:3]}*** gesendet.")
        return True

    except Exception as e:
        main_logger.error(f"Fehler beim Versand an {to_address[:3]}***: {e}")
        return False

def is_valid_email(email):
    """
    Check if the given email address is valid based on a regex pattern.

    This function determines whether an email address adheres to a common
    email structure using a regular expression. It checks if the email
    consists of a valid combination of characters, followed by an '@'
    symbol, a domain name, and a valid top-level domain.

    Parameters:
    email : str
        The email address to be validated.

    Returns:
    bool
        True if the email address is valid according to the regex
        pattern; otherwise, False.
    """
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None