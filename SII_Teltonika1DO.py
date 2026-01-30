#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client.serial import ModbusSerialClient

# ==========================================================
# COLORES ANSI
# ==========================================================

RESET = "\033[0m"
BOLD = "\033[1m"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

MODBUS_PORT = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 120
TIEMPO_CICLO = 2

DO_BOMBA = "ioman.gpio.dio0"
DI_MOTOR = "ioman.gpio.dio1"

# ==========================================================
# ESTADOS
# ==========================================================

bomba_encendida = False
ultimo_evento = "Inicio del sistema"
tiempo_ultimo_cambio = 0
rearranque_activo = False

# ==========================================================
# MODBUS
# ==========================================================

client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDIOS,
    timeout=2,
    stopbits=1,
    bytesize=8,
    parity="N"
)

# ==========================================================
# HARDWARE
# ==========================================================

def set_bomba(encender: bool, motivo: str):
    global bomba_encendida, ultimo_evento, tiempo_ultimo_cambio, rearranque_activo

    if encender == bomba_encendida:
        return

    valor = "1" if encender else "0"
    subprocess.call([
        "ubus", "call", DO_BOMBA, "update",
        f'{{"value":"{valor}"}}'
    ])

    bomba_encendida = encender
    ultimo_evento = motivo
    tiempo_ultimo_cambio = time.time()
    rearranque_activo = not encender


def leer_motor():
    try:
        salida = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            text=True
        )
        return '"value": "1"' in salida
    except:
        return None


def leer_flotadores():
    if not client.connect():
        raise Exception("RS485 no disponible")

    lectura = client.read_discrete_inputs(
        address=0,
        count=2,
        device_id=ID_TANQUE
    )

    if lectura.isError():
        raise Exception("Error Modbus flotadores")

    return lectura.bits[0], lectura.bits[1]

# ==========================================================
# UI
# ==========================================================

def encabezado():
    print("\n" + BOLD + CYAN + "=" * 78 + RESET)
    print(BOLD + CYAN + "  SISTEMA POZO – TANQUE | TELTONIKA TRB145" + RESET)
    print(GRAY + "  RS485 · Flotadores · DO Bomba · DI Motor" + RESET)
    print(BOLD + CYAN + "=" * 78 + RESET)
    print(
        f"{BOLD}Hora     Bajo   Alto   Motor     Bomba     Estado{RESET}"
    )
    print(GRAY + "-" * 78 + RESET)


def icono_bool(valor):
    return f"{GREEN}✔{RESET}" if valor else f"{RED}✖{RESET}"


def icono_bomba():
    if bomba_encendida:
        return f"{GREEN}🟢 ON {RESET}"
    return f"{RED}🔴 OFF{RESET}"


def icono_motor(valor):
    if valor is None:
        return f"{GRAY}?{RESET}"
    return f"{GREEN}ON{RESET}" if valor else f"{RED}OFF{RESET}"


def log_estado(bajo, alto, motor, estado):
    print(
        f"{GRAY}{time.strftime('%H:%M:%S')}{RESET}   "
        f"{icono_bool(bajo):<6} "
        f"{icono_bool(alto):<6} "
        f"{icono_motor(motor):<9} "
        f"{icono_bomba():<10} "
        f"{estado}"
    )

# ==========================================================
# MAIN
# ==========================================================

encabezado()

while True:
    try:
        bajo, alto = leer_flotadores()
        motor = leer_motor()

        ahora = time.time()
        restante = max(
            0,
            RETARDO_REARRANQUE - (ahora - tiempo_ultimo_cambio)
        )

        if alto and not bajo:
            if bomba_encendida:
                set_bomba(False, "⚠ Inconsistencia flotadores")
            estado = f"{RED}⚠ INCONSISTENCIA{RESET}"

        elif bajo and alto:
            if bomba_encendida:
                set_bomba(False, "🛑 Tanque lleno")
            estado = f"{RED}🛑 TANQUE LLENO{RESET}"

        elif not bajo and not alto:
            if not bomba_encendida:
                if rearranque_activo and restante > 0:
                    estado = f"{YELLOW}⏳ Rearranque {int(restante)}s{RESET}"
                else:
                    set_bomba(True, "▶ Tanque vacío")
                    estado = f"{GREEN}▶ ARRANQUE{RESET}"
            else:
                estado = f"{GREEN}✔ OPERANDO{RESET}"

        else:
            estado = f"{BLUE}… TRANSICIÓN{RESET}"

        log_estado(bajo, alto, motor, estado)

    except Exception as e:
        if bomba_encendida:
            set_bomba(False, "⚠ Fail-safe comunicación")
        print(f"{RED}{time.strftime('%H:%M:%S')}  ERROR: {e}{RESET}")

    time.sleep(TIEMPO_CICLO)
