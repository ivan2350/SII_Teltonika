#!/usr/bin/env python3
import time
from pymodbus.client.sync import ModbusSerialClient

# ================= CONFIGURACIÓN =================

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_TANQUE = 32   # SOLO tanque, el pozo ya NO es RS485

GPIO_DO = "/sys/class/gpio/gpio1/value"   # 🔴 AJUSTAR SI ES NECESARIO

TIEMPO_ESPERA_CICLO = 30        # más corto para pruebas
TIEMPO_REINTENTO_ERROR = 5
MAX_ERRORES = 5


# ================= GPIO =================

def encender_bomba():
    try:
        with open(GPIO_DO, "w") as f:
            f.write("1")
        print("BOMBA ENCENDIDA (DO Teltonika)")
    except Exception as e:
        print(f"Error encendiendo bomba: {e}")

def apagar_bomba():
    try:
        with open(GPIO_DO, "w") as f:
            f.write("0")
        print("BOMBA APAGADA (DO Teltonika)")
    except Exception as e:
        print(f"Error apagando bomba: {e}")

def apagar_bomba_seguridad():
    print("FAIL-SAFE → apagando bomba")
    apagar_bomba()


# ================= MODBUS =================

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


# ================= LÓGICA PRINCIPAL =================

def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    ultimo_estado_bomba = None
    errores_consecutivos = 0

    print("\nSistema Pozo–Tanque (DO Teltonika) iniciado\n")

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

            print(f"Flotadores → Bajo: {flotador_bajo} | Alto: {flotador_alto}")

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
                if accion:
                    encender_bomba()
                else:
                    apagar_bomba()

                ultimo_estado_bomba = accion

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"ERROR ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            apagar_bomba_seguridad()

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
        apagar_bomba()
