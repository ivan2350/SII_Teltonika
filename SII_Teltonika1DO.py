#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

PUERTO_RS485 = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

REARRANQUE_SEG = 300  # 5 minutos

# GPIO Teltonika (AJUSTA SI ES NECESARIO)
GPIO_MOTOR_DI = "/sys/class/gpio/gpio1/value"   # Estado real del motor
GPIO_MOTOR_DO = "/sys/class/gpio/gpio0/value"   # Relay bomba

# =================================================

def leer_gpio(path):
    with open(path, "r") as f:
        return f.read().strip() == "1"

def escribir_gpio(path, valor):
    with open(path, "w") as f:
        f.write("1" if valor else "0")

def leer_DI_motor():
    return leer_gpio(GPIO_MOTOR_DI)

def motor_encender():
    escribir_gpio(GPIO_MOTOR_DO, True)

def motor_apagar():
    escribir_gpio(GPIO_MOTOR_DO, False)

def conectar(client):
    if not client.connect():
        return False
    return True

# ================= MODBUS =================

client = ModbusSerialClient(
    method="rtu",
    port=PUERTO_RS485,
    baudrate=BAUDIOS,
    timeout=2
)

# ================= ESTADOS =================

motor_DO = False
ultimo_motivo = "—"
en_rearranque = False
fin_rearranque = 0

print("🚀 Sistema Pozo–Tanque iniciado")

# ================= LOOP PRINCIPAL =================

while True:
    try:
        if not conectar(client):
            raise Exception("No conecta Modbus")

        lectura = client.read_discrete_inputs(
            address=0,
            count=2,
            device_id=ID_TANQUE
        )

        if lectura.isError():
            raise Exception("Error lectura flotadores")

        flotador_bajo = lectura.bits[0]
        flotador_alto = lectura.bits[1]

        motor_DI = leer_DI_motor()
        ahora = time.time()

        # ================= ESTADO MANUAL =================
        if not motor_DO and motor_DI:
            estado_manual = "⚠️ MANUAL ACTIVO"
        else:
            estado_manual = "OK"

        # ================= REARRANQUE =================
        if en_rearranque:
            restante = int(fin_rearranque - ahora)
            if restante <= 0:
                en_rearranque = False
            else:
                print(
                    f"⏳ REARRANQUE {restante}s | "
                    f"Bajo:{flotador_bajo} Alto:{flotador_alto} | "
                    f"Motor DI:{motor_DI} | Motivo:{ultimo_motivo}"
                )
                time.sleep(1)
                continue

        # ================= LÓGICA AUTOMÁTICA =================

        # Inconsistencia
        if flotador_alto and not flotador_bajo:
            if motor_DO:
                motor_apagar()
                motor_DO = False
                ultimo_motivo = "Inconsistencia flotadores"
                en_rearranque = True
                fin_rearranque = ahora + REARRANQUE_SEG

        # Tanque lleno
        elif flotador_bajo and flotador_alto:
            if motor_DO:
                motor_apagar()
                motor_DO = False
                ultimo_motivo = "Tanque lleno"
                en_rearranque = True
                fin_rearranque = ahora + REARRANQUE_SEG

        # Tanque bajo
        elif not flotador_bajo and not flotador_alto:
            if not motor_DO:
                motor_encender()
                motor_DO = True
                ultimo_motivo = "Nivel bajo"

        # ================= CONSOLA =================

        print(
            f"Bajo:{flotador_bajo} | Alto:{flotador_alto} | "
            f"Motor DO:{motor_DO} | Motor DI:{motor_DI} | "
            f"Estado:{estado_manual} | Motivo:{ultimo_motivo}"
        )

        time.sleep(1)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        if motor_DO:
            motor_apagar()
            motor_DO = False
            ultimo_motivo = "Fail-safe"
        time.sleep(2)
