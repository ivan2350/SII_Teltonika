#!/usr/bin/env python3
import time
import subprocess
from datetime import datetime
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================
MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120      # segundos
MAX_ERRORES_MODBUS = 10
INTERVALO_LECTURA = 1         # segundos

# =========================================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDRATE,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

# ====== ESTADOS ======
control_motor = False
ultimo_cambio = None
motivo_ultimo_cambio = "Inicio del sistema"
errores_modbus = 0

# ==================== UBUS ====================

def ubus_set_dio0(valor: bool):
    v = "1" if valor else "0"
    subprocess.run(
        ["ubus", "call", "ioman.gpio.dio0", "update", f'{{"value":"{v}"}}'],
        check=False
    )

def leer_dio1():
    try:
        r = subprocess.check_output(
            ["ubus", "call", "ioman.gpio.dio1", "status"],
            text=True
        )
        return '"value": "1"' in r
    except Exception:
        return False

# ================= MODBUS ====================

def leer_flotadores():
    global errores_modbus

    if not client.connect():
        errores_modbus += 1
        return None

    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        errores_modbus += 1
        return None

    errores_modbus = 0
    return lectura.bits[0], lectura.bits[1]

# ================= CONTROL ===================

def encender_motor(motivo):
    global control_motor, ultimo_cambio, motivo_ultimo_cambio
    if not control_motor:
        ubus_set_dio0(True)
        control_motor = True
        ultimo_cambio = time.time()
        motivo_ultimo_cambio = motivo

def apagar_motor(motivo):
    global control_motor, ultimo_cambio, motivo_ultimo_cambio
    if control_motor:
        ubus_set_dio0(False)
        control_motor = False
        ultimo_cambio = time.time()
        motivo_ultimo_cambio = motivo

def tiempo_rearranque_restante():
    if ultimo_cambio is None:
        return 0
    t = RETARDO_REARRANQUE - (time.time() - ultimo_cambio)
    return max(0, int(t))

# ================= CONSOLA ===================

def log_estado(bajo, alto, estado_motor):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "="*55)
    print(f"[{ts}] Sistema Pozo–Tanque")
    print(f"Flotadores → Bajo: {int(bajo)} | Alto: {int(alto)}")
    print(f"Control motor (DIO0): {'ENCENDIDO' if control_motor else 'APAGADO'}")
    print(f"Estado motor  (DIO1): {'ENCENDIDO' if estado_motor else 'APAGADO'}")

    if not control_motor and estado_motor:
        print("⚠ Motor encendido manualmente")

    if tiempo_rearranque_restante() > 0:
        print(f"⏳ Rearranque en: {tiempo_rearranque_restante()} s")

    print(f"Motivo último evento: {motivo_ultimo_cambio}")
    print("="*55)

# ================= MAIN ======================

print("🚀 Sistema Pozo–Tanque iniciado")

while True:
    flotadores = leer_flotadores()

    if flotadores is None:
        if errores_modbus >= MAX_ERRORES_MODBUS:
            apagar_motor("Falla comunicación Modbus")
        time.sleep(INTERVALO_LECTURA)
        continue

    bajo, alto = flotadores
    estado_motor = leer_dio1()

    # --- INCONSISTENCIA ---
    if alto and not bajo:
        apagar_motor("Inconsistencia flotadores")

    # --- TANQUE LLENO ---
    elif bajo and alto:
        apagar_motor("Tanque lleno")

    # --- TANQUE VACÍO ---
    elif not bajo and not alto:
        if not control_motor and tiempo_rearranque_restante() == 0:
            encender_motor("Tanque vacío")

    log_estado(bajo, alto, estado_motor)
    time.sleep(INTERVALO_LECTURA)
