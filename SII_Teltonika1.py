#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 120
TIEMPO_REINTENTO_ERROR = 10


def iniciar_cliente():
    return ModbusSerialClient(
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2
    )


def leer_entrada(client, direccion):
    rr = client.read_discrete_inputs(direccion)
    if rr.isError():
        raise Exception(f"Error lectura entrada {direccion}")
    return rr.bits[0]


def control_pozo():
    client = iniciar_cliente()
    client.connect()

    print("\nSistema Pozo-Tanque iniciado\n")

    while True:
        try:
            # ---- LECTURA TANQUE ----
            client.unit_id = ID_TANQUE

            flotador_bajo = leer_entrada(client, 0)
            flotador_alto = leer_entrada(client, 1)

            print(f"Bajo={flotador_bajo} | Alto={flotador_alto}")

            # ---- LÓGICA ----
            if not flotador_bajo and not flotador_alto:
                accion = True
                print("Tanque vacío → ENCENDER bomba")
            else:
                accion = False
                print("Tanque lleno / error → APAGAR bomba")

            # ---- ESCRITURA POZO ----
            client.unit_id = ID_POZO
            client.write_coil_
