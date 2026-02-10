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
INTERVALO_ERROR = 2
INTERVALO_DIAG = 2

RETARDO_REARRANQUE = 180
MAX_FALLOS_MODBUS = 30

TIEMPO_DIAGNOSTICO = 180   # 1 hora
POLL_BOTON = 1             # segundos (muestreo DI)

# GPIO Teltonika
DO_MOTOR = "ioman.gpio.dio0"   # Control bomba
DI_DIAG = "ioman.gpio.dio1"    # Interruptor diagnóstico

# ================= ESTADO =================

control_motor = False
tiempo_ultimo_apagado = None
fallos_modbus = 0
estado_proceso = "Inicializando"

modo_diag_activo = False
tiempo_diag_inicio = None

estado_diag_anterior = False   # para detectar flanco OFF->ON

intervalo_actual = INTERVALO_NORMAL

# ================= UTIL =================

def ts():
    return time.strftime("%d-%m-%Y %H:%M:%S")

def tiempo_restante_diag():
    if not modo_diag_activo or tiempo_diag_inicio is None:
        return None

    restante = int(TIEMPO_DIAGNOSTICO - (time.time() - tiempo_diag_inicio))
    if restante < 0:
        restante = 0

    minutos = restante // 60
    segundos = restante % 60
    return f"{minutos}m {segundos}s"

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

def leer_interruptor_diag():
    try:
        out = subprocess.check_output(
            f"ubus call {DI_DIAG} status", shell=True
        ).decode()
        return '"value": "1"' in out
    except:
        return False

def procesar_interruptor_diagnostico():
    """
    Detecta SOLO flanco OFF -> ON
    - Activa diagnóstico una sola vez
    - Ignora si el interruptor se queda en ON
    - Rompe el sleep para aplicar diagnóstico inmediato
    """
    global modo_diag_activo, tiempo_diag_inicio, estado_diag_anterior

    estado_actual = leer_interruptor_diag()

    # Flanco OFF -> ON
    if (not estado_diag_anterior) and estado_actual:
        if not modo_diag_activo:
            modo_diag_activo = True
            tiempo_diag_inicio = time.time()
            print(f"[{ts()}] 🧪 MODO DIAGNÓSTICO ACTIVADO (1 hora)")
            estado_diag_anterior = estado_actual
            return True  # activar de inmediato

    estado_diag_anterior = estado_actual
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

print(f"[{ts()}] 🚀 Sistema Pozo–Tanque iniciado (diagnóstico por interruptor)")
client = crear_cliente()

while True:
    try:
        ahora = time.time()

        # ===== CONTROL TIEMPO DIAGNÓSTICO =====
        if modo_diag_activo:
            if (ahora - tiempo_diag_inicio) >= TIEMPO_DIAGNOSTICO:
                modo_diag_activo = False
                tiempo_diag_inicio = None
                print(f"[{ts()}] 🟢 MODO DIAGNÓSTICO FINALIZADO")

        intervalo_actual = INTERVALO_DIAG if modo_diag_activo else INTERVALO_NORMAL

        # ===== MODBUS =====
        flotador_bajo, flotador_alto = leer_flotadores(client)
        fallos_modbus = 0

        # ===== LÓGICA DEL TANQUE (SIN CAMBIOS) =====
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
        restante_diag = tiempo_restante_diag()

        print(
            f"[{ts()}] "
            f"🟢 Bajo: {flotador_bajo} | "
            f"🔵 Alto: {flotador_alto} | "
            f"🎛️ Bomba: {'ON' if control_motor else 'OFF'} | "
            f"🧪 Diagnóstico: "
            f"{'ON (' + restante_diag + ' restantes)' if restante_diag else 'OFF'} | "
            f"{estado_proceso}"
        )

        # ===== SLEEP FRAGMENTADO (respuesta inmediata) =====
        tiempo_dormido = 0
        while tiempo_dormido < intervalo_actual:
            if procesar_interruptor_diagnostico():
                break  # salir y aplicar diagnóstico YA

            time.sleep(POLL_BOTON)
            tiempo_dormido += POLL_BOTON

    except Exception:
        fallos_modbus += 1
        intervalo_actual = INTERVALO_ERROR

        print(f"[{ts()}] ❌ ERROR Modbus ({fallos_modbus}/{MAX_FALLOS_MODBUS})")

        if fallos_modbus >= MAX_FALLOS_MODBUS:
            set_motor(False, "Falla comunicación Modbus")
            client = reiniciar_modbus(client)
            fallos_modbus = 0

        time.sleep(intervalo_actual)
