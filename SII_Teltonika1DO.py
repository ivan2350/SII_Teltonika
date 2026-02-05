#!/usr/bin/env python3
import time
import json
import subprocess
from pymodbus.client import ModbusSerialClient

# ================== CONFIGURACIÓN ==================

MODBUS_PORT = "/dev/ttyHS0"     # RS485 Teltonika
MODBUS_BAUD = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120        # segundos
CICLO = 2                       # segundos

# ===================================================

# ----------- ESTADO DEL SISTEMA --------------------

bomba_encendida = False
ultimo_control = None           # "ON" / "OFF"
motivo_ultimo = "Inicio"
t_ultimo_control = 0

# --------------------------------------------------


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# ---------------- DO CONTROL -----------------------

def set_bomba(encender: bool):
    valor = "1" if encender else "0"
    subprocess.call([
        "ubus", "call",
        "ioman.gpio.dio0",
        "update",
        f'{{"value":"{valor}"}}'
    ])


# ---------------- DI MOTOR -------------------------

def leer_motor_DI():
    try:
        salida = subprocess.check_output([
            "ubus", "call",
            "ioman.gpio.dio0",
            "status"
        ]).decode()

        data = json.loads(salida)
        return data.get("value") == "1"

    except Exception as e:
        log(f"⚠ ERROR leyendo estado motor: {e}")
        return False


# ---------------- MODBUS ---------------------------

def conectar_modbus():
    client = ModbusSerialClient(
        port=MODBUS_PORT,
        baudrate=MODBUS_BAUD,
        timeout=1
    )
    return client if client.connect() else None


def leer_flotadores(client):
    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error Modbus lectura flotadores")

    return lectura.bits[0], lectura.bits[1]   # bajo, alto


# ================== MAIN ===========================

log("🚀 Sistema Pozo–Tanque iniciado")

client = None

try:
    while True:

        # ---------- MODBUS ----------
        if not client:
            client = conectar_modbus()
            if not client:
                log("❌ ERROR: No conecta Modbus")
                time.sleep(5)
                continue

        try:
            bajo, alto = leer_flotadores(client)
        except Exception as e:
            log(f"❌ {e}")
            client.close()
            client = None
            continue

        # ---------- MOTOR DI ----------
        motor_DI = leer_motor_DI()

        # ---------- ESTADO ----------
        log(
            f"Flotador BAJO: {bajo} | "
            f"Flotador ALTO: {alto} | "
            f"Motor: {'ENCENDIDO' if motor_DI else 'APAGADO'}"
        )

        # ---------- ALERTA MANUAL ----------
        if not bomba_encendida and motor_DI:
            log("⚠ ALERTA: Motor encendido en MANUAL (DO=OFF, DI=ON)")

        ahora = time.time()
        en_rearranque = (
            ultimo_control == "OFF" and
            (ahora - t_ultimo_control) < RETARDO_REARRANQUE
        )

        if en_rearranque:
            restante = int(RETARDO_REARRANQUE - (ahora - t_ultimo_control))
            log(f"⏳ Rearranque activo ({restante}s) – Motivo: {motivo_ultimo}")
            time.sleep(CICLO)
            continue

        # ========== LÓGICA DE CONTROL ==========

        # TANQUE LLENO
        if bajo and alto and bomba_encendida:
            set_bomba(False)
            bomba_encendida = False
            ultimo_control = "OFF"
            motivo_ultimo = "Tanque lleno"
            t_ultimo_control = ahora
            log("🛑 Bomba APAGADA – Tanque lleno")

        # INCONSISTENCIA
        elif alto and not bajo and bomba_encendida:
            set_bomba(False)
            bomba_encendida = False
            ultimo_control = "OFF"
            motivo_ultimo = "Inconsistencia flotadores"
            t_ultimo_control = ahora
            log("🛑 Bomba APAGADA – Inconsistencia flotadores")

        # TANQUE VACÍO
        elif not bajo and not alto and not bomba_encendida:
            set_bomba(True)
            bomba_encendida = True
            ultimo_control = "ON"
            motivo_ultimo = "Tanque vacío"
            t_ultimo_control = ahora
            log("▶️ Bomba ENCENDIDA – Tanque vacío")

        time.sleep(CICLO)

except KeyboardInterrupt:
    log("🛑 Programa detenido manualmente")

finally:
    if client:
        client.close()
