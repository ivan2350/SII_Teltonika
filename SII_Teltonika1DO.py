#este programa es para usar solo 1 2+2+2 en el tanque, utilizando la DOI0 como control y la DOI1 como estado del motor/bomba

#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/rs485"
BAUDRATE = 9600
ID_TANQUE = 32

INTERVALO_NORMAL = 60
INTERVALO_ERROR = 5
INTERVALO_DIAG = 5

RETARDO_REARRANQUE = 180
MAX_FALLOS_MODBUS = 30

TIEMPO_DIAGNOSTICO = 3600   # 1 hora

# GPIO Teltonika
DO_MOTOR = "ioman.gpio.dio0"   # Control bomba
DI_DIAG = "ioman.gpio.dio1"    # Push-button diagnóstico

# ================= ESTADO =================

control_motor = False
tiempo_ultimo_apagado = None
fallos_modbus = 0
estado_proceso = "Inicializando"

modo_diag_activo = False
tiempo_diag_inicio = None

intervalo_actual = INTERVALO_NORMAL

# ================= UTIL =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

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
            print(f"[{ts()}] 🔴 BOMBA APAGADA → {motivo}")
    else:
        if motivo:
            print(f"[{ts()}] 🟢 BOMBA ENCENDIDA → {motivo}")

def leer_push_diagnostico():
    try:
        out = subprocess.check_output(
            f"ubus call {DI_DIAG} status", shell=True
        ).decode()
        return '"value": "1"' in out
    except:
        return False

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
    print(f"[{ts()}] 🔄 Reiniciando Modbus RS485...")
    try:
        client.close()
    except:
        pass
    time.sleep(2)
    return crear_cliente()

# ================= INICIO =================

print(f"[{ts()}] 🚀 Sistema Pozo–Tanque iniciado (diagnóstico por push-button)")
client = crear_cliente()

while True:
    try:
        ahora = time.time()

        # ===== PUSH-BUTTON DIAGNÓSTICO =====
        if leer_push_diagnostico():
            modo_diag_activo = True
            tiempo_diag_inicio = ahora
            print(f"[{ts()}] 🧪 MODO DIAGNÓSTICO ACTIVADO (1 hora)")

        # ===== CONTROL DE TIEMPO DIAGNÓSTICO =====
        if modo_diag_activo:
            if (ahora - tiempo_diag_inicio) < TIEMPO_DIAGNOSTICO:
                intervalo_actual = INTERVALO_DIAG
            else:
                modo_diag_activo = False
                tiempo_diag_inicio = None
                intervalo_actual = INTERVALO_NORMAL
                print(f"[{ts()}] 🟢 MODO DIAGNÓSTICO FINALIZADO")
        else:
            intervalo_actual = INTERVALO_NORMAL

        # ===== MODBUS =====
        flotador_bajo, flotador_alto = leer_flotadores(client)
        fallos_modbus = 0

        # ===== LÓGICA (IGUAL A LA ORIGINAL) =====
        if flotador_alto and not flotador_bajo:
            estado_proceso = "⚠️ Inconsistencia flotadores"
            set_motor(False, "Inconsistencia flotadores")

        elif flotador_alto and flotador_bajo:
            estado_proceso = "🟦 Tanque lleno"
            set_motor(False, "Tanque lleno")

        elif not flotador_bajo and not flotador_alto:
            if not control_motor:
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
                estado_proceso = "💧 Llenando tanque"

        else:
            estado_proceso = "🟡 Nivel medio"

        # ===== CONSOLA =====
        print(
            f"[{ts()}] "
            f"🟢 Bajo: {flotador_bajo} | "
            f"🔵 Alto: {flotador_alto} | "
            f"🎛️ Bomba: {'ON' if control_motor else 'OFF'} | "
            f"🧪 Diagnóstico: {'ON' if modo_diag_activo else 'OFF'} | "
            f"{estado_proceso}"
        )

        time.sleep(intervalo_actual)

    except Exception:
        fallos_modbus += 1
        intervalo_actual = INTERVALO_ERROR

        print(
            f"[{ts()}] ❌ ERROR Modbus ({fallos_modbus}/{MAX_FALLOS_MODBUS})"
        )

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            set_motor(False, "Falla comunicación Modbus")
            client = reiniciar_modbus(client)
            fallos_modbus = 0

        time.sleep(intervalo_actual)
