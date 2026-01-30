#!/usr/bin/env python3
import time
import subprocess
from datetime import datetime
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"      # RS485 Teltonika
BAUDIOS = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120         # segundos
CICLO = 2                        # segundos entre ciclos

# GPIO Teltonika (ioman)
DO_BOMBA = "ioman.gpio.dio0"     # Salida bomba
DI_MOTOR = "ioman.gpio.dio1"     # Entrada estado motor

# ================= ESTADOS =================

bomba_encendida = False
arranque_pendiente = False
tiempo_evento = None
ultimo_motivo = "Inicio del sistema"

motor_estado_anterior = False
tiempo_inicio_motor = None
tiempo_total_motor = 0

errores_modbus = 0

# ================= UTILIDADES =================

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def ubus_do(valor):
    subprocess.run(
        ["ubus", "call", DO_BOMBA, "update", f'{{"value":"{valor}"}}'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def leer_di():
    try:
        r = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            stderr=subprocess.DEVNULL
        ).decode()
        return '"value": "1"' in r
    except:
        return False

def formatear_tiempo(seg):
    h = int(seg // 3600)
    m = int((seg % 3600) // 60)
    s = int(seg % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ================= MODBUS =================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDIOS,
    timeout=1,
    stopbits=1,
    bytesize=8,
    parity='N'
)

def leer_flotadores():
    if not client.connect():
        raise Exception("No conecta Modbus")

    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error Modbus lectura tanque")

    return lectura.bits[0], lectura.bits[1]

# ================= INICIO =================

log("Sistema Pozo–Tanque iniciado")

while True:
    try:
        flotador_bajo, flotador_alto = leer_flotadores()
        errores_modbus = 0

        # ================= MOTOR (DI) =================
        motor_estado = leer_di()

        if motor_estado and not motor_estado_anterior:
            tiempo_inicio_motor = time.time()

        if not motor_estado and motor_estado_anterior:
            tiempo_total_motor += time.time() - tiempo_inicio_motor
            tiempo_inicio_motor = None

        motor_estado_anterior = motor_estado

        tiempo_motor = tiempo_total_motor
        if motor_estado and tiempo_inicio_motor:
            tiempo_motor += time.time() - tiempo_inicio_motor

        # ================= ALERTA MANUAL =================
        alerta_manual = (not bomba_encendida and motor_estado)

        # ================= LÓGICA CONTROL =================

        # TANQUE LLENO
        if flotador_bajo and flotador_alto and bomba_encendida:
            ubus_do("0")
            bomba_encendida = False
            arranque_pendiente = True
            tiempo_evento = time.time()
            ultimo_motivo = "Tanque lleno"

        # INCONSISTENCIA
        elif not flotador_bajo and flotador_alto and bomba_encendida:
            ubus_do("0")
            bomba_encendida = False
            arranque_pendiente = True
            tiempo_evento = time.time()
            ultimo_motivo = "Inconsistencia flotadores"

        # TANQUE VACÍO → ARRANQUE PROGRAMADO
        elif not flotador_bajo and not flotador_alto and not bomba_encendida:
            if not arranque_pendiente:
                arranque_pendiente = True
                tiempo_evento = time.time()
                ultimo_motivo = "Solicitud de llenado"

        # ARRANQUE DESPUÉS DE RETARDO
        if arranque_pendiente:
            restante = RETARDO_REARRANQUE - (time.time() - tiempo_evento)
            if restante <= 0 and not bomba_encendida:
                ubus_do("1")
                bomba_encendida = True
                arranque_pendiente = False
                ultimo_motivo = "Arranque automático"

        # ================= CONSOLA =================

        estado_ctrl = "ENCENDIDO" if bomba_encendida else "APAGADO"
        estado_motor = "ENCENDIDO" if motor_estado else "APAGADO"

        log(
            f"Flotadores BAJO={flotador_bajo} | ALTO={flotador_alto} | "
            f"CTRL={estado_ctrl} | MOTOR={estado_motor} | "
            f"Tiempo={formatear_tiempo(tiempo_motor)}"
        )

        if alerta_manual:
            log("⚠️ ALERTA: Motor ENCENDIDO en MANUAL")

        if arranque_pendiente:
            log(f"⏳ Arranque en {int(max(0, restante))}s | Motivo: {ultimo_motivo}")
        else:
            log(f"ℹ️ Motivo último cambio: {ultimo_motivo}")

        time.sleep(CICLO)

    except Exception as e:
        errores_modbus += 1
        log(f"ERROR Modbus ({errores_modbus}): {e}")

        if bomba_encendida:
            ubus_do("0")
            bomba_encendida = False
            ultimo_motivo = "FAIL-SAFE Modbus"
            arranque_pendiente = True
            tiempo_evento = time.time()

        time.sleep(5)
