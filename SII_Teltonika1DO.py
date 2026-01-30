#!/usr/bin/env python3
import time
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"
BAUDRATE = 9600
ID_TANQUE = 32

TIEMPO_REARRANQUE = 300      # segundos
TIEMPO_CICLO = 2             # segundos

# ================= ESTADOS =================

motor_encendido = False
ultimo_motivo = "Sistema iniciado"
en_rearranque = False
tiempo_apagado = None

# ================= MODBUS =================

client = ModbusSerialClient(
    method="rtu",
    port=MODBUS_PORT,
    baudrate=BAUDRATE,
    timeout=1,
    parity="N",
    stopbits=1,
    bytesize=8
)

def conectar():
    if not client.connected:
        return client.connect()
    return True

# ================= SALIDA DIGITAL =================

def encender_motor():
    global motor_encendido, ultimo_motivo
    if motor_encendido:
        return
    motor_encendido = True
    ultimo_motivo = "Arranque permitido"
    print(">> MOTOR ENCENDIDO")

def apagar_motor(motivo):
    global motor_encendido, ultimo_motivo, en_rearranque, tiempo_apagado
    if not motor_encendido:
        return
    motor_encendido = False
    ultimo_motivo = motivo
    en_rearranque = True
    tiempo_apagado = time.time()
    print(f">> MOTOR APAGADO ({motivo})")

# ================= LÓGICA =================

print("Sistema Pozo–Tanque iniciado")

while True:
    try:
        if not conectar():
            raise Exception("No se pudo abrir puerto Modbus")

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

        # Rearranque
        if en_rearranque:
            restante = TIEMPO_REARRANQUE - (ahora - tiempo_apagado)
            if restante <= 0:
                en_rearranque = False
            else:
                print(
                    f"BAJO: {flotador_bajo} | ALTO: {flotador_alto} | "
                    f"MOTOR: {'ENCENDIDO' if motor_encendido else 'APAGADO'} | "
                    f"REARRANQUE: {int(restante)}s | "
                    f"ULTIMO: {ultimo_motivo}"
                )
                time.sleep(TIEMPO_CICLO)
                continue

        # Inconsistencia
        if flotador_alto and not flotador_bajo:
            apagar_motor("Inconsistencia flotadores")

        # Tanque lleno
        elif flotador_bajo and flotador_alto:
            apagar_motor("Tanque lleno")

        # Permitir arranque
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
