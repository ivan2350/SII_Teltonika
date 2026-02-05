#!/usr/bin/env python3
import time
import subprocess
from datetime import datetime
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================
MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120
MAX_ERRORES_MODBUS = 10
INTERVALO = 1

# =========================================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDRATE,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

# ========== ESTADOS ==========
control_motor = False          # DIO0
tiempo_apagado = None          # SOLO cuando se apaga
motivo_ultimo_evento = "Inicio del sistema"
errores_modbus = 0
# =============================

# ---------- UBUS -------------
def set_motor(valor: bool):
    v = "1" if valor else "0"
    subprocess.run(
        ["ubus", "call", "ioman.gpio.dio0", "update", f'{{"value":"{v}"}}'],
        check=False
    )

def leer_motor_DI():
    try:
        r = subprocess.check_output(
            ["ubus", "call", "ioman.gpio.dio1", "status"],
            text=True
        )
        return '"value": "1"' in r
    except Exception:
        return False
# -----------------------------

# ---------- MODBUS ----------
def leer_flotadores():
    global errores_modbus

    if not client.connect():
        errores_modbus += 1
        return None

    r = client.read_discrete_inputs(0, 2, device_id=ID_TANQUE)

    if r.isError():
        errores_modbus += 1
        return None

    errores_modbus = 0
    return r.bits[0], r.bits[1]
# ----------------------------

# -------- CONTROL ----------
def encender_motor(motivo):
    global control_motor, motivo_ultimo_evento
    if not control_motor:
        set_motor(True)
        control_motor = True
        motivo_ultimo_evento = motivo

def apagar_motor(motivo):
    global control_motor, tiempo_apagado, motivo_ultimo_evento
    if control_motor:
        set_motor(False)
        control_motor = False
        tiempo_apagado = time.time()   # ⬅️ AQUÍ inicia el rearranque
        motivo_ultimo_evento = motivo

def tiempo_rearranque_restante():
    if control_motor or tiempo_apagado is None:
        return 0
    restante = RETARDO_REARRANQUE - (time.time() - tiempo_apagado)
    return max(0, int(restante))
# ----------------------------

# -------- LOG --------------
def imprimir_estado(bajo, alto, motor_di):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "-"*55)
    print(f"[{ts}] Sistema Pozo–Tanque")
    print(f"Flotadores → Bajo:{int(bajo)} | Alto:{int(alto)}")
    print(f"Control motor (DIO0): {'ENCENDIDO' if control_motor else 'APAGADO'}")
    print(f"Estado motor  (DIO1): {'ENCENDIDO' if motor_di else 'APAGADO'}")

    if not control_motor and motor_di:
        print("⚠ Motor encendido manualmente")

    if not control_motor and tiempo_rearranque_restante() > 0:
        print(f"⏳ Rearranque en {tiempo_rearranque_restante()} s")

    print(f"Motivo último evento: {motivo_ultimo_evento}")
    print("-"*55)
# ----------------------------

print("🚀 Sistema Pozo–Tanque iniciado")

while True:
    flot = leer_flotadores()

    if flot is None:
        if errores_modbus >= MAX_ERRORES_MODBUS:
            apagar_motor("Falla comunicación Modbus")
        time.sleep(INTERVALO)
        continue

    bajo, alto = flot
    motor_di = leer_motor_DI()

    # Inconsistencia
    if alto and not bajo:
        apagar_motor("Inconsistencia flotadores")

    # Tanque lleno
    elif bajo and alto:
        apagar_motor("Tanque lleno")

    # Tanque vacío
    elif not bajo and not alto:
        if not control_motor and tiempo_rearranque_restante() == 0:
            encender_motor("Tanque vacío")

    imprimir_estado(bajo, alto, motor_di)
    time.sleep(INTERVALO)
