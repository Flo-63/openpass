import sqlite3
import hashlib
from cryptography.fernet import Fernet

# 1) Pfad zur DB
DB_PATH = '../../instance/members.db'

# 2) Dein Fernet-Key (als Bytes-Literal)
FERNET_KEY = b'7dD2TnMPe-6DduoqTf3vgu1wejGvF_d4nNVPdoSroZk='

fernet = Fernet(FERNET_KEY)

# 3) Nutze die E-Mail, die du prüfen willst
email = 'florian@radtreffcampus.de'
email_hash = hashlib.sha256(email.encode()).hexdigest()

# 4) Verbindung öffnen und Datensatz holen
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT role, join_year FROM members WHERE email_hash = ?", (email_hash,))
row = cur.fetchone()
conn.close()

if not row:
    print("Kein Datensatz für", email)
else:
    role_raw, join_year_raw = row
    print("RAW role:     ", role_raw)
    print("RAW join_year:", join_year_raw)

    # 5) Entschlüsselung
    for name, token in (('role', role_raw), ('join_year', join_year_raw)):
        if token is None:
            print(f"{name!r} ist NULL")
            continue
        # token kann str (TEXT) oder bytes (BLOB) sein
        if isinstance(token, str):
            token = token.encode()
        try:
            plaintext = fernet.decrypt(token).decode()
            print(f"Decrypted {name}: {plaintext}")
        except Exception as e:
            print(f"Fehler beim Entschlüsseln von {name}: {e}")
