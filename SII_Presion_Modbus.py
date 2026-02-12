from pymodbus.client import ModbusTcpClient
import struct

client = ModbusTcpClient("127.0.0.1", port=502)
client.connect()

result = client.read_holding_registers(address=0, count=2, unit=0)

print(result)

if not result.isError():
    raw = struct.pack('>HH', result.registers[1], result.registers[0])
    presion = struct.unpack('>f', raw)[0]
    print("Presión:", presion)
