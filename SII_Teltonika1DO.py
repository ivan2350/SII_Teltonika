#!/usr/bin/env python3
import time
from datetime import datetime
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600
TIMEOUT = 2

ID_TANQUE = 32
ID_POZO = 31

REARRANQUE_SEGUNDOS = 120
MAX_ERRORES = 5

# ================================================

client = ModbusSerialClient(
    method="rtu",
    port=PUERTO,
    baudrate=BAUDIOS,
    timeout=TIMEOUT
)

motor_encendido = False
ultimo_cambio_motor = 0
motivo_apagado = "Inicial"
errores_consecutivos = 0


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def conectar(cli):
    return cli.connect()


def leer_flotadores():
    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )
    if lectura.isError():
        raise Exception("Error Modbus lectura flotadores")

    return lectura.bits[0], lectura.bits[1]


def escribir_motor(estado):
    global motor_encendido, ultimo_cambio_motor

    if estado == motor_encendido:
        return  # No hacer nada si ya está en ese estado

    client.write_coil(
        address=0,
        value=estado,
        device_id=ID_POZO
    )

    motor_encendido = estado
    ultimo_cambio_motor = time.time()

    if estado:
        log("🔵 MOTOR ENCENDIDO")
    else:
        log("🔴 MOTOR APAGADO")


# ================== MAIN ==================

log("Sistema Pozo–Tanque iniciado")

while True:
    try:
        if not conectar(client):
            raise Exception("Puerto serial no disponible")

        flotador_bajo, flotador_alto = leer_flotadores()
        errores_consecutivos = 0

        estado_motor = "ENCENDIDO" if motor_encendido else "APAGADO"

        log(
            f"Flotador BAJO: {flotador_bajo} | "
            f"Flotador ALTO: {flotador_alto} | "
            f"Motor: {estado_motor} | "
            f"Motivo: {motivo_apagado}"
        )

        ahora = time.time()

        # ======= APAGADOS =======

        if flotador_alto and flotador_bajo:
            motivo_apagado = "Tanque lleno"
            escribir_motor(False)

        elif flotador_alto and not flotador_bajo:
            motivo_apagado = "Inconsistencia de flotadores"
            escribir_motor(False)

        # ======= ENCENDIDO =======

        elif not flotador_bajo and not flotador_alto:
            if not motor_encendido:
                if ahora - ultimo_cambio_motor >= REARRANQUE_SEGUNDOS:
                    motivo_apagado = "Condición normal"
                    escribir_motor(True)
                else:
                    restante = int(
                        REARRANQUE_SEGUNDOS - (ahora - ultimo_cambio_motor)
                    )
                    log(f"⏳ Esperando re-arranque: {restante}s")

        time.sleep(2)

    except Exception as e:
        errores_consecutivos += 1
        log(f"⚠ ERROR: {e}")

        if errores_consecutivos >= MAX_ERRORES:
            motivo_apagado = "Protección por falla de comunicación"
            escribir_motor(False)

        time.sleep(3)
