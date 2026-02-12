#!/usr/bin/env python3
from pymodbus.client import ModbusSerialClient
import struct

client = ModbusSerialClient(
    method='rtu',
    port='/dev/rs485',
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=2
)

client.connect()

print("Conectado RS485")

# 🔥 PRUEBA 1: holding registers desde 0
result = client.read_holding_registers(address=0, count=2, unit=1)
print("Holding 0:", result)

# 🔥 PRUEBA 2: holding desde 1
result = client.read_holding_registers(address=1, count=2, unit=1)
print("Holding 1:", result)

# 🔥 PRUEBA 3: input registers desde 0
result = client.read_input_registers(address=0, count=2, unit=1)
print("Input 0:", result)

# 🔥 PRUEBA 4: leer 10 registros como el manual
result = client.read_holding_registers(address=0, count=10, unit=1)
print("Holding 10:", result)

client.close()
