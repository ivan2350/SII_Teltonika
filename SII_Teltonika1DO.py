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

# GPIO Teltonika (ubus)
DO_MOTOR = "ioman.gpio.dio0"   # control
DI_MOTOR = "ioman.gpio.dio1"   # estado informativo

# ================= ESTADO =================

control_motor = False
motor_estado = False

ultimo_cambio = None
motivo_ultimo_cambio = None
tiempo_ultimo_apagado = None

fallos_modbus = 0

# ================= FUNCIONES GPIO =================

def set_motor(valor: bool):
    global control_motor, ultimo_cambio, motivo_ultimo_cambio, tiempo_ultimo_apagado

    if control_motor == valor:
        return  # NO repetir comando

    cmd = f"ubus call {DO_MOTOR} update '{{\"value\":\"{1 if valor else 0}\"}}'"
    subprocess.run(cmd, shell=True, check=False)

    control_motor = valor
    ultimo_cambio = time.strftime("%Y-%m-%d %H:%M:%S")

    if not valor:
        tiempo_ultimo_apagado = time.time()

    print(f"🔔 CONTROL MOTOR {'ENCENDIDO' if valor else 'APAGADO'} | Motivo: {motivo_ultimo_cambio}")

def leer_motor_estado():
    try:
        out = subprocess.check_output(
            f"ubus call {DI_MOTOR} status", shell=True
        ).decode()
        return '"value": "1"' in out
    except:
        return motor_estado  # mantiene último valor válido

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

    bajo = bool(lectura.bits[0])
    alto = bool(lectura.bits[1])

    return bajo, alto

def reiniciar_modbus(client):
    print("🔄 Reiniciando conexión Modbus RS485...")
    try:
        client.close()
    except:
        pass
    time.sleep(2)
    return crear_cliente()

# ================= INICIO =================

print("🚀 Sistema Pozo–Tanque iniciado")
client = crear_cliente()

while True:
    try:
        # ===== LEER MODBUS =====
        bajo, alto = leer_flotadores(client)
        fallos_modbus = 0

        # ===== LEER ESTADO MOTOR =====
        motor_estado = leer_motor_estado()

        # ===== MOSTRAR ESTADO =====
        print(
            f"🟢 Flotador BAJO: {bajo} | "
            f"🔵 Flotador ALTO: {alto} | "
            f"⚙️ Motor: {'ENCENDIDO' if motor_estado else 'APAGADO'}"
        )

        ahora = time.time()

        # ===== LÓGICA DE CONTROL =====

        # Inconsistencia
        if alto and not bajo:
            if control_motor:
                motivo_ultimo_cambio = "Inconsistencia flotadores"
                set_motor(False)

        # Tanque lleno
        elif alto and bajo:
            if control_motor:
                motivo_ultimo_cambio = "Tanque lleno"
                set_motor(False)

        # Tanque vacío
        elif not bajo and not alto:
            if not control_motor:
                if tiempo_ultimo_apagado is None or \
                   (ahora - tiempo_ultimo_apagado) >= RETARDO_REARRANQUE:
                    motivo_ultimo_cambio = "Tanque vacío"
                    set_motor(True)
                else:
                    restante = int(
                        RETARDO_REARRANQUE - (ahora - tiempo_ultimo_apagado)
                    )
                    print(f"⏳ Rearranque en {restante}s")

        time.sleep(INTERVALO_LECTURA)

    except Exception as e:
        fallos_modbus += 1
        print(f"❌ ERROR Modbus ({fallos_modbus}/{MAX_FALLOS_MODBUS}): {e}")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            if control_motor:
                motivo_ultimo_cambio = "Falla comunicación Modbus"
                set_motor(False)

            client = reiniciar_modbus(client)
            fallos_modbus = 0

        time.sleep(1)
