#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------
PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600

ID_POZO = 31
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 120       # Cada cuánto se lee el tanque
TIEMPO_REINTENTO_ERROR = 10      # Pausa tras error antes de reintentar
TIEMPO_REINTENTO_PUERTO = 8      # Pausa al reiniciar puerto
MAX_ERRORES = 3                   # Reintentos antes de apagar
RETARDO_MIN_APAGADO = 180         # 3 minutos mínimo apagada

# ---------------------------------------------------
# VARIABLES GLOBALES
# ---------------------------------------------------
ultimo_estado_bomba = None
tiempo_ultimo_apagado = None

# ---------------------------------------------------
# UTILIDADES
# ---------------------------------------------------
def log(msg):
    print(time.strftime("[%d/%d/%y-%H-%W-%A %H:%M:%S]"), msg)


def puede_encender():
    """Devuelve True si ya pasó el retardo mínimo de bomba apagada"""
    if tiempo_ultimo_apagado is None:
        return True

    tiempo_apagada = time.time() - tiempo_ultimo_apagado
    if tiempo_apagada < RETARDO_MIN_APAGADO:
        restante = int(RETARDO_MIN_APAGADO - tiempo_apagada)
        log(f"Bomba en retardo OFF ({restante} s restantes)")
        return False

    return True

# ---------------------------------------------------
# MODBUS
# ---------------------------------------------------
def iniciar_cliente():
    return ModbusSerialClient(
        port=PUERTO,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2,
        retries=3
    )


def conectar(client):
    if not client.connected:
        log("Conectando puerto Modbus...")
        return client.connect()
    return True


def reiniciar_conexion(client):
    log("Reiniciando puerto serial...")
    try:
        client.close()
    except:
        pass
    time.sleep(TIEMPO_REINTENTO_PUERTO)
    client = iniciar_cliente()
    conectar(client)
    return client


def apagar_bomba_seguridad(client):
    global tiempo_ultimo_apagado, ultimo_estado_bomba
    try:
        if ultimo_estado_bomba != False:
            client.write_coil(0, False, device_id=ID_POZO)
            tiempo_ultimo_apagado = time.time()
            ultimo_estado_bomba = False
            log("BOMBA APAGADA (Fail-Safe)")
    except Exception as e:
        log(f"No se pudo apagar bomba: {e}")

# ---------------------------------------------------
# LÓGICA PRINCIPAL
# ---------------------------------------------------
def control_pozo():
    global ultimo_estado_bomba, tiempo_ultimo_apagado

    client = iniciar_cliente()
    conectar(client)

    errores_consecutivos = 0

    log("Sistema Pozo-Tanque iniciado")

    while True:
        try:
            if not conectar(client):
                raise Exception("Puerto serial no disponible")

            lectura = client.read_discrete_inputs(
                0,
                count=2,
                device_id=ID_TANQUE
            )

            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores_consecutivos = 0  # Lectura exitosa → reinicia errores

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            log(f"Flotadores → Bajo: {flotador_bajo} | Alto: {flotador_alto}")

            accion = None

            # TANQUE VACÍO
            if not flotador_bajo and not flotador_alto:
                if puede_encender():
                    accion = True
                    log("Tanque vacío → ENCENDER")
                else:
                    accion = False
                    log("Tanque vacío pero retardo OFF activo")

            # TANQUE LLENO
            elif flotador_bajo and flotador_alto:
                accion = False
                log("Tanque lleno → APAGAR")

            # ERROR FLOTADORES
            elif not flotador_bajo and flotador_alto:
                accion = False
                log("Error flotadores → APAGAR")

            # Aplicar acción solo si cambió el estado
            if accion is not None and accion != ultimo_estado_bomba:
                resp = client.write_coil(0, accion, device_id=ID_POZO)
                if resp.isError():
                    raise Exception("Error Modbus escritura pozo")

                if not accion:
                    tiempo_ultimo_apagado = time.time()

                ultimo_estado_bomba = accion
                log(f"Bomba {'ENCENDIDA' if accion else 'APAGADA'}")

            # Espera entre ciclos
            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            log(f"ERROR ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            if errores_consecutivos >= MAX_ERRORES:
                log("Máximo de errores alcanzado → apagando bomba y reiniciando puerto")
                apagar_bomba_seguridad(client)
                client = reiniciar_conexion(client)
                errores_consecutivos = 0
            else:
                log("Error temporal, reintentando sin apagar bomba")
                time.sleep(TIEMPO_REINTENTO_ERROR)

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
if __name__ == "__main__":
    try:
        control_pozo()
    except KeyboardInterrupt:
        log("Programa detenido por el usuario")
