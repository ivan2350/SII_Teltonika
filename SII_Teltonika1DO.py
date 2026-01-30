#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client.serial import ModbusSerialClient

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================

MODBUS_PORT = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120      # segundos
TIEMPO_CICLO = 2              # segundos

DO_BOMBA = "ioman.gpio.dio0"
DI_MOTOR = "ioman.gpio.dio1"

# ==========================================================
# ESTADOS INTERNOS
# ==========================================================

bomba_encendida = False
ultimo_evento = "Inicio del sistema"
tiempo_ultimo_cambio = 0
rearranque_activo = False

# ==========================================================
# MODBUS
# ==========================================================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDIOS,
    timeout=2,
    stopbits=1,
    bytesize=8,
    parity="N"
)

# ==========================================================
# FUNCIONES DE HARDWARE
# ==========================================================

def set_bomba(encender: bool, motivo: str):
    global bomba_encendida, ultimo_evento, tiempo_ultimo_cambio, rearranque_activo

    if encender == bomba_encendida:
        return  # Evita comandos redundantes

    valor = "1" if encender else "0"
    subprocess.call([
        "ubus", "call", DO_BOMBA, "update",
        f'{{"value":"{valor}"}}'
    ])

    bomba_encendida = encender
    ultimo_evento = motivo
    tiempo_ultimo_cambio = time.time()
    rearranque_activo = not encender


def leer_motor():
    try:
        salida = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            text=True
        )
        return '"value": "1"' in salida
    except:
        return None


def leer_flotadores():
    if not client.connect():
        raise Exception("Puerto RS485 no disponible")

    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error Modbus lectura de flotadores")

    return lectura.bits[0], lectura.bits[1]

# ==========================================================
# UTILIDADES
# ==========================================================

def encabezado():
    print("\n" + "=" * 68)
    print(" SISTEMA DE CONTROL POZO – TANQUE")
    print(" Control por RS485 + DO Teltonika")
    print("=" * 68)
    print(
        f"{'Hora':<9}"
        f"{'Bajo':<7}"
        f"{'Alto':<7}"
        f"{'Motor':<9}"
        f"{'Bomba':<9}"
        f"{'Estado':<20}"
    )
    print("-" * 68)


def log_estado(bajo, alto, motor, estado):
    print(
        f"{time.strftime('%H:%M:%S'):<9}"
        f"{str(bajo):<7}"
        f"{str(alto):<7}"
        f"{str(motor):<9}"
        f"{('ON' if bomba_encendida else 'OFF'):<9}"
        f"{estado:<20}"
    )

# ==========================================================
# MAIN
# ==========================================================

encabezado()

while True:
    try:
        bajo, alto = leer_flotadores()
        motor = leer_motor()

        ahora = time.time()
        tiempo_restante = max(
            0,
            RETARDO_REARRANQUE - (ahora - tiempo_ultimo_cambio)
        )

        # ------------------ LÓGICA DE CONTROL ------------------

        if alto and not bajo:
            if bomba_encendida:
                set_bomba(False, "Inconsistencia flotadores")
            estado = "INCONSISTENCIA"

        elif bajo and alto:
            if bomba_encendida:
                set_bomba(False, "Tanque lleno")
            estado = "TANQUE LLENO"

        elif not bajo and not alto:
            if not bomba_encendida:
                if rearranque_activo and tiempo_restante > 0:
                    estado = f"REARRANQUE {int(tiempo_restante)}s"
                else:
                    set_bomba(True, "Tanque vacío")
                    estado = "ARRANQUE"
            else:
                estado = "OPERANDO"

        else:
            estado = "TRANSICIÓN"

        # ------------------ LOG ------------------

        log_estado(bajo, alto, motor, estado)

    except Exception as e:
        if bomba_encendida:
            set_bomba(False, "Fail-safe comunicación")
        print(f"{time.strftime('%H:%M:%S')}  ERROR: {e}")

    time.sleep(TIEMPO_CICLO)
