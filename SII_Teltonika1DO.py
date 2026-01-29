import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================

PUERTO_RS485 = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

DO_MOTOR = "dio0"   # salida (relay)
DI_ESTADO = "dio1"  # entrada (solo informativa)

TIEMPO_CICLO = 5
RETARDO_ARRANQUE = 10

MAX_ERRORES = 5
TIEMPO_REINTENTO_ERROR = 10

# ================= GPIO =================

def set_bomba(valor):
    subprocess.run(
        [
            "ubus",
            "call",
            f"ioman.gpio.{DO_MOTOR}",
            "update",
            f'{{"value":"{valor}"}}'
        ],
        check=False
    )

def leer_estado_motor():
    try:
        r = subprocess.check_output(
            ["ubus", "call", f"ioman.gpio.{DI_ESTADO}", "status"],
            text=True
        )
        return '"value": "1"' in r
    except:
        return False

# ================= MODBUS =================

def iniciar_modbus():
    return ModbusSerialClient(
        method="rtu",
        port=PUERTO_RS485,
        baudrate=BAUDIOS,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=2
    )

def reiniciar_modbus(client):
    print("Reiniciando comunicación RS485...")
    try:
        client.close()
    except:
        pass

    time.sleep(5)
    client = iniciar_modbus()
    client.connect()
    return client

def leer_flotadores(client):
    rr = client.read_discrete_inputs(
        address=0,
        count=2,
        unit=ID_TANQUE
    )

    if rr.isError():
        raise Exception("Error Modbus lectura flotadores")

    return rr.bits[0], rr.bits[1]

# ================= MAIN =================

def main():
    client = iniciar_modbus()
    client.connect()

    bomba_encendida = False
    arranque_pendiente = False
    tiempo_arranque = 0
    errores_consecutivos = 0

    print("\nSistema Pozo–Tanque iniciado\n")

    while True:
        try:
            bajo, alto = leer_flotadores(client)
            estado_motor = leer_estado_motor()
            errores_consecutivos = 0

            print(
                f"Flotadores → Bajo:{bajo} Alto:{alto} | "
                f"Motor (info): {estado_motor}"
            )

            # TANQUE VACÍO → solicitar arranque
            if not bajo and not alto and not bomba_encendida and not arranque_pendiente:
                arranque_pendiente = True
                tiempo_arranque = time.time()
                print(f"Arranque programado en {RETARDO_ARRANQUE}s")

            # ARRANQUE EN ESPERA
            if arranque_pendiente:
                if bajo or alto:
                    print("Arranque cancelado (nivel cambió)")
                    arranque_pendiente = False

                elif time.time() - tiempo_arranque >= RETARDO_ARRANQUE:
                    print("Encendiendo bomba")
                    set_bomba("1")
                    bomba_encendida = True
                    arranque_pendiente = False
