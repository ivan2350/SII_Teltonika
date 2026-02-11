#!/usr/bin/env python3
import time
import struct
from pymodbus.client import ModbusTcpClient

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

client = ModbusTcpClient("127.0.0.1", port=502)

if not client.connect():
    print("❌ No se pudo conectar a Modbus TCP")
    exit()

print("✅ Conectado a Modbus TCP local")

while True:
    try:
        result = client.read_holding_registers(address=1, count=2, unit=1)

        if result.isError():
            print("Error lectura")
        else:
            raw = struct.pack('>HH', result.registers[1], result.registers[0])
            presion = struct.unpack('>f', raw)[0]
            print(f"[{ts()}] Presión: {presion:.2f} PSI")

        time.sleep(5)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(3)
