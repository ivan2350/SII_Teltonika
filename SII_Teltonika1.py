#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------
PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 12       # Cada cuánto se lee el tanque
TIEMPO_REINTENTO_ERROR = 10      # Pausa tras error antes de reintentar
TIEMPO_REINTENTO_PUERTO = 8      # Pausa al reiniciar puerto
MAX_ERRORES = 3                   # Reintentos antes de apagar
RETARDO_MIN_APAGADO = 180         # 3 minutos mínimo apagada

# ---------------------------------------------------
# VARIABLES GLOBALES
# ---------------------------------------------------
ultimo_estado_bomba = None
tiempo_ultimo_apagado = None

# ---------------------------------------------------
# UTILIDADES
# ---------------------------------------------------
def log(msg):
    print(time.strftime("[%m/%d/%y-%H-%W-%A %H:%M:%S]"), msg)


def puede_encender():
    """Devuelve True si ya pasó el retardo mínimo de bomba apagada"""
    if tiempo_ultimo_apagado is None:
        return True

    tiempo_apagada = time.time() - tiempo_ultimo_apagado
    if tiempo_apagada < RETARDO_MIN_APAGADO:
        restante = int(RETARDO_MIN_APAGADO - tiempo_apagada)
        log(f"Bomba en retardo OFF ({restante} s restantes)")
        return False

    return True

# ---------------------------------------------------
# MODBUS
# ---------------------------------------------------
def iniciar_cliente():
    return ModbusSerialClient(
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        ti
