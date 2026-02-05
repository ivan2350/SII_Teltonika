#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/rs485"
MODBUS_BAUD = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120    # segundos
MAX_INTENTOS_MODBUS = 10                        
CICLO_NORMAL = 60   # segundos
CICLO_ERROR = 1

# Teltonika
DIO_CONTROL = "ioman.gpio.dio0"   # salida
DIO_ESTADO = "ioman.gpio.dio1"    # entrada

# ================= ESTADO =================

control_motor = False
ultimo_motivo = "Inicio"
ultimo_cambio_ts = 0

rearranque_activo = False
ts_rearranque = 0

errores_modbus = 0

# ================= UTILIDADES =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

def ubus_call(obj, method, params):
    subprocess.run(
        ["ubus", "call", obj, method, params],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def leer_estado_motor():
    try:
        out = subprocess.check_output(
            ["ubus", "call", DIO_ESTADO, "status"],
            text=True
        )
        return '"value": "1"' in out
    except:
        return None

def set_motor(on: bool, motivo: str):
    global control_motor, ultimo_motivo, ultimo_cambio_ts
    global rearranque_activo, ts_rearranque

    if control_motor == on:
        return

    ubus_call(
        DIO_CONTROL,
        "update",
        f'{{"value":"{1 if on else 0}"}}'
    )

    control_motor = on
    ultimo_motivo = motivo
    ultimo_cambio_ts = time.time()

    if not on:
        rearranque_activo = True
        ts_rearranque = time.time()

    print(
        f"[{ts()}] 🔔 CONTROL {'ENCENDIDO' if on else 'APAGADO'} | Motivo: {motivo}"
    )

def conectar_modbus():
    client = ModbusSerialClient(
        port=MODBUS_PORT,
        baudrate=MODBUS_BAUD,
        parity="N",
        stopbits=1,
        bytesize=8,
        timeout=1
    )
    return client if client.connect() else None

# ================= INICIO =================

print("🚀 Sistema Pozo–Tanque iniciado")

client = None

while True:
    try:
        if not client:
            client = conectar_modbus()
            if not client:
                raise Exception("No conecta Modbus")

        lectura = client.read_discrete_inputs(
            address=0,
            count=2,
            device_id=ID_TANQUE
        )

        if lectura.isError():
            raise Exception("Error lectura Modbus")

        errores_modbus = 0

        flot_bajo = lectura.bits[0]
        flot_alto = lectura.bits[1]

        estado_motor = leer_estado_motor()

        ahora = time.time()
        restante = 0

        if rearranque_activo:
            restante = int(
                max(0, RETARDO_REARRANQUE - (ahora - ts_rearranque))
            )
            if restante == 0:
                rearranque_activo = False

        # ================= LÓGICA =================

        if not flot_bajo and not flot_alto:
            if not control_motor and not rearranque_activo:
                set_motor(True, "Tanque vacío")

        elif flot_bajo and flot_alto:
            if control_motor:
                set_motor(False, "Tanque lleno")

        elif flot_alto and not flot_bajo:
            if control_motor:
                set_motor(False, "Inconsistencia flotadores")

        # ================= CONSOLA =================

        estado_txt = "DESCONOCIDO" if estado_motor is None else (
            "ON" if estado_motor else "OFF"
        )

        print(
            f"[{ts()}] "
            f"Flotadores → Bajo:{int(flot_bajo)} Alto:{int(flot_alto)} | "
            f"Control:{'ON' if control_motor else 'OFF'} | "
            f"Motor:{estado_txt} | "
            f"Rearranque:{restante}s | "
            f"Motivo:{ultimo_motivo}"
        )

        time.sleep(CICLO_NORMAL)

    except Exception:
        errores_modbus += 1
        print(f"[{ts()}] ❌ ERROR Modbus ({errores_modbus}/{MAX_INTENTOS_MODBUS})")

        if errores_modbus >= MAX_INTENTOS_MODBUS:
            if control_motor:
                set_motor(False, "Falla comunicación Modbus")
            client = None
            errores_modbus = 0

        time.sleep(CICLO_ERROR)
