"""
===============================================================================
Project   : openpass
Module    : create_members_table.py
Created   : 16.10.2025
Author    : Florian
Purpose   : [Describe the purpose of this module briefly.]

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../../instance/members.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_hash TEXT UNIQUE NOT NULL,
    first_name_enc TEXT NOT NULL,
    last_name_enc TEXT NOT NULL,
    join_year INTEGER,
    role TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print(f"✅ Tabelle 'members' erfolgreich angelegt in {DB_PATH}")
