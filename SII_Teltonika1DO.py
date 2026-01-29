#!/usr/bin/env python3
import time
import sys
from pymodbus.client.serial import ModbusSerialClient

# ================= CONFIGURACIÓN =================
MODBUS_PORT = "/dev/ttyRS485"
MODBUS_BAUDRATE = 9600
MODBUS_SLAVE = 32

COIL_FLOTADOR_BAJO = 0
COIL_FLOTADOR_ALTO = 1

DO_GPIO = 1  # Salida digital Teltonika

TIEMPO_REARRANQUE = 60        # segundos
TIEMPO_MAX_ENCENDIDO = 1800   # 30 min seguridad
CICLO_LECTURA = 2             # segundos
# =================================================

motor_encendido = False
ultimo_arranque = 0

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    sys.stdout.flush()

def set_motor(estado):
    global motor_encendido
    if estado and not motor_encendido:
        log("MOTOR → ENCENDIDO")
        system_call("on")
        motor_encendido = True
    elif not estado and motor_encendido:
        log("MOTOR → APAGADO")
        system_call("off")
        motor_encendido = False

def system_call(cmd):
    # Teltonika DO
    # gpio.sh set <gpio> <0|1>
    value = "1" if cmd == "on" else "0"
    os_cmd = f"gpio.sh set {DO_GPIO} {value}"
    import os
    os.system(os_cmd)

def fail_safe():
    log("FAIL-SAFE → apagando bomba")
    set_motor(False)

# ================= MODBUS =================
client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=MODBUS_BAUDRATE,
    timeout=1
)

if not client.connect():
    log("ERROR: No conecta Modbus")
    fail_safe()
    sys.exit(1)

log("Sistema Pozo–Tanque iniciado")

# ================= LOOP PRINCIPAL =================
while True:
    try:
        rr = client.read_coils(
            address=COIL_FLOTADOR_BAJO,
            count=2,
            slave=MODBUS_SLAVE
        )

        if rr.isError():
            raise Exception("Error lectura Modbus")

        flotador_bajo = rr.bits[0]
        flotador_alto = rr.bits[1]

        log(f"Flotador BAJO: {flotador_bajo} | Flotador ALTO: {flotador_alto} | Motor: {motor_encendido}")

        ahora = time.time()

        # -------- LÓGICA --------
        # Tanque lleno → apagar
        if flotador_bajo and flotador_alto:
            set_motor(False)

        # Tanque bajo → posible arranque
        elif not flotador_bajo:
            if not motor_encendido:
                if ahora - ultimo_arranque >= TIEMPO_REARRANQUE:
                    set_motor(True)
                    ultimo_arranque = ahora
                else:
                    log("Esperando tiempo de re-arranque")

        # Protección por tiempo máximo encendido
        if motor_encendido and (ahora - ultimo_arranque) > TIEMPO_MAX_ENCENDIDO:
            log("Protección: tiempo máximo encendido alcanzado")
            set_motor(False)

    except Exception as e:
        log(f"ERROR: {e}")
        fail_safe()

    time.sleep(CICLO_LECTURA)
