#!/usr/bin/env python3
import time
import json
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================

MODBUS_PORT = "/dev/rs485"
BAUDIOS = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 60      # segundos
MAX_FALLOS_FLOTADORES = 10
INTERVALO_LECTURA = 1        # segundos

# ==========================================

bomba_encendida = False
ultimo_control = None
motivo_ultimo = "Inicio sistema"
tiempo_ultimo_control = time.time()

fallos_flotadores = 0

# ================ FUNCIONES =================

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def set_bomba(encender):
    global bomba_encendida, ultimo_control, motivo_ultimo, tiempo_ultimo_control

    if encender and bomba_encendida:
        return
    if not encender and not bomba_encendida:
        return

    valor = "1" if encender else "0"

    subprocess.check_call([
        "ubus", "call",
        "ioman.gpio.dio0",
        "update",
        json.dumps({"value": valor})
    ])

    bomba_encendida = encender
    ultimo_control = "ENCENDIDO" if encender else "APAGADO"
    tiempo_ultimo_control = time.time()

def leer_motor_DI():
    try:
        salida = subprocess.check_output([
            "ubus", "call",
            "ioman.gpio.dio1",
            "status"
        ]).decode()

        data = json.loads(salida)
        return data.get("value") == "1"

    except:
        return False

def leer_flotadores(client):
    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error lectura flotadores")

    return lectura.bits[0], lectura.bits[1]

# ================ MAIN =================

log("🚀 Sistema Pozo–Tanque iniciado")

client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=BAUDIOS,
    timeout=1
)

while True:
    try:
        if not client.connect():
            raise Exception("No conecta Modbus")

        try:
            flot_bajo, flot_alto = leer_flotadores(client)
            fallos_flotadores = 0

        except Exception as e:
            fallos_flotadores += 1
            log(f"⚠ Error flotadores ({fallos_flotadores}/{MAX_FALLOS_FLOTADORES})")

            if fallos_flotadores >= MAX_FALLOS_FLOTADORES:
                motivo_ultimo = "Falla comunicación flotadores"
                set_bomba(False)
                log("🚨 FAIL-SAFE → Bomba APAGADA")
            time.sleep(INTERVALO_LECTURA)
            continue

        motor_DI = leer_motor_DI()

        tiempo_restante = max(
            0,
            RETARDO_REARRANQUE - int(time.time() - tiempo_ultimo_control)
        )

        log(
            f"Flotadores → Bajo:{flot_bajo} Alto:{flot_alto} | "
            f"Motor DI:{'ON' if motor_DI else 'OFF'} | "
            f"Bomba:{'ON' if bomba_encendida else 'OFF'} | "
            f"Rearranque:{tiempo_restante}s | "
            f"Motivo:{motivo_ultimo}"
        )

        # ---------- LOGICA ----------

        # Inconsistencia
        if flot_alto and not flot_bajo:
            motivo_ultimo = "Inconsistencia flotadores"
            set_bomba(False)

        # Tanque lleno
        elif flot_bajo and flot_alto:
            motivo_ultimo = "Tanque lleno"
            set_bomba(False)

        # Tanque vacío
        elif not flot_bajo and not flot_alto:
            if not bomba_encendida and tiempo_restante == 0:
                motivo_ultimo = "Tanque vacío"
                set_bomba(True)

        time.sleep(INTERVALO_LECTURA)

    except KeyboardInterrupt:
        log("🛑 Programa detenido manualmente")
        break

    except Exception as e:
        log(f"❌ ERROR GENERAL: {e}")
        time.sleep(INTERVALO_LECTURA)
