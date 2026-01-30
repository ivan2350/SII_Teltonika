#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client.serial import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120  # segundos
CICLO = 2  # segundos

# DO y DI Teltonika
DO_BOMBA = "ioman.gpio.dio0"
DI_MOTOR = "ioman.gpio.dio1"

# ================= ESTADOS =================

bomba_encendida = False
ultimo_evento = "Inicio"
tiempo_ultimo_cambio = 0
rearranque_activo = False

# ================= MODBUS =================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDIOS,
    timeout=2,
    stopbits=1,
    bytesize=8,
    parity="N"
)

# ================= FUNCIONES =================

def set_bomba(encender: bool, motivo: str):
    global bomba_encendida, ultimo_evento, tiempo_ultimo_cambio, rearranque_activo

    if encender == bomba_encendida:
        return  # No repetir orden

    valor = "1" if encender else "0"
    subprocess.call([
        "ubus", "call", DO_BOMBA, "update",
        f'{{"value":"{valor}"}}'
    ])

    bomba_encendida = encender
    ultimo_evento = motivo
    tiempo_ultimo_cambio = time.time()
    rearranque_activo = not encender

    estado = "ENCENDIDA" if encender else "APAGADA"
    print(f"🔌 Bomba {estado} → {motivo}")

def leer_motor():
    try:
        r = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            text=True
        )
        return '"value": "1"' in r
    except:
        return None

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

# ================= MAIN =================

print("Sistema Pozo–Tanque iniciado\n")

while True:
    try:
        bajo, alto = leer_flotadores()
        motor = leer_motor()

        ahora = time.time()
        restante = max(0, RETARDO_REARRANQUE - (ahora - tiempo_ultimo_cambio))

        # ================= LÓGICA =================

        # INCONSISTENCIA
        if alto and not bajo:
            if bomba_encendida:
                set_bomba(False, "Inconsistencia flotadores")
            accion = "INCONSISTENCIA"

        # TANQUE LLENO
        elif bajo and alto:
            if bomba_encendida:
                set_bomba(False, "Tanque lleno")
            accion = "TANQUE LLENO"

        # TANQUE VACÍO
        elif not bajo and not alto:
            if not bomba_encendida:
                if rearranque_activo and restante > 0:
                    accion = f"Rearranque en {int(restante)} s"
                else:
                    set_bomba(True, "Tanque vacío")
                    accion = "ARRANQUE"
            else:
                accion = "OPERANDO"

        else:
            accion = "ESTADO INTERMEDIO"

        # ================= LOG =================

        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"Bajo:{bajo} Alto:{alto} | "
            f"Motor:{motor} | "
            f"Bomba:{'ON' if bomba_encendida else 'OFF'} | "
            f"{accion} | Último: {ultimo_evento}"
        )

    except Exception as e:
        print(f"❌ ERROR: {e}")
        if bomba_encendida:
            set_bomba(False, "Fail-safe Modbus")

    time.sleep(CICLO)
