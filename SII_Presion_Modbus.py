#!/usr/bin/env python3
import time
import struct
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("127.0.0.1", port=502)

client.connect()

result = client.read_holding_registers(0, 2, unit=1)

print(result)