#!/usr/bin/env python3
import struct
import time
from pymodbus.client import ModbusTcpClient

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

client = ModbusTcpClient("127.0.0.1", port=502)

if not client.connect():
    print("❌ No se pudo conectar al gateway TCP")
    exit()

print("✅ Conectado al gateway TCP")

while True:
    try:
        # 🔥 IMPORTANTE: address=0 y unit=0
        result = client.read_holding_registers(address=0, count=2, unit=0)

        if result.isError():
            print("Error lectura:", result)
        else:
            raw = struct.pack('>HH', result.registers[1], result.registers[0])
            presion = struct.unpack('>f', raw)[0]
            print(f"[{ts()}] Presión: {presion:.2f} PSI")

        time.sleep(5)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(3)
