## Installation

1. Voraussetzungen

- Python 3.11+
- Docker (optional)
- Redis (für Rate Limiting)

2. Projektstruktur

```
<ANWENDUNG>/
├── blueprints/
│             ├── admin/ # Admin-Interface
│             ├── auth/ # Authentifizierung
│             └── cards/ # Mitgliedsausweise
├── core/   # Kernfunktionalität
│       ├── extensions.py # Flask Erweiterungen
│       └── token_manager.py # Token-Verwaltung
├── static/ # Statische Dateien
│         ├── css/ # Stylesheets
│         ├── js/ # JavaScript
│         └── images/ # Bilder & Icons
├── templates/ # Jinja2 Templates
├── utils/ # Hilfsfunktionen
├── instance/ # Datenbank
│           └── members.db # SQLite Datenbank
├── uploads/
│          └── photos /# Für verschlüsselte Fotos
│                     └── *.enc # Verschlüsselte Fotos
├── logs/ # Logdateien
├── .env # Umgebungsvariablen
├── .gitignore # Git-Ignore Datei
├── Dockerfile # Docker Build-Datei
├── requirements.txt # Produktionsabhängigkeiten
├── requirements-dev.txt # Entwicklungsabhängigkeiten
├── wsgi.py # WSGI Anwendungs-Entry-Point
└── gunicorn_config.py # Gunicorn-Konfiguration
```

3. Repository klonen:

```bash
git clone [RCB-Ausweis](https://github.com/Flo-63/RCB-Ausweis.git)
```

4. Virtuelle Umgebung erstellen und aktivieren:

```bash
# Virtuelle Umgebung erstellen
python -m venv venv
# Unter Linux/MacOS aktivieren:
source venv/bin/activate
# Unter Windows aktivieren:
.\venv\Scripts\activate
```

5. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

6. Umgebungsvariablen konfigurieren:
Die App wird über Umgebungsvariablen gesteuert. Diese werden in der Entwicklungsumgebung oder bei einem Deployment ohne
Kamal / Docker aus der Datei .env gelesen.

```ini
# .env.example

##############################################
# Sicherheit & Kernkonfiguration
##############################################

# Geheimer Schlüssel für die Flask-App (z.B. zur Signierung von Sessions)
SECRET_KEY=change-this-secret-key

# Fernet-Schlüssel für verschlüsselte Inhalte (Base64, z.B. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
FERNET_KEY=your-generated-fernet-key

# Schlüssel für AES-Foto-Verschlüsselung (hexadezimal, z.B. `openssl rand -hex 32`)
PHOTO_ENCRYPTION_KEY=your-64-char-hex-key

# Token-Gültigkeitsdauer in Sekunden (Standard: 3600 = 1 Stunde)
TOKEN_MAX_AGE_SECONDS=3600

##############################################
# Server & URL-Konfiguration
##############################################

# SERVER_NAME für Flask (z.B. ausweis.verein.de)
SERVER_NAME=ausweis.example.org

# Für URL-Generierung (http oder https)
PREFERRED_URL_SCHEME=https

##############################################
# OAuth (z.B. Rocket.Chat oder Authentik)
##############################################

# Name des OAuth-Anbieters (nur zur Anzeige)
OAUTH_NAME=Rocket.Chat

# OpenID-Discovery-URL (z.B. https://chat.example.org/.well-known/openid-configuration)
OAUTH_DISCOVERY_URL=

# OAuth Client-ID & Secret (aus dem Backend der OAuth-App)
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=

# Alternativ: manuelle OAuth-Endpunkte (falls kein Discovery verwendet wird)
OAUTH_AUTHORIZE_URL=https://chat.example.org/oauth/authorize
OAUTH_TOKEN_URL=https://chat.example.org/oauth/token
OAUTH_API_URL=https://chat.example.org/api/v1/
OAUTH_USERINFO_URL=https://chat.example.org/oauth/userinfo

##############################################
# E-Mail-Versand (SMTP)
##############################################

SMTP_SERVER=smtp.example.org
SMTP_PORT=587
SMTP_USERNAME=username@example.org
SMTP_PASSWORD=secure-password

# Absenderinformationen für versendete Mails
MAIL_SENDER_NAME=Vereins-Ausweis
MAIL_SENDER_ADDRESS=ausweis@example.org

##############################################
# Sicherheit & Rate Limiting
##############################################

# Redis URL für Ratelimit-Speicher
RATE_LIMIT_STORAGE=redis://localhost:6379

# Login-Versuche per E-Mail beschränken
EMAIL_LOGIN_RATE_LIMIT=5 per hour

# CSP-Report-Endpunkt (optional)
CSP_REPORT_URI=https://ausweis.example.org/csp-report

##############################################
# Mitgliederliste
##############################################

# Pfad zur Mitgliederliste
MEMBER_DB=members.db

# Liste der Admin-Emails, durch Komma getrennt (muss mit Login-Adresse übereinstimmen)
ADMIN_EMAILS=admin1@example.org,admin2@example.org

# CSV-Trennzeichen für Uploads (z. B. ; oder ,)
CSV_DELIMITER=;

##############################################
# Logging
##############################################

# Haupt-Logverzeichnis
LOG_PATH=logs

# Optional anderes Logverzeichnis für Serverlogs
SERVER_LOG_PATH=

# Loglevels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
CONSOLE_LOG_LEVEL=INFO
IMPORT_LOG_LEVEL=INFO
AUTH_LOG_LEVEL=INFO
TASK_LOG_LEVEL=INFO
CSP_LOG_LEVEL=WARNING
```

# Eigene .env Datei erstellen
```bash
cp .env.example .env
```
# Mindestens folgende Variablen in .env setzen:
```ini
SECRET_KEY=<your-secure-secret-key>
PHOTO_ENCRYPTION_KEY=<your-photo-encryption-key>
FERNET_KEY=<your-fernet-key>
```

7. Entwicklungsserver starten:

Die App wurde mit JetBrains PyCharm entwickelt. Diese IDE bringt auch einen Entwicklungsserver mit.
Falls keine IDE zur Verfügung steht, kann z.B. unter Linux ein temporärer Server gestartet werden:

```bash
# Standardkonfiguration
flask run --port 5001
# Mit Debug-Modus
flask run --port 5001 --debug
# Mit spezifischer Host-Bindung
flask run --port 5001 --host 0.0.0.0
```
