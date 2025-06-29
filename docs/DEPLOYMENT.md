# DEPLOYMENT.md

## Inhaltsverzeichnis

- [Deployment](#deployment)
- [Deployment mit Docker](#deployment-mit-docker)
- [Deployment mit Kamal](#deployment-mit-kamal)
  - [Windows-Setup mit WSL](#windows-setup-mit-wsl)
    - [Deploy Umgebung unter Windows vorbereiten](#deploy-umgebung-unter-windows-vorbereiten)
    - [Wichtige WSL-Befehle](#wichtige-wsl-befehle)
  - [Kamal-Konfiguration](#kamal-konfiguration)
    - [Wichtige Dateien](#wichtige-dateien)
    - [Wichtige Kamal-Befehle](#wichtige-kamal-befehle)
  - [Kamal Accessories](#kamal-accessories)
    - [Redis Accessory Konfiguration](#redis-accessory-konfiguration)
    - [Wichtige Accessory-Befehle](#wichtige-accessory-befehle)
- [Deployment mit Gunicorn](#deployment-mit-gunicorn)
    - [Konfiguration von gunicorn](#konfiguration-von-gunicorn)
    - [Apache virtual host mit reverse proxy](#apache-virtual-host-mit-reverse-proxy)
    - [systemd-service](#systemd-service)

## Deployment

Die App kann als WSGI Anwendung nativ z.B. auf Linux Servern mit gunicorn bereit gestellt werden. Ebenso kann die App
als Docker Container gebaut und zum Beispiel mittels kamal automatisiert deployed werden.

### Deployment mit Docker

1. Docker Image bauen:
Voraussetzung: docker ist installiert, auf Windows wird Docker Desktop benötigt.
```bash
docker build -t <IMAGE_NAME>
```
2. Container starten:
Nach der Vorbereitung der .env Datei (siehe entsprechendes Kapitel in [KONFIGURATION.md](KONFIGURATION.md) ) kann 
die App so gestartet werden.
```bash
docker run -d -p 5001:5001 --env-file .env -p 5001:5001 <IMAGE_NAME>
```

### Deployment mit Kamal

Um die App unter Windows mit Kamal deployen zu können benötigt man ein dafür konfiguriertes
WSL (Windows Subsystem für Linux):

#### Deploy Umgebung unter Windows vorbereiten:

1. Installation
```powershell
# PowerShell als Administrator
wsl --install -d Ubuntu
# Nach der Installation und Neustart:
# Ubuntu aus dem Start-Menü öffnen und Benutzer einrichten
```
2. Entwicklungsumgebung in WSL einrichten:
```bash
# System aktualisieren
sudo apt update && sudo apt upgrade

# Ruby installieren (wird für Kamal benötigt)
sudo apt install ruby-full

# Docker in WSL einrichten
# Docker Repository einrichten
curl -fsSL [https://download.docker.com/linux/ubuntu/gpg](https://download.docker.com/linux/ubuntu/gpg) | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] [https://download.docker.com/linux/ubuntu](https://download.docker.com/linux/ubuntu) $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list

# Docker installieren
sudo apt update sudo apt install docker-ce docker-ce-cli containerd.io

# Docker ohne sudo ermöglichen
sudo usermod -aG docker $USER

# Docker Service starten
sudo service docker start
```

3. Kamal installieren:
```bash
gem install kamal
```

4. SSH-Keys einrichten:
```bash
# SSH-Key generieren
ssh-keygen -t ed25519 -C "your_email@example.com"
# SSH-Key zum Server hinzufügen
ssh-copy-id username@your-server.com
```
#### Wichtige WSL-Befehle
```powershell
# WSL-Status prüfen
wsl --status
# Ubuntu-Terminal öffnen
wsl -d Ubuntu
# WSL neustarten
wsl --shutdown wsl -d Ubuntu
# WSL-Distribution als Standard setzen
wsl --set-default Ubuntu

```
### Kamal-Konfiguration:
```bash
# Initialisierung
kamal init
```
#### Wichtige Dateien
```
.kamal/
     ├── hooks/ #wird automatisch angelegt und muss nicht verändert werden.
     └──secrets-common # Umgebungsvariablen, die NICHT sichtbar in den container übergeben werden sollen.

config/
     ├── deploy.test.yml # Deploy Konfiguration für den Testserver
     └── deploy.yml  # Deploy Konfiguration für den Produktionsserver
```

#### Wichtige Kamal-Befehle:
```bash
# Deployment zum Testserver durchführen
kamal deploy -d test
# Deployment zum Produktionserver durchführen
kamal deploy
# Status überprüfen
kamal status
# Logs anzeigen
kamal logs
# Rollback durchführen
kamal rollback
# Neustart der Anwendung
kamal restart
```

### Kamal Accessories

Die Anwendung nutzt Redis als Accessory für Rate-Limiting und Session-Management.
Es werden keine Daten gespeichert, weswegen kein Volume angelegt werden muss.
Die Konfiguration erfolgt in der `deploy.yml` im Verzeichnis `/config`:

```yaml
# Redis Accessory Konfiguration
accessories:
  redis:
    image: redis:7.2-alpine
    host: <ANWENDUNG>.example.com
```

Wichtige Accessory-Befehle:
```bash
# Status der Accessories prüfen
kamal accessory status
# Accessories neustarten
kamal accessory restart redis
# Logs der Accessories anzeigen
kamal accessory logs redis
```
Wenn redis aktualisiert werden muss gilt folgendes Vorgehen:
a) Eintrag des neuen Images in der deploy.yml
b) Neustart von redis mit
```bash
kamal accessory reboot redis
```


## Deployment mit Gunicorn:
Für Produktions-und Testumgebungen bietet sich gunicorn server an. Damit können auch große Umgebungen sicher
und robust betrieben werden.

### Konfiguration von gunicorn
Für die Konfiguration von Gunicorn Server wird eine gunicorn_config.py bereitgestellt.

```python
# User and group settings for process execution

user = "www-data"  # User that runs Gunicorn processes
group = "www-data" # Group for the Gunicorn processes

# Network binding configuration

bind = "0.0.0.0:5001"  # Listen on all interfaces on port 5001
# bind = "unix:/run/gunicorn/rcb-ausweis.sock" # Listen on unix domain socket for reverse proxy via Apache

# Application loading
preload_app = True  # Load application code before forking workers

# Request handling configuration
timeout = 300  # Request timeout in seconds
workers = 1    # Number of worker processes (reduced to 1 for async operation)

# Worker class configuration
#worker_class = "gevent"  # Async worker (commented out)
worker_class = "sync"     # Synchronous worker currently in use

# Logging configuration
errorlog = "/var/log/<ANWENDUNG>/gunicorn.log"  # Error log file location
```

### Apache virtual host mit reverse proxy
Für apache server muss ein virtual host in folgender Weise angelegt werden:

```bash
# /etc/apache2/sites-available/<ANWENDUNG>.conf

<VirtualHost *:80>
    ServerName <your fqdn server name here>

    ErrorLog ${APACHE_LOG_DIR}/<ANWENDUNG>_error.log
    CustomLog ${APACHE_LOG_DIR}/<ANWENDUNG>_access.log combined

    Redirect permanent / https://<fqdn of your server>/
</VirtualHost>

<VirtualHost *:443>
    ServerName <your fqdn server name here>

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/<fqdn of your server>/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/<fqdn of your server>/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf

    ProxyPreserveHost On
    ProxyPassMatch ^/(.*)$ "unix:/run/gunicorn/openpass.sock|http://localhost/$1"
    ProxyPassReverse / http://localhost/

    ProxyPassReverseCookieDomain localhost <fqdn of your server>
    ProxyPassReverseCookiePath / /


    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Ssl on
    RequestHeader set X-Forwarded-Port "443"


    ErrorLog ${APACHE_LOG_DIR}/<ANWENDUNG>_error.log
    CustomLog ${APACHE_LOG_DIR}/<ANWENDUNG>_access.log combined
</VirtualHost>
```
Nach Anlegen der Definition muss die Seite aktiviert und apache neu geladen werden.
```bash
a2ensite <ANWENDUNG>.conf
service apache2 reload
```
*Hinweis: Hier werden Zertifikate von letsencrypt verwendet. Ohne Zertifikate funktioniert https nicht.*
*Zu Einrichtung und Benutzung von letsencrypt gibt es viele Quellen in youtube oder Foren.*

### systemd-Service
Um gunicorn als systemservice zu nutzen wird eine service-datei benötigt
```bash
# /etc/systemd/system/openpass.service
[Unit]
Description=<ANWENDUNG> Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/<ANWENDUNG>
Environment="PATH=/var/www/<ANWENDUNG>/venv/bin"
ExecStart=/var/www/<ANWENDUNG>/venv/bin/gunicorn --config /var/www/<ANWENDUNG>/gunicorn_config.py wsgi:app

[Install]
WantedBy=multi-user.target

```
Nach Anlegen der Datei muss diese im systemd geladen und der systemd neu gestartet werden.
```bash
# 1. Änderungen einlesen oder neue Unit registrieren
sudo systemctl daemon-reexec     # sicherer, aber selten nötig
sudo systemctl daemon-reload     # meist ausreichend und gebräuchlich

# 2. (Optional) Service aktivieren – startet bei jedem Boot
sudo systemctl enable <ANWENDUNG>.service

# 3. Service starten
sudo systemctl start <ANWENDUNG>.service

# 4. (Optional) Status prüfen
sudo systemctl status <ANWENDUNG>.service

# 5. (Optional) Logs anzeigen
journalctl -u <ANWENDUNG>.service -f
```
