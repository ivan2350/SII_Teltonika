#!/usr/bin/env python3
import sqlite3
import struct
import time

DB_PATH = "/var/run/modbus_client/modbus.db"

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

while True:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 🔥 Obtener último registro de p1
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
            # response_data viene como texto hexadecimal
            hex_string = row[0].replace(" ", "")
            raw_bytes = bytes.fromhex(hex_string)

            # Tomamos los primeros 4 bytes (32bit float 3412)
            b = raw_bytes[:4]

            # Byte order 3,4,1,2
            reordered = b[2:4] + b[0:2]

            presion = struct.unpack(">f", reordered)[0]

            print(f"[{ts()}] Presión: {presion:.2f} PSI")

        else:
            print("Sin datos aún")

        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(3)
