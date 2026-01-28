#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ---------------- CONFIGURACIÓN ----------------
PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 120
TIEMPO_REINTENTO_ERROR = 10
MAX_ERRORES = 3
# -----------------------------------------------


def iniciar_cliente():
    client = ModbusSerialClient(
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2
    )
    return client


def conectar(client):
    if not client.connected:
        print("Conectando puerto Modbus...")
        return client.connect()
    return True


def apagar_bomba_seguridad(client):
    try:
        client.unit_id = ID_POZO
        client.write_coil(0, False)
        print("BOMBA APAGADA (Fail-Safe)")
    except Exception as e:
        print(f"No se pudo apagar bomba: {e}")


def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    ultimo_estado_bomba = None
    errores_consecutivos = 0

    print("\nSistema Pozo-Tanque iniciado\n")

    while True:
        try:
            if not conectar(client):
                raise Exception("Puerto serial no disponible")

            # ---- LECTURA TANQUE ----
            client.unit_id = ID_TANQUE
            lectura = client.read_discrete_inputs(0, 2)

            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores_consecutivos = 0

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            print(f"Bajo: {flotador_bajo} | Alto: {flotador_alto}")

            accion = None

            if not flotador_ba_
