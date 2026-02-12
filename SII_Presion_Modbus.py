#!/usr/bin/env python3
import sqlite3
import time
import subprocess

# ================= CONFIG =================

DB_PATH = "/var/run/modbus_client/modbus.db"

DO_MOTOR = "ioman.gpio.dio0"

PRESION_ARRANQUE = 10.0     # PSI
PRESION_PARO = 42.0         # PSI
RETARDO_REARRANQUE = 180    # segundos

INTERVALO = 5               # segundos lectura

# ================= ESTADO =================

bomba_encendida = False
tiempo_ultimo_apagado = None

# ================= UTIL =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

def set_bomba(valor, motivo=""):
    global bomba_encendida, tiempo_ultimo_apagado

    if bomba_encendida == valor:
        return

    cmd = f"ubus call {DO_MOTOR} update '{{\"value\":\"{1 if valor else 0}\"}}'"
    subprocess.run(cmd, shell=True)

    bomba_encendida = valor

    if not valor:
        tiempo_ultimo_apagado = time.time()
        print(f"[{ts()}] 🔴 BOMBA APAGADA → {motivo}")
    else:
        print(f"[{ts()}] 🟢 BOMBA ENCENDIDA → {motivo}")

# ================= LOOP PRINCIPAL =================

print(f"[{ts()}] 🚀 Sistema Tanque por Presión iniciado")

while True:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, response_data
            FROM modbus_data
            WHERE request_name='p1'
            ORDER BY id DESC
            LIMIT 1;
        """)

        row = cursor.fetchone()

        if row and row[1]:

            record_id = row[0]
            raw = row[1].decode()
            value = raw.strip("[]")
            presion = float(value)

            print(f"[{ts()}] Presión actual: {presion:.2f} PSI")

            # 🔥 LIMPIEZA AUTOMÁTICA
            cursor.execute("DELETE FROM modbus_data WHERE id < ?;", (record_id,))
            conn.commit()

            ahora = time.time()

            # ================= LÓGICA =================

            if presion >= PRESION_PARO:
                set_bomba(False, "Tanque lleno")

            elif presion <= PRESION_ARRANQUE:
                if not bomba_encendida:
                    if tiempo_ultimo_apagado is None or \
                       (ahora - tiempo_ultimo_apagado) >= RETARDO_REARRANQUE:
                        set_bomba(True, "Tanque bajo")
                    else:
                        restante = int(
                            RETARDO_REARRANQUE - (ahora - tiempo_ultimo_apagado)
                        )
                        print(f"[{ts()}] ⏳ Esperando rearranque ({restante}s)")

        conn.close()
        time.sleep(INTERVALO)

    except Exception as e:
        print(f"[{ts()}] ERROR:", e)
        time.sleep(3)
