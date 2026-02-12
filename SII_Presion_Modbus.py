#!/usr/bin/env python3
import sqlite3

DB_PATH = "/var/run/modbus_client/modbus.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(modbus_data);")
columns = cursor.fetchall()

print("Columnas en modbus_data:")
for col in columns:
    print(col)

conn.close()
