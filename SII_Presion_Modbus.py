from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    method="rtu",
    port="/dev/rs485",
    baudrate=9600,
    bytesize=8,
    stopbits=1,
    parity='N',
    timeout=2
)

print("Conectando...")
print(client.connect())

result = client.read_holding_registers(address=0, count=2, unit=1)

print(result)

client.close()
