#!/usr/bin/env python3
import time
import subprocess
import struct
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_SENSOR = 1  # Cambiar si es distinto

INTERVALO_NORMAL = 60
INTERVALO_ERROR = 5
INTERVALO_DIAG = 5

RETARDO_REARRANQUE = 180
MAX_FALLOS_MODBUS = 30

TIEMPO_DIAGNOSTICO = 3600
POLL_BOTON = 1

ALTURA_TANQUE = 30.0
NIVEL_ENCENDIDO = 3.0
NIVEL_APAGADO = 30.0

FACTOR_PSI_A_METROS = 0.703

DO_MOTOR = "ioman.gpio.dio0"
DI_DIAG = "ioman.gpio.dio1"

# ================= ESTADO =================

control_motor = False
tiempo_ultimo_apagado = None
fallos_modbus = 0
modo_diag_activo = False
tiempo_diag_inicio = None
estado_diag_anterior = False
intervalo_actual = INTERVALO_NORMAL

# ================= UTIL =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

# ================= GPIO =================

def set_motor(valor, motivo=None):
    global control_motor, tiempo_ultimo_apagado

    if control_motor == valor:
        return

    cmd = f"ubus call {DO_MOTOR} update '{{\"value\":\"{1 if valor else 0}\"}}'"
    subprocess.run(cmd, shell=True)

    control_motor = valor

    if not valor:
        tiempo_ultimo_apagado = time.time()
        print(f"[{ts()}] 🔴 BOMBA APAGADA → {motivo}")
    else:
        print(f"[{ts()}] 🟢 BOMBA ENCENDIDA → {motivo}")

# ================= MODBUS =================

def crear_cliente():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        timeout=1
    )

def leer_presion(client):
    lectura = client.read_holding_registers(
        address=0,
        count=2,
        unit=ID_SENSOR
    )

    if lectura.isError():
        raise Exception("Error lectura presión")

    raw = struct.pack('>HH', lectura.registers[0], lectura.registers[1])
    presion = struct.unpack('>f', raw)[0]

    return presion

# ================= INICIO =================

print(f"[{ts()}] 🚀 Sistema control por presión iniciado")
client = crear_cliente()

while True:
    try:
        ahora = time.time()

        presion_psi = leer_presion(client)

        # Validación básica
        if presion_psi < -1 or presion_psi > 60:
            raise Exception("Presión fuera de rango")

        nivel_m = presion_psi * FACTOR_PSI_A_METROS
        porcentaje = (nivel_m / ALTURA_TANQUE) * 100

        # ===== LÓGICA =====

        if nivel_m <= NIVEL_ENCENDIDO:
            if not control_motor:
                if tiempo_ultimo_apagado is None or \
                   (ahora - tiempo_ultimo_apagado) >= RETARDO_REARRANQUE:
                    set_motor(True, "Nivel bajo")
        elif nivel_m >= NIVEL_APAGADO:
            set_motor(False, "Tanque lleno")

        print(
            f"[{ts()}] "
            f"Presión: {presion_psi:.2f} PSI | "
            f"Nivel: {nivel_m:.2f} m | "
            f"{porcentaje:.1f}% | "
            f"Bomba: {'ON' if control_motor else 'OFF'}"
        )

        time.sleep(INTERVALO_NORMAL)

    except Exception as e:
        fallos_modbus += 1
        print(f"[{ts()}] ❌ ERROR ({fallos_modbus}/{MAX_FALLOS_MODBUS}) - {e}")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            set_motor(False, "Falla comunicación")
            client.close()
            time.sleep(2)
            client = crear_cliente()
            fallos_modbus = 0

        time.sleep(INTERVALO_ERROR)
