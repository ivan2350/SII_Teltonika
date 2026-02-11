#!/usr/bin/env python3
import time
import struct
from pymodbus.client import ModbusSerialClient

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_SENSOR = 1

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

def crear_cliente():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        stopbits=1,
        parity='N',
        timeout=2,
        retries=3,
        retry_on_empty=True,
        strict=False
    )

def leer_presion(client):
    # pequeño delay para estabilizar RS485
    time.sleep(0.1)

    lectura = client.read_holding_registers(
        address=0,
        count=10,
        unit=ID_SENSOR
    )

    if lectura.isError():
        raise Exception("Error lectura presión")

    # primeros 2 registros = presión
    raw = struct.pack('>HH', lectura.registers[1], lectura.registers[0])
    presion = struct.unpack('>f', raw)[0]

    return presion

print(f"[{ts()}] 🚀 Probando lectura DPR-S80")

client = crear_cliente()

if not client.connect():
    print("❌ No se pudo abrir puerto RS485")
    exit()

while True:
    try:
        presion = leer_presion(client)
        print(f"[{ts()}] Presión: {presion:.2f} PSI")
        time.sleep(5)

    except Exception as e:
        print(f"[{ts()}] ERROR → {e}")
        time.sleep(3)
