#!/usr/bin/env python3
import sqlite3
import time

DB_PATH = "/var/run/modbus_client/modbus.db"

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

while True:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 🔥 Obtener último valor guardado
        cursor.execute("SELECT tag_name, value FROM tags;")
        rows = cursor.fetchall()

        for row in rows:
            print(f"[{ts()}] {row[0]}: {row[1]}")

        conn.close()
        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(3)
