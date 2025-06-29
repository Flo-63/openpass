# Inhaltsverzeichnis

  - [Admin-Funktionen](#admin-funktionen)
     - [CSV-Import von Mitgliederdaten:](#csv-import-von-mitgliederdaten)
  - [Logging](#logging)

# Admin-Funktionen

Zum Upload der Mitgliederliste (CSV) gibt es einen eigenen, nur für Admins verfügbaren Endpunkt. Admins werden über
die Email Adresse identifiziert, mit der sie sich bei der App anmelden. In der Konfiguration gibt es eine 
Einstellung `admin_emails`, in der Komma-separiert die Email-Adressen der Admins definiert werden.

## CSV-Import von Mitgliederdaten:
- Format: `email,vorname,nachname,rolle`
- Zugriff über `/upload_members`
- Nur für Administratoren verfügbar => siehe oben stehende Bemerkung!
- keine Speicherung beim Upload, unmittelbare Verschlüsselung
- Email Adresse wird nur als Hash gespeichert.

# Logging
Logs werden in folgende Dateien geschrieben:
- Allgemeine Anwendungslogik `logs/main.log`
- Authentifizierung `logs/auth.log`
- Mitgliederimport `logs/import.log`
- CSP Reports `logs/csp.log`

Der Loglevel wird in der .env (gunicorn) bzw. deploy.yml festgelegt. 
Weiteres hierzu in der [KONFIGURATION.md](KONFIGURATION.md)