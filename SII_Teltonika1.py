#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 120
TIEMPO_REINTENTO_ERROR = 10
MAX_ERRORES = 3


def iniciar_cliente():
    return ModbusSerialClient(
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2
    )


def control_pozo():
    client = iniciar_cliente()
    client.connect()

    print("\nSistema Pozo-Tanque iniciado\n")

    while True:
        try:
            # ---- LECTURA TANQUE ----
            client.unit_id = ID_TANQUE
            rr = client.read_discrete_inputs(0, 2)

            if rr.isError():
                raise Exception("Error lectura tanque")

            bajo = rr.bits[0]
            alto = rr.bits[1]

            print(f"Bajo={bajo} Alto={alto}")

            # ---- CONTROL BOMBA ----
            if not bajo and not alto:
                accion = True
            else:
                accion = False

            client.unit_id = ID_POZO
            client.write_coil(0, accion)

            print("Bomba", "ENCENDIDA" if accion else "APAGADA")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            print("ERROR:", e)
            try:
                client.unit_id = ID_POZO
                client.write_coil(0, False)
            except:
                pass
            time.sleep(TIEMPO_REINTENTO_ERROR)


if __name__ == "__main__":
    control_pozo()
