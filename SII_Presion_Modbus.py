#!/usr/bin/env python3
import time
import subprocess
import struct
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_SENSOR = 1

ALTURA_TANQUE = 30.0  # metros
NIVEL_ENCENDIDO = 6.0
NIVEL_APAGADO = 28.0

FACTOR_PSI_A_METROS = 0.70307

INTERVALO_NORMAL = 60
INTERVALO_ERROR = 5

RETARDO_REARRANQUE = 180
MAX_FALLOS_MODBUS = 10

DO_MOTOR = "ioman.gpio.dio0"

# ================= ESTADO =================

control_motor = False
tiempo_ultimo_apagado = None
fallos_modbus = 0

# ================= UTIL =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

def psi_a_metros(psi):
    return psi * FACTOR_PSI_A_METROS

def porcentaje_tanque(nivel_m):
    return (nivel_m / ALTURA_TANQUE) * 100

# ================= GPIO =================

def set_motor(valor, motivo=None):
    global control_motor, tiempo_ultimo_apagado

    if control_motor == valor:
        return

    cmd = f"ubus call {DO_MOTOR} update '{{\"value\":\"{1 if valor else 0}\"}}'"
    subprocess.run(cmd, shell=True, check=False)

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
        bytesize=8,
        stopbits=1,
        parity='N',
        timeout=2
    )

def leer_presion(client):
    # 🔥 Leemos exactamente 10 registros como indica el manual
    lectura = client.read_holding_registers(
        address=0,
        count=10,
        unit=ID_SENSOR
    )

    if lectura.isError():
        raise Exception("Error lectura presión")

    # Primer float = registros 0 y 1
    # Orden compatible con 3,4,1,2
    raw = struct.pack('>HH', lectura.registers[1], lectura.registers[0])
    presion = struct.unpack('>f', raw)[0]

    return presion

def reiniciar_modbus(client):
    print(f"[{ts()}] 🔄 Reiniciando RS485...")
    try:
        client.close()
    except:
        pass
    time.sleep(2)

    nuevo = crear_cliente()
    nuevo.connect()
    return nuevo

# ================= INICIO =================

print(f"[{ts()}] 🚀 Sistema Tanque por Presión iniciado")

client = crear_cliente()

if not client.connect():
    print("❌ No se pudo abrir puerto RS485")
    exit()

while True:
    try:
        ahora = time.time()

        presion_psi = leer_presion(client)
        fallos_modbus = 0

        if presion_psi < -1 or presion_psi > 60:
            raise Exception("Presión fuera de rango lógico")

        nivel_m = psi_a_metros(presion_psi)
        porcentaje = porcentaje_tanque(nivel_m)

        # ===== CONTROL =====

        if nivel_m >= NIVEL_APAGADO:
            set_motor(False, "Nivel máximo alcanzado")

        elif nivel_m <= NIVEL_ENCENDIDO:
            if not control_motor:
                if tiempo_ultimo_apagado is None or \
                   (ahora - tiempo_ultimo_apagado) >= RETARDO_REARRANQUE:
                    set_motor(True, "Nivel bajo")

        print(
            f"[{ts()}] "
            f"📟 {presion_psi:.2f} PSI | "
            f"📏 {nivel_m:.2f} m | "
            f"📊 {porcentaje:.1f}% | "
            f"🎛️ {'ON' if control_motor else 'OFF'}"
        )

        time.sleep(INTERVALO_NORMAL)

    except Exception as e:
        fallos_modbus += 1
        print(f"[{ts()}] ❌ ERROR ({fallos_modbus}/{MAX_FALLOS_MODBUS}) → {e}")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            set_motor(False, "Falla comunicación")
            client = reiniciar_modbus(client)
            fallos_modbus = 0

        time.sleep(INTERVALO_ERROR)
