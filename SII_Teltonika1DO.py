#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 60        # segundos
INTERVALO_LECTURA = 2          # segundos
MAX_FALLOS_MODBUS = 10

# Teltonika GPIO (ubus)
DO_MOTOR = "ioman.gpio.dio0"   # Control motor/bomba
DI_MOTOR = "ioman.gpio.dio1"   # Estado motor/bomba (informativo)

# ================= ESTADO =================

control_motor = False
motor_estado = False

tiempo_ultimo_apagado = None
fallos_modbus = 0
estado_proceso = "Inicializando"

# ================= UTIL =================

def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

# ================= GPIO =================

def set_motor(valor: bool, motivo=None):
    global control_motor, tiempo_ultimo_apagado

    if control_motor == valor:
        return

    cmd = f"ubus call {DO_MOTOR} update '{{\"value\":\"{1 if valor else 0}\"}}'"
    subprocess.run(cmd, shell=True, check=False)

    control_motor = valor

    if not valor:
        tiempo_ultimo_apagado = time.time()
        if motivo:
            print(f"[{ts()}] 🔴 CONTROL APAGADO → {motivo}")
    else:
        if motivo:
            print(f"[{ts()}] 🟢 CONTROL ENCENDIDO → {motivo}")

def leer_motor_estado():
    try:
        out = subprocess.check_output(
            f"ubus call {DI_MOTOR} status", shell=True
        ).decode()
        return '"value": "1"' in out
    except:
        return motor_estado

# ================= MODBUS =================

def crear_cliente():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        timeout=1
    )

def leer_flotadores(client):
    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        unit=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error lectura flotadores")

    return bool(lectura.bits[0]), bool(lectura.bits[1])

def reiniciar_modbus(client):
    print(f"[{ts()}] 🔄 Reiniciando conexión Modbus RS485...")
    try:
        client.close()
    except:
        pass
    time.sleep(2)
    return crear_cliente()

# ================= INICIO =================

print(f"[{ts()}] 🚀 Sistema Pozo–Tanque iniciado")
client = crear_cliente()

while True:
    try:
        # ===== MODBUS =====
        flotador_bajo, flotador_alto = leer_flotadores(client)
        fallos_modbus = 0

        # ===== ESTADO MOTOR (DI) =====
        motor_estado = leer_motor_estado()
        ahora = time.time()

        # ===== LÓGICA =====
        if flotador_alto and not flotador_bajo:
            estado_proceso = "⚠️ Inconsistencia flotadores"
            if control_motor:
                set_motor(False, "Inconsistencia flotadores")

        elif flotador_alto and flotador_bajo:
            estado_proceso = "🟦 Tanque lleno"
            if control_motor:
                set_motor(False, "Tanque lleno")

        elif not flotador_bajo and not flotador_alto:
            if control_motor:
                estado_proceso = "💧 Llenando tanque"
            else:
                if tiempo_ultimo_apagado is None or \
                   (ahora - tiempo_ultimo_apagado) >= RETARDO_REARRANQUE:
                    estado_proceso = "▶️ Arranque permitido"
                    set_motor(True, "Tanque vacío")
                else:
                    restante = int(
                        RETARDO_REARRANQUE - (ahora - tiempo_ultimo_apagado)
                    )
                    estado_proceso = f"⏳ Esperando rearranque ({restante}s)"

        else:
            estado_proceso = "🟡 Nivel medio"

        # ===== CONSOLA =====
        print(
            f"[{ts()}] "
            f"🟢 Bajo: {flotador_bajo} | "
            f"🔵 Alto: {flotador_alto} | "
            f"🎛️ Control: {'ON' if control_motor else 'OFF'} | "
            f"⚙️ Motor: {'ON' if motor_estado else 'OFF'} | "
            f"{estado_proceso}"
        )

        time.sleep(INTERVALO_LECTURA)

    except Exception as e:
        fallos_modbus += 1
        print(f"[{ts()}] ❌ ERROR Modbus ({fallos_modbus}/{MAX_FALLOS_MODBUS}): {e}")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            estado_proceso = "❌ Falla comunicación Modbus"
            if control_motor:
                set_motor(False, "Falla comunicación Modbus")

            client = reiniciar_modbus(client)
            fallos_modbus = 0

        time.sleep(1)
