#!/usr/bin/env python3
import time
from pymodbus.client.sync import ModbusSerialClient


# ================= CONFIGURACIÓN =================

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 120        # segundos
TIEMPO_REINTENTO_ERROR = 10
MAX_ERRORES = 3


# ================= FUNCIONES =================

def iniciar_cliente():
    return ModbusSerialClient(
        method='rtu',
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2,
        retries=2,
        handle_local_echo=False
    )


def conectar(client):
    if not client.connected:
        print("Conectando puerto Modbus...")
        return client.connect()
    return True


def reiniciar_conexion(client):
    print("Reiniciando puerto serial...")
    try:
        client.close()
    except Exception:
        pass

    time.sleep(5)
    client = iniciar_cliente()
    conectar(client)
    return client


def apagar_bomba_seguridad(client):
    try:
        client.write_coil(0, False, unit=ID_POZO)
        print("BOMBA APAGADA (FAIL-SAFE)")
    except Exception as e:
        print(f"No se pudo apagar bomba: {e}")


# ================= LÓGICA PRINCIPAL =================

def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    ultimo_estado_bomba = None
    errores_consecutivos = 0

    print("\nSistema Pozo–Tanque iniciado\n")

    while True:
        try:
            if not conectar(client):
                raise Exception("Puerto serial no disponible")

            lectura = client.read_discrete_inputs(
                address=0,
                count=2,
                unit=ID_TANQUE
            )

            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores_consecutivos = 0

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            print(f"Estado flotadores → Bajo: {flotador_bajo} | Alto: {flotador_alto}")

            accion = None

            # Tanque vacío
            if not flotador_bajo and not flotador_alto:
                accion = True
                print("Tanque vacío → ENCENDER bomba")

            # Tanque lleno
            elif flotador_bajo and flotador_alto:
                accion = False
                print("Tanque lleno → APAGAR bomba")

            # Estado inválido
            elif not flotador_bajo and flotador_alto:
                accion = False
                print("ERROR flotadores → APAGAR bomba")

            if accion is not None and accion != ultimo_estado_bomba:
                resp = client.write_coil(0, accion, unit=ID_POZO)

                if resp.isError():
                    raise Exception("Error Modbus escritura pozo")

                ultimo_estado_bomba = accion
                print(f"Bomba {'ENCENDIDA' if accion else 'APAGADA'}")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"ERROR ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            apagar_bomba_seguridad(client)

            if errores_consecutivos >= MAX_ERRORES:
                client = reiniciar_conexion(client)
                errores_consecutivos = 0

            time.sleep(TIEMPO_REINTENTO_ERROR)


# ================= EJECUCIÓN =================

if __name__ == "__main__":
    try:
        control_pozo()
    except KeyboardInterrupt:
        print("Programa detenido manualmente")
