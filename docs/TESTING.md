## Inhaltsverzeichnis

  - [Unit Tests](#unit-tests)
    - [Test-Konfiguration](#test-konfiguration)
    - [Tests ausführen](#tests-ausführen)
- [Alle Tests ausführen](#alle-tests-ausführen)
- [Tests mit Coverage-Report](#tests-mit-coverage-report)
- [Spezifische Test-Datei ausführen](#spezifische-test-datei-ausführen)
- [Tests mit detaillierter Ausgabe](#tests-mit-detaillierter-ausgabe)
    - [Test-Struktur](#test-struktur)
    - [Test Coverage](#test-coverage)

## Unit Tests

Das Projekt verwendet pytest für Unit Tests. Die Tests befinden sich im Verzeichnis `tests/`.
 
### Test-Konfiguration

Das Projekt enthält zwei wichtige Konfigurationsdateien für Tests:

1. `pytest.ini` im Wurzelverzeichnis:
```
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*``` 
```
2. `pyproject.toml` (Test-relevante Ausschnitte):
```
[project] name = "rcb-ausweis" version = "0.9.0" 
requires-python = ">=3.9"
[project.optional-dependencies] dev = ["pytest"]
``` 
Die `pyproject.toml` definiert pytest als optionale Entwicklungsabhängigkeit. Um die Entwicklungsabhängigkeiten zu installieren:
```
bash pip install -e ".[dev]"
``` 

### Tests ausführen
```
# Alle Tests ausführen
pytest
# Tests mit Coverage-Report
pytest --cov=app tests/
# Spezifische Test-Datei ausführen
pytest tests/test_auth.py
# Tests mit detaillierter Ausgabe
pytest -v
``` 

### Test-Struktur
```
tests/ 
     ├── conftest.py # Test-Konfiguration und Fixtures 
     ├── test_auth.py # Authentifizierungs-Tests 
     ├── test_admin_functions.py # Admin-Funktionalitäts-Tests
     ├── test_email_functions.py # Email-Funktionalitäts-Tests
     ├── test_flask_app_fixtures.py # Flask-App Fixtures
     ├── test_member_card.py # Tests der Ausweis-Routen
     ├── test_oauth_routes.py # OAuth Tests
     ├── test_photo_functions.py # Tests der Funktionen zur Handhabung der Fotos 
     └── test_qr_card_auth.py # Tests zur Authentiserung und der QR Code-Seiten Funktionen 
``` 

### Test Coverage

Coverage-Reports werden im HTML-Format generiert:
```
bash pytest --cov=app --cov-report=html tests/
``` 
Der Report wird im Verzeichnis `htmlcov/` erstellt.
