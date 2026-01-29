#!/usr/bin/env python3
import time
from pymodbus.client.serial import ModbusSerialClient

# ================= CONFIG =================
MODBUS_PORT = "/dev/rs485"      # ← COMO EN TU CÓDIGO ORIGINAL
MODBUS_BAUDRATE = 9600
MODBUS_SLAVE = 32

COIL_FLOTADOR_BAJO = 0
COIL_FLOTADOR_ALTO = 1

RETARDO_REARRANQUE = 60
TIEMPO_MAX_MARCHA = 1800
CICLO = 2
# =========================================

bomba_encendida = False
ultimo_arranque = 0

def set_bomba(estado):
    global bomba_encendida
    if estado == bomba_encendida:
        return

    value = "1" if estado else "0"
    with open("/sys/class/gpio/gpio1/value", "w") as f:
        f.write(value)

    bomba_encendida = estado
    print(f"BOMBA → {'ENCENDIDA' if estado else 'APAGADA'}")

client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=MODBUS_BAUDRATE,
    timeout=1
)

if not client.connect():
    print("ERROR Modbus")
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

        # ===== PARO POR TANQUE LLENO =====
        if flot_bajo and flot_alto:
            set_bomba(False)

        # ===== ARRANQUE POR TANQUE VACÍO =====
        elif not flot_bajo and not flot_alto:
            if not bomba_encendida:
                if ahora - ultimo_arranque >= RETARDO_REARRANQUE:
                    set_bomba(True)
                    ultimo_arranque = ahora

        # ===== PROTECCIÓN =====
        if bomba_encendida and (ahora - ultimo_arranque) > TIEMPO_MAX_MARCHA:
            print("Protección: tanque no responde")
            set_bomba(False)

    except Exception as e:
        print(f"ERROR: {e}")
        set_bomba(False)

    time.sleep(CICLO)
