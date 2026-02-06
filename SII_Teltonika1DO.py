#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

PUERTO_RS485 = "/dev/ttyHS0"
BAUDIOS = 9600
SLAVE_ID = 1

# GPIO
DIO_CONTROL = "dio0"   # Control motor/bomba
DIO_ESTADO  = "dio1"   # Estado real motor/bomba

# Tiempos
INTERVALO_NORMAL = 5
INTERVALO_ERROR_MODBUS = 1
TIEMPO_REARRANQUE = 60

# Intentos
MAX_INTENTOS_FLOTADORES = 10
MAX_INTENTOS_MODBUS = 10

# Registros Modbus (ejemplo)
REG_FLOTADOR_MIN = 0
REG_FLOTADOR_MAX = 1

# ================= FUNCIONES GPIO =================

def gpio_status(dio):
    cmd = f"ubus call ioman.gpio.{dio} status"
    res = subprocess.check_output(cmd, shell=True).decode()
    return '"value": "1"' in res

def gpio_on():
    subprocess.call(f"ubus call ioman.gpio.{DIO_CONTROL} set '{{\"value\":1}}'", shell=True)
    print("🟢 Motor ENCENDIDO")

def gpio_off():
    subprocess.call(f"ubus call ioman.gpio.{DIO_CONTROL} set '{{\"value\":0}}'", shell=True)
    print("🔴 Motor APAGADO")

# ================= MODBUS =================

def crear_cliente():
    return ModbusSerialClient(
        method='rtu',
        port=PUERTO_RS485,
        baudrate=BAUDIOS,
        timeout=1
    )

def reiniciar_rs485():
    print("🔄 Reiniciando puerto RS485...")
    subprocess.call("ubus call network.interface down '{\"interface\":\"rs485\"}'", shell=True)
    time.sleep(2)
    subprocess.call("ubus call network.interface up '{\"interface\":\"rs485\"}'", shell=True)
    time.sleep(2)

def leer_flotadores(cliente):
    rr = cliente.read_holding_registers(REG_FLOTADOR_MIN, 2, unit=SLAVE_ID)
    if rr.isError():
        return None
    flot_min = rr.registers[0]
    flot_max = rr.registers[1]
    return flot_min, flot_max

# ================= PROGRAMA PRINCIPAL =================

cliente = crear_cliente()
cliente.connect()

intentos_flotador = 0
intentos_modbus = 0
ultimo_apagado = None

while True:
    try:
        flotadores = leer_flotadores(cliente)

        if flotadores is None:
            intentos_modbus += 1
            print(f"⚠️ Error Modbus ({intentos_modbus}/{MAX_INTENTOS_MODBUS})")

            if intentos_modbus >= MAX_INTENTOS_MODBUS:
                print("❌ Modbus no responde, apagando motor y reiniciando puerto")
                gpio_off()
                cliente.close()
                reiniciar_rs485()
                cliente = crear_cliente()
                cliente.connect()
                intentos_modbus = 0

            time.sleep(INTERVALO_ERROR_MODBUS)
            continue

        # Modbus OK
        intentos_modbus = 0
        flot_min, flot_max = flotadores
        print(f"📟 Flotadores → MIN:{flot_min} MAX:{flot_max}")

        estado_motor = gpio_status(DIO_ESTADO)
        control_motor = gpio_status(DIO_CONTROL)

        # --------- Lógica flotadores ---------

        if flot_min == 0 or flot_max == 0:
            intentos_flotador += 1
            print(f"⚠️ Flotadores inválidos ({intentos_flotador}/{MAX_INTENTOS_FLOTADORES})")

            if intentos_flotador >= MAX_INTENTOS_FLOTADORES:
                print("❌ Protección flotadores → apagando motor")
                gpio_off()
        else:
            intentos_flotador = 0

            # Rearranque solo si control está apagado
            if not control_motor:
                if ultimo_apagado is None:
                    ultimo_apagado = time.time()
                elif time.time() - ultimo_apagado >= TIEMPO_REARRANQUE:
                    print("⏱️ Tiempo de rearranque cumplido")
                    gpio_on()
                    ultimo_apagado = None
            else:
                ultimo_apagado = None

        # Mostrar estado real del motor
        print("⚙️ Estado motor:", "ENCENDIDO" if estado_motor else "APAGADO")

        time.sleep(INTERVALO_NORMAL)

    except Exception as e:
        print("💥 Error general:", e)
        gpio_off()
        time.sleep(2)
