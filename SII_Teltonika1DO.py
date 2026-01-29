#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"
BAUDRATE = 9600
SLAVE_TANQUE = 32

TIEMPO_CICLO = 5            # segundos
RETARDO_ARRANQUE = 60       # segundos
TIMEOUT_MODBUS = 2
MAX_ERRORES = 5

# ================= IO TELTONIKA =================

DO_BOMBA = "ioman.gpio.dio0"   # salida bomba
DI_MOTOR = "ioman.gpio.dio1"   # entrada estado motor (informativo)

# ================= FUNCIONES =================

def iniciar_modbus():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=TIMEOUT_MODBUS
    )


def leer_flotadores(client):
    rr = client.read_discrete_inputs(0, 2, unit=SLAVE_TANQUE)
    if rr.isError():
        raise Exception("Error Modbus flotadores")

    return rr.bits[0], rr.bits[1]


def set_bomba(encender):
    valor = "1" if encender else "0"
    subprocess.run(
        ["ubus", "call", DO_BOMBA, "update", f'{{"value":"{valor}"}}'],
        check=True
    )


def leer_estado_motor():
    r = subprocess.check_output(
        ["ubus", "call", DI_MOTOR, "status"],
        text=True
    )
    return '"value": "1"' in r


# ================= PROGRAMA PRINCIPAL =================

def main():
    print("\nSistema Pozo–Tanque (DO Teltonika) iniciado\n")

    client = iniciar_modbus()
    errores = 0

    bomba_encendida = False
    arranque_pendiente = False
    tiempo_arranque = 0

    if not client.connect():
        print("ERROR: No conecta Modbus")
        set_bomba(False)
        return

    try:
        while True:
            try:
                bajo, alto = leer_flotadores(client)
                estado_motor = leer_estado_motor()

                print(f"Flotadores → Bajo:{bajo} Alto:{alto} | Motor:{estado_motor}")

                errores = 0

                # ===== TANQUE LLENO =====
                if bajo and alto:
                    if bomba_encendida:
                        print("Tanque lleno → APAGAR bomba")
                        set_bomba(False)
                        bomba_encendida = False
                    arranque_pendiente = False

                # ===== ESTADO INVÁLIDO =====
                elif not bajo and alto:
                    print("Estado inválido flotadores → APAGAR bomba")
                    set_bomba(False)
                    bomba_encendida = False
                    arranque_pendiente = False

                # ===== TANQUE VACÍO =====
                elif not bajo and not alto:
                    if not bomba_encendida and not arranque_pendiente:
                        arranque_pendiente = True
                        tiempo_arranque = time.time()
                        print(f"Arranque programado en {RETARDO_ARRANQUE}s")

                # ===== ARRANQUE EN ESPERA =====
                if arranque_pendiente:
                    if bajo or alto:
                        print("Arranque cancelado (nivel cambió)")
                        arranque_pendiente = False

                    elif time.time() - tiempo_arranque >= RETARDO_ARRANQUE:
                        print("Encendiendo bomba")
                        set_bomba(True)
                        bomba_encendida = True
                        arranque_pendiente = False

                time.sleep(TIEMPO_CICLO)

            except Exception as e:
                errores += 1
                print(f"ERROR ({errores}/{MAX_ERRORES}): {e}")

                set_bomba(False)
                bomba_encendida = False
                arranque_pendiente = False

                if errores >= MAX_ERRORES:
                    print("Reiniciando conexión Modbus")
                    client.close()
                    time.sleep(3)
                    client = iniciar_modbus()
                    client.connect()
                    errores = 0

                time.sleep(5)

    except KeyboardInterrupt:
        print("\nPrograma detenido por usuario")
        set_bomba(False)

    finally:
        client.close()
        set_bomba(False)


if __name__ == "__main__":
    main()
