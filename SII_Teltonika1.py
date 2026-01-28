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


def conectar(client):
    if not client.connected:
        print("Conectando puerto Modbus...")
        return client.connect()
    return True


def apagar_bomba_seguridad(client):
    try:
        client.write_coil(0, False, unit=ID_POZO)
        print("BOMBA APAGADA (Fail-Safe)")
    except Exception as e:
        print(f"No se pudo apagar bomba: {e}")


def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    ultimo_estado_bomba = None
    errores_consecutivos = 0

    print("Sistema Pozo-Tanque iniciado")

    while True:
        try:
            lectura = client.read_discrete_inputs(
                address=0,
                count=2,
                unit=ID_TANQUE
            )

            if lectura.isError():
                raise Exception("Error lectura tanque")

            errores_consecutivos = 0

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            accion = None

            if not flotador_bajo and not flotador_alto:
                accion = True
            elif flotador_bajo and flotador_alto:
                accion = False
            elif not flotador_bajo and flotador_alto:
                accion = False

            if accion is not None and accion != ultimo_estado_bomba:
                resp = client.write_coil(0, accion, unit=ID_POZO)
                if resp.isError():
                    raise Exception("Error escritura pozo")

                ultimo_estado_bomba = accion
                print("Bomba", "ENCENDIDA" if accion else "APAGADA")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"Error ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            apagar_bomba_seguridad(client)

            if errores_consecutivos >= MAX_ERRORES:
                client.close()
                time.sleep(5)
                client = iniciar_cliente()
                conectar(client)
                errores_consecutivos = 0

            time.sleep(TIEMPO_REINTENTO_ERROR)


if __name__ == "__main__":
    control_pozo()
