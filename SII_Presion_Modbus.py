#!/usr/bin/env python3
import sqlite3
import time

DB_PATH = "/var/run/modbus_client/modbus.db"

while True:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, request_name, response_data
        FROM modbus_data
        ORDER BY id DESC
        LIMIT 5;
    """)

    rows = cursor.fetchall()
    conn.close()

    print("Últimos registros:")
    for r in rows:
        print(r)

    time.sleep(5)
