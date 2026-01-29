#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client.serial import ModbusSerialClient

# ================= CONFIG =================
MODBUS_PORT = "/dev/rs485"
MODBUS_BAUDRATE = 9600
MODBUS_SLAVE = 32

COIL_FLOTADOR_BAJO = 0
COIL_FLOTADOR_ALTO = 1

RETARDO_REARRANQUE = 60       # segundos
TIEMPO_MAX_MARCHA = 1800     # segundos
CICLO = 2                    # segundos

DO_BOMBA = "ioman.gpio.dio0"
# =========================================

bomba_encendida = False
ultimo_arranque = 0


def set_bomba(estado: bool):
    global bomba_encendida

    if estado == bomba_encendida:
        return

    value = "1" if estado else "0"

    try:
        subprocess.run(
            [
                "ubus",
                "call",
                DO_BOMBA,
                "update",
                f'{{"value":"{value}"}}'
            ],
            check=True
        )
        bomba_encendida = estado
        print(f"BOMBA → {'ENCENDIDA' if estado else 'APAGADA'}")

    except Exception as e:
        print(f"ERROR control DO: {e}")
        bomba_encendida = False


client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=MODBUS_BAUDRATE,
    timeout=1
)

if not client.connect():
    print("ERROR: No conecta Modbus")
    exit(1)

print("Sistema Pozo–Tanque iniciado")

while True:
    try:
        rr = client.read_coils(
            address=COIL_FLOTADOR_BAJO,
            count=2,
            slave=MODBUS_SLAVE
        )

        if rr.isError():
            raise Exception("Error Modbus")

        flot_bajo = rr.bits[0]
        flot_alto = rr.bits[1]
        ahora = time.time()

        print(
            f"Flotador BAJO: {flot_bajo} | "
            f"Flotador ALTO: {flot_alto} | "
            f"Motor: {bomba_encendida}"
        )

        # ===== PARO SOLO CON TANQUE LLENO =====
        if flot_bajo and flot_alto:
            set_bomba(False)

        # ===== ARRANQUE SOLO CON TANQUE VACÍO =====
        elif not flot_bajo and not flot_alto:
            if not bomba_encendida:
                if ahora - ultimo_arranque >= RETARDO_REARRANQUE:
                    set_bomba(True)
                    ultimo_arranque = ahora

        # ===== PROTECCIÓN POR TIEMPO =====
        if bomba_encendida and (ahora - ultimo_arranque) > TIEMPO_MAX_MARCHA:
            print("Protección: tanque no responde")
            set_bomba(False)

    except Exception as e:
        print(f"ERROR: {e}")
        set_bomba(False)

    time.sleep(CICLO)
