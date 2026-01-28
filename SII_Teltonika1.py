#!/usr/bin/env python3
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

TIEMPO_ESPERA_CICLO = 12
TIEMPO_REINTENTO_ERROR = 1
TIEMPO_REINTENTO_PUERTO = 8
MAX_ERRORES = 3

RETARDO_REARRANQUE = 30  # 5 minutos después de reconexión

# ---------------------------------------------------
# VARIABLES GLOBALES
# ---------------------------------------------------
ultimo_rearranque = None


# ---------------------------------------------------
# UTILIDADES
# ---------------------------------------------------
def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg)


def puede_encender():
    global ultimo_rearranque

    if ultimo_rearranque is None:
        return True

    tiempo = time.time() - ultimo_rearranque
    if tiempo < RETARDO_REARRANQUE:
        restante = int((RETARDO_REARRANQUE - tiempo) / 60) + 1
        log(f"Retardo de rearranque activo ({restante} min)")
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
    global ultimo_rearranque

    log("Reiniciando puerto serial...")
    try:
        client.close()
    except:
        pass

    time.sleep(TIEMPO_REINTENTO_PUERTO)

    client = iniciar_cliente()
    conectar(client)

    ultimo_rearranque = time.time()
    log("Puerto reconectado → inicia retardo de 5 minutos")

    return client


def apagar_bomba_seguridad(client):
    try:
        client.write_coil(0, False, device_id=ID_POZO)
        log("BOMBA APAGADA (Fail-Safe)")
    except Exception as e:
        log(f"No se pudo apagar bomba: {e}")


# ---------------------------------------------------
# LÓGICA PRINCIPAL
# ---------------------------------------------------
def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    ultimo_estado_bomba = None
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

            errores_consecutivos = 0

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
                    log("Tanque vacío pero en retardo → NO ENCENDER")

            # TANQUE LLENO
            elif flotador_bajo and flotador_alto:
                accion = False
                log("Tanque lleno → APAGAR")

            # ERROR FLOTADORES
            elif not flotador_bajo and flotador_alto:
                accion = False
                log("Error flotadores → APAGAR")

            if accion is not None and accion != ultimo_estado_bomba:
                resp = client.write_coil(0, accion, device_id=ID_POZO)
                if resp.isError():
                    raise Exception("Error Modbus escritura pozo")

                ultimo_estado_bomba = accion
                log(f"Bomba {'ENCENDIDA' if accion else 'APAGADA'}")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            log(f"ERROR ({errores_consecutivos}/{MAX_ERRORES}): {e}")

            apagar_bomba_seguridad(client)

            if errores_consecutivos >= MAX_ERRORES:
                client = reiniciar_conexion(client)
                errores_consecutivos = 0

            time.sleep(TIEMPO_REINTENTO_ERROR)


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
if __name__ == "__main__":
    try:
        control_pozo()
    except KeyboardInterrupt:
        log("Programa detenido por el usuario")

