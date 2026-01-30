#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"
BAUDRATE = 9600
ID_TANQUE = 32

TIEMPO_REARRANQUE = 300   # segundos
TIEMPO_CICLO = 2

# ================= ESTADOS =================

motor_encendido = False
ultimo_motivo = "Sistema iniciado"
en_rearranque = False
inicio_rearranque = None

# ================= MODBUS =================

client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=BAUDRATE,
    timeout=1
)

def conectar():
    if not client.connected:
        return client.connect()
    return True

# ================= CONTROL MOTOR =================

def encender_motor():
    global motor_encendido, ultimo_motivo
    if motor_encendido:
        return
    motor_encendido = True
    ultimo_motivo = "Arranque permitido"
    print(">> CONTROL: MOTOR ENCENDIDO")

def apagar_motor(motivo):
    global motor_encendido, ultimo_motivo, en_rearranque, inicio_rearranque
    if not motor_encendido:
        return
    motor_encendido = False
    ultimo_motivo = motivo
    en_rearranque = True
    inicio_rearranque = time.time()
    print(f">> CONTROL: MOTOR APAGADO ({motivo})")

# ================= SISTEMA =================

print("Sistema Pozo–Tanque iniciado")

while True:
    try:
        if not conectar():
            raise Exception("No conecta Modbus")

        lectura = client.read_discrete_inputs(
            address=0,
            count=2,
            slave=ID_TANQUE
        )

        if lectura.isError():
            raise Exception("Error lectura flotadores")

        flotador_bajo = lectura.bits[0]
        flotador_alto = lectura.bits[1]

        ahora = time.time()

        # ================= REARRANQUE =================
        if en_rearranque:
            transcurrido = ahora - inicio_rearranque
            restante = TIEMPO_REARRANQUE - transcurrido

            if restante <= 0:
                en_rearranque = False
            else:
                print(
                    f"BAJO: {flotador_bajo} | ALTO: {flotador_alto} | "
                    f"MOTOR: APAGADO | "
                    f"REARRANQUE: {int(restante)}s | "
                    f"ULTIMO: {ultimo_motivo}"
                )
                time.sleep(TIEMPO_CICLO)
                continue

        # ================= LÓGICA =================

        # Inconsistencia
        if flotador_alto and not flotador_bajo:
            apagar_motor("Inconsistencia flotadores")

        # Tanque lleno
        elif flotador_bajo and flotador_alto:
            apagar_motor("Tanque lleno")

        # Condición de arranque
        elif not flotador_bajo and not flotador_alto:
            encender_motor()

        print(
            f"BAJO: {flotador_bajo} | ALTO: {flotador_alto} | "
            f"MOTOR: {'ENCENDIDO' if motor_encendido else 'APAGADO'} | "
            f"ULTIMO: {ultimo_motivo}"
        )

    except Exception as e:
        print(f"ERROR: {e}")

    time.sleep(TIEMPO_CICLO)
