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
        client.write_coil(0, False, slave=ID_POZO)
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

            lectura = client.read_discrete_inputs(
                address=0,
                count=2,
                slave=ID_TANQUE
            )

            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores_consecutivos = 0

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            print(f"Bajo: {flotador_bajo} | Alto: {flotador_alto}")

            accion = None

            if not flotador_bajo and not flotador_alto:
                accion = True
                print("Tanque vacío → ENCENDER bomba")

            elif flotador_bajo and flotador_alto:
                accion = False
                print("Tanque lleno → APAGAR bomba")

            elif not flotador_bajo and flotador_alto:
                accion = False
                print("Error flotadores → APAGAR bomba")

            if accion is not None and accion != ultimo_estado_bomba:
                resp = client.write_coil(0, accion, slave=ID_POZO)

                if resp.isError():
                    raise Exception("Error Modbus escritura pozo")

                ultimo_estado_bomba = accion
                print("Bomba", "ENCENDIDA" if accion else "APAGADA")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"Error ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            apagar_bomba_seguridad(client)

            if errores_consecutivos >= MAX_ERRORES:
                print("Reiniciando conexión Modbus...")
                try:
                    client.close()
                except:
                    pass

                time.sleep(5)
                client = iniciar_cliente()
                conectar(client)
                errores_consecutivos = 0

            time.sleep(TIEMPO_REINTENTO_ERROR)


if __name__ == "__main__":
    try:
        control_pozo()
    except KeyboardInterrupt:
        print("Programa detenido por el usuario")
