from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    method="rtu",
    port="/dev/rs485",
    baudrate=9600,
    bytesize=8,
    stopbits=1,
    parity='N',
    timeout=1
)

client.connect()

for unit in range(1, 6):
    print(f"Probando ID {unit}")
    result = client.read_holding_registers(address=0, count=2, unit=unit)
    print(result)

client.close()
