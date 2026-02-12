from pymodbus.client import ModbusTcpClient
import struct
import time

client = ModbusTcpClient("127.0.0.1", port=502)

if not client.connect():
    print("No se pudo conectar")
    exit()

print("Conectado")

while True:
    result = client.read_holding_registers(
        address=0,
        count=2,
        unit=255   # 🔥 ESTA ES LA CLAVE
    )

    print(result)

    if not result.isError():
        raw = struct.pack('>HH', result.registers[1], result.registers[0])
        presion = struct.unpack('>f', raw)[0]
        print("Presión:", presion)

    time.sleep(5)
