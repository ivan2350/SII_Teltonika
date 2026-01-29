#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

# Retardo de arranque en segundos
RETARDO_ARRANQUE = 10

# Intervalo de ciclo principal
CICLO = 2

# Modbus RS485
MODBUS_PORT = "/dev/ttyRS485"
MODBUS_BAUDRATE = 9600
MODBUS_SLAVE_ID = 1
MODBUS_TIMEOUT = 2

# Registros flotadores (EJEMPLO)
REG_FLOTADOR_BAJO = 0
REG_FLOTADOR_ALTO = 1

# DO bomba
DO_BOMBA = "ioman.gpio.dio0"

# DI estado motor (solo informativo)
DI_MOTOR = "ioman.gpio.dio1"

# ================================================

bomba_encendida = False
arranque_pendiente = False
tiempo_arranque = 0


# -------- FUNCIONES GPIO (UBUS) --------

def set_bomba(valor):
    try:
        subprocess.run(
            ["ubus", "call", DO_BOMBA, "update", f'{{"value":"{valor}"}}'],
            check=True
        )
    except Exception as e:
        print(f"Error controlando bomba: {e}")


def leer_di_motor():
    try:
        result = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            text=True
        )
        return '"value": "1"' in result
    except Exception:
        return False


# -------- MODBUS --------

def leer_flotadores(client):
    rr = client.read_coils(REG_FLOTADOR_BAJO, 2, slave=MODBUS_SLAVE_ID)
    if rr.isError():
        raise Exception("Error Modbus flotadores")

    flotador_bajo = rr.bits[0]
    flotador_alto = rr.bits[1]
    return flotador_bajo, flotador_alto


# -------- MAIN --------

print("Sistema Pozo–Tanque (DO Teltonika) iniciado")

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=MODBUS_BAUDRATE,
    timeout=MODBUS_TIMEOUT,
    parity='N',
    stopbits=1,
    bytesize=8
)

while True:
    try:
        if not client.connect():
            raise Exception("No conecta Modbus")

        bajo, alto = leer_flotadores(client)
        estado_motor = leer_di_motor()

        print(f"Flotadores → Bajo: {bajo} | Alto: {alto} | Motor: {estado_motor}")

        # -------- LÓGICA TANQUE --------

        # TANQUE VACÍO → solicitar arranque
        if not bajo and not alto and not bomba_encendida and not arranque_pendiente:
            arranque_pendiente = True
            tiempo_arranque = time.time()
            print(f"Arranque programado en {RETARDO_ARRANQUE}s")

        # ARRANQUE EN ESPERA
        if arranque_pendiente:
            if bajo or alto:
                print("Arranque cancelado (nivel cambió)")
                arranque_pendiente = False

            elif time.time() - tiempo_arranque >= RETARDO_ARRANQUE:
                print("Encendiendo bomba")
                set_bomba("1")
                bomba_encendida = True
                arranque_pendiente = False

        # TANQUE LLENO → apagar
        if alto and bomba_encendida:
            print("Tanque lleno → APAGAR bomba")
            set_bomba("0")
            bomba_encendida = False
            arranque_pendiente = False

    except Exception as e:
        print("ERROR:", e)
        print("FAIL-SAFE → apagando bomba")
        set_bomba("0")
        bomba_encendida = False
        arranque_pendiente = False
        client.close()
        time.sleep(5)

    time.sleep(CICLO)
