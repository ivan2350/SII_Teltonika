#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
SLAVE_ID = 32

RETARDO_REARRANQUE = 120      # segundos
INTERVALO_LECTURA = 5         # segundos
MAX_FALLOS_MODBUS = 10

# ================= ESTADO =================

control_motor = False         # DIO0
ultimo_motivo = "Inicio"
ultimo_cambio_ts = None
rearranque_habilitado = True

fallos_modbus = 0

# ================= UTILIDADES =================

def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def ubus_call(path, method, data=None):
    cmd = ["ubus", "call", path, method]
    if data:
        cmd.append(data)
    out = subprocess.check_output(cmd).decode()
    return out

# ================= GPIO =================

def set_motor(on: bool):
    global control_motor, ultimo_motivo, ultimo_cambio_ts
    if control_motor == on:
        return

    ubus_call(
        "ioman.gpio.dio0",
        "update",
        f'{{"value":"{1 if on else 0}"}}'
    )

    control_motor = on
    ultimo_cambio_ts = time.time()

def leer_motor_estado():
    try:
        out = ubus_call("ioman.gpio.dio1", "status")
        return '"value": "1"' in out
    except:
        return None

# ================= MODBUS =================

def crear_cliente():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        timeout=1
    )

def leer_flotadores(client):
    rr = client.read_discrete_inputs(0, 2, slave=SLAVE_ID)
    if rr.isError():
        raise Exception("Error Modbus")
    return rr.bits[0], rr.bits[1]

# ================= MAIN =================

print("🚀 Sistema Pozo–Tanque iniciado")
client = crear_cliente()

while True:
    try:
        # ===== LEER ESTADO MOTOR (SIEMPRE) =====
        motor_estado = leer_motor_estado()

        # ===== LEER FLOTADORES =====
        bajo, alto = leer_flotadores(client)
        fallos_modbus = 0

        # ===== LÓGICA =====
        ahora = time.time()

        if alto and bajo:
            if control_motor:
                set_motor(False)
                ultimo_motivo = "Tanque lleno"

        elif alto and not bajo:
            if control_motor:
                set_motor(False)
                ultimo_motivo = "Inconsistencia flotadores"

        elif not bajo and not alto:
            if not control_motor:
                if ultimo_cambio_ts is None:
                    listo = True
                else:
                    listo = (ahora - ultimo_cambio_ts) >= RETARDO_REARRANQUE

                if listo:
                    set_motor(True)
                    ultimo_motivo = "Tanque vacío"

        # ===== IMPRESIÓN =====
        restante = 0
        if not control_motor and ultimo_cambio_ts:
            restante = max(
                0,
                RETARDO_REARRANQUE - int(ahora - ultimo_cambio_ts)
            )

        print(
            f"[{ts()}] "
            f"Flotadores → Bajo:{int(bajo)} Alto:{int(alto)} | "
            f"Control:{'ON' if control_motor else 'OFF'} | "
            f"Motor:{'ON' if motor_estado else 'OFF'} | "
            f"Rearranque:{restante}s | "
            f"Motivo:{ultimo_motivo}"
        )

    except Exception as e:
        fallos_modbus += 1
        print(f"[{ts()}] ⚠ ERROR Modbus ({fallos_modbus}/{MAX_FALLOS_MODBUS})")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            if control_motor:
                set_motor(False)
                ultimo_motivo = "Falla comunicación Modbus"
            client.close()
            time.sleep(2)
            client = crear_cliente()
            fallos_modbus = 0

    time.sleep(INTERVALO_LECTURA)
