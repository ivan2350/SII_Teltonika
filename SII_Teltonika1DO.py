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

# Entrada digital del motor (solo lectura)
ENTRADA_MOTOR = "/sys/class/gpio/gpio1/value"  # Ajusta según tu Teltonika

# ================================================

client = ModbusSerialClient(port=PUERTO, baudrate=BAUDIOS, timeout=TIMEOUT, method="rtu")

motor_encendido = False
ultimo_cambio_motor = 0
motivo_apagado = "Inicial"
errores_consecutivos = 0

# ================================================

def log(msg, color=None):
    colors = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m", "reset": "\033[0m"}
    prefix = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
    if color in colors:
        print(f"{prefix}{colors[color]}{msg}{colors['reset']}")
    else:
        print(f"{prefix}{msg}")

def conectar(cli):
    if not cli.connected:
        return cli.connect()
    return True

def leer_flotadores():
    lectura = client.read_discrete_inputs(address=0, count=2, slave=ID_TANQUE)
    if lectura.isError():
        raise Exception("Error Modbus lectura flotadores")
    return lectura.bits[0], lectura.bits[1]

def leer_estado_motor():
    try:
        with open(ENTRADA_MOTOR, "r") as f:
            return f.read().strip() == "1"
    except:
        return False

def escribir_motor(estado):
    global motor_encendido, ultimo_cambio_motor
    if estado == motor_encendido:
        return
    client.write_coil(address=0, value=estado, slave=ID_POZO)
    motor_encendido = estado
    ultimo_cambio_motor = time.time()
    if estado:
        log("🔵 MOTOR ENCENDIDO", "green")
    else:
        log(f"🔴 MOTOR APAGADO → {motivo_apagado}", "red")

# ================== MAIN ==================

log("=== Sistema Pozo–Tanque iniciado ===", "yellow")

while True:
    try:
        if not conectar(client):
            raise Exception("Puerto serial no disponible")

        flotador_bajo, flotador_alto = leer_flotadores()
        estado_motor_digital = leer_estado_motor()
        errores_consecutivos = 0

        ahora = time.time()

        # ======= APAGADOS =======
        if flotador_alto and flotador_bajo:
            motivo_apagado = "Tanque lleno"
            escribir_motor(False)
        elif flotador_alto and not flotador_bajo:
            motivo_apagado = "Inconsistencia flotadores"
            escribir_motor(False)
        # ======= ENCENDIDO =======
        elif not flotador_bajo and not flotador_alto:
            if not motor_encendido:
                if ahora - ultimo_cambio_motor >= REARRANQUE_SEGUNDOS:
                    motivo_apagado = "Condición normal"
                    escribir_motor(True)
                else:
                    restante = int(REARRANQUE_SEGUNDOS - (ahora - ultimo_cambio_motor))
                    log(f"⏳ Esperando re-arranque: {restante}s", "yellow")

        # ======= LOG EN CONSOLA =======
        log(
            f"Flotadores → Bajo: {flotador_bajo} | Alto: {flotador_alto} | "
            f"Motor: {'ENCENDIDO' if estado_motor_digital else 'APAGADO'} | "
            f"Motivo último cambio: {motivo_apagado}"
        )

        time.sleep(2)

    except Exception as e:
        errores_consecutivos += 1
        log(f"⚠ ERROR: {e}", "red")
        if errores_consecutivos >= MAX_ERRORES:
            motivo_apagado = "Protección por falla Modbus"
            escribir_motor(False)
        time.sleep(3)
