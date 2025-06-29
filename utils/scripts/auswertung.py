#!/usr/bin/env python3
from collections import defaultdict

logfile = "/var/log/rcb-ausweis/main.log"

# Dictionaries: datum -> set of usernames bzw. count der QR-Calls
membership_users_per_day = defaultdict(set)
qr_count_per_day         = defaultdict(int)

with open(logfile, encoding="utf-8") as f:
    for line in f:
        # Datum ist das erste Feld (YYYY-MM-DD)
        parts = line.strip().split()
        if not parts:
            continue
        datum = parts[0]

        # 1) Membership-Card-Aufrufe (unique users)
        if "Mitgliedsausweis angezeigt für User:" in line \
        or "Membership card displayed for User:" in line:
            try:
                username = parts[parts.index("User:") + 1]
                membership_users_per_day[datum].add(username)
            except (ValueError, IndexError):
                # falls das Parsing fehlschlägt, überspringen
                pass

        # 2) QR-Code-Anzeigen (total count)
        if "QR card displayed for:" in line:
            qr_count_per_day[datum] += 1

# Ausgabe-Tabelle
print(f"{'Datum':<12} | {'Unique Member-User':>18} | {'QR-Code Displays':>16}")
print("-" * 54)

gesamt_users = set()
for datum in sorted(set(membership_users_per_day) | set(qr_count_per_day)):
    member_count = len(membership_users_per_day[datum])
    qr_count     = qr_count_per_day[datum]
    gesamt_users |= membership_users_per_day[datum]
    print(f"{datum:<12} | {member_count:18d} | {qr_count:16d}")

print("-" * 54)
print(f"{'Gesamt':<12} | {len(gesamt_users):18d} | {sum(qr_count_per_day.values()):16d}")
