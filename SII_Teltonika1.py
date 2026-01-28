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
        parity="N",
        stopbits=1,
        timeout=2
    )


def apagar_bomba_seguridad(client):
    try:
        client.write_coil(0, False, device_id=ID_POZO)
        print("BOMBA APAGADA (Fail-Safe)")
    except Exception as e:
        print("No se pudo apagar bomba:", e)


def control_pozo():
    client = iniciar_cliente()
    client.connect()

    errores_consecutivos = 0
    ultimo_estado = None

    print("\nSistema Pozo-Tanque iniciado\n")

    while True:
        try:
            # ---- LECTURA TANQUE ----
            rr = client.read_discrete_inputs(
                0,
                count=2,
                device_id=ID_TANQUE
            )

            if rr.isError():
                raise Exception("Error lectura tanque")

            errores_consecutivos = 0

            flotador_bajo = rr.bits[0]
            flotador_alto = rr.bits[1]

            print(f"Bajo={flotador_bajo} | Alto={flotador_alto}")

            # ---- LÓGICA ----
            if not flotador_bajo and not flotador_alto:
                accion = True
                print("Tanque vacío → ENCENDER bomba")
            else:
                accion = False
                print("Tanque lleno / error → APAGAR bomba")

            # ---- ESCRITURA POZO ----
            if accion != ultimo_estado:
                wr = client.write_coil(
                    0,
                    accion,
                    device_id=ID_POZO
                )

                if wr.isError():
                    raise Exception("Error escritura pozo")

                ultimo_estado = accion
                print("Bomba", "ENCENDIDA" if accion else "APAGADA")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"ERROR ({errores_consecutivos}/{MAX_ERRORES}):", e)

            apagar_bomba_seguridad(client)

            if errores_consecutivos >= MAX_ERRORES:
                print("Reiniciando conexión Modbus...")
                client.close()
                time.sleep(5)
                client = iniciar_cliente()
                client.connect()
                errores_consecutivos = 0

            time.sleep(TIEMPO_REINTENTO_ERROR)


if __name__ == "__main__":
    control_pozo()
