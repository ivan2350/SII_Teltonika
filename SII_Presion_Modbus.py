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

        cursor.execute("""
            SELECT response_data
            FROM modbus_data
            WHERE request_name='p1'
            ORDER BY id DESC
            LIMIT 1;
        """)

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            raw = row[0].decode()        # convertir bytes a string
            value = raw.strip("[]")      # quitar corchetes
            presion = float(value)       # convertir a float

            print(f"[{ts()}] Presión: {presion:.2f} PSI")

        else:
            print("Sin datos")

        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(3)
