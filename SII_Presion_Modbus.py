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

ALTURA_TANQUE = 30.0        # metros
PSI_A_METROS = 0.703

INTERVALO = 5               # segundos lectura

TIMEOUT_SENSOR = 20         # segundos sin actualización
PRESION_MAXIMA = 60.0
PRESION_MINIMA = -1.0

MAX_FALLAS = 3

# ================= ESTADO =================

bomba_encendida = False
tiempo_ultimo_apagado = None

ultimo_id = None
ultimo_update = time.time()
contador_fallas = 0

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

# ================= LOOP =================

print(f"[{ts()}] 🚀 Sistema Tanque PRUEBA iniciado")

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

            # Detectar actualización real
            if ultimo_id != record_id:
                ultimo_id = record_id
                ultimo_update = time.time()

            raw = row[1].decode()
            value = raw.strip("[]")
            presion = float(value)

            # 🔥 Validar rango físico
            if presion > PRESION_MAXIMA or presion < PRESION_MINIMA:
                set_bomba(False, "Valor fuera de rango")
                continue

            # Conversión
            altura = presion * PSI_A_METROS
            porcentaje = (altura / ALTURA_TANQUE) * 100
            if porcentaje > 100:
                porcentaje = 100

            print(
                f"[{ts()}] "
                f"Presión: {presion:.2f} PSI | "
                f"Altura: {altura:.2f} m | "
                f"Llenado: {porcentaje:.1f}% | "
                f"Bomba: {'ON' if bomba_encendida else 'OFF'}"
            )

            # Limpieza automática
            cursor.execute("DELETE FROM modbus_data WHERE id < ?;", (record_id,))
            conn.commit()

            ahora = time.time()

            # ===== LÓGICA NORMAL =====

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

        # ===== PROTECCIÓN SENSOR =====

        if (time.time() - ultimo_update) > TIMEOUT_SENSOR:
            contador_fallas += 1
            print(f"[{ts()}] ⚠️ Falla sensor ({contador_fallas})")

            if contador_fallas >= MAX_FALLAS:
                set_bomba(False, "Falla comunicación Modbus")
        else:
            contador_fallas = 0

        time.sleep(INTERVALO)

    except Exception as e:
        print(f"[{ts()}] ERROR:", e)
        time.sleep(3)
