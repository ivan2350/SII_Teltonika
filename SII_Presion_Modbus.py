#!/usr/bin/env python3
import sqlite3

DB_PATH = "/var/run/modbus_client/modbus.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tablas encontradas:")
for t in tables:
    print(t[0])

conn.close()
