#!/usr/bin/env python3
import time
import json
import subprocess
from pymodbus.client.sync import ModbusSerialClient

# ================= CONFIGURACIÓN =================
MODBUS_PORT = "/dev/ttyHS0"
BAUDIOS = 9600
ID_TANQUE = 32

TIEMPO_ESPERA_CICLO = 5        # segundos entre chequeos
RETARDO_ARRANQUE = 10           # segundos antes de encender bomba

# ================= FUNCIONES =================

def iniciar_cliente():
    return ModbusSerialClient(
        method='rtu',
        port=MODBUS_PORT,
        baudrate=BAUDIOS,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2,
        retries=2,
        handle_local_echo=False
    )

def conectar(client):
    if not client.connected:
        return client.connect()
    return True

def reiniciar_conexion(client):
    print("🔄 Reiniciando puerto Modbus...")
    try:
        client.close()
    except:
        pass
    time.sleep(2)
    client = iniciar_cliente()
    conectar(client)
    return client

def set_bomba(valor: str):
    """Control de salida digital dio0"""
    try:
        subprocess.run(
            ["ubus", "call", "ioman.gpio.dio0", "update", f'{{"value":"{valor}"}}'],
            check=True
        )
    except Exception as e:
        print(f"[ERROR] accion bomba: {e}")

def leer_estado_motor():
    """Lee el estado real del motor desde entrada digital dio1"""
    try:
        resultado = subprocess.run(
            ["ubus", "call", "ioman.gpio.dio1", "status"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(resultado.stdout)
        valor = data.get("value", "0")
        return valor == "1"
    except:
        return False

# ================= LÓGICA PRINCIPAL =================

def control_pozo():
    client = iniciar_cliente()
    conectar(client)

    bomba_encendida = False
    arranque_pendiente = False
    tiempo_arranque = 0
    motivo_ultimo_cambio = "Sistema iniciado"
    errores_consecutivos = 0

    print("\n🚰 Sistema Pozo–Tanque iniciado\n")

    while True:
        try:
            if not conectar(client):
                raise Exception("Puerto serial no disponible")

            # Lectura de flotadores por Modbus
            lectura = client.read_discrete_inputs(address=0, count=2, unit=ID_TANQUE)
            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores_consecutivos = 0

            bajo = lectura.bits[0]
            alto = lectura.bits[1]
            motor_estado = leer_estado_motor()

            # ================= LOGICA DE CONTROL =================

            # Tanque vacío → programar arranque
            if not bajo and not alto and not bomba_encendida and not arranque_pendiente:
                arranque_pendiente = True
                tiempo_arranque = time.time()
                print(f"[INFO] Arranque programado en {RETARDO_ARRANQUE}s")

            # Rearranque
            if arranque_pendiente:
                if bajo or alto:
                    print("[INFO] Arranque cancelado (nivel cambió)")
                    arranque_pendiente = False
                elif time.time() - tiempo_arranque >= RETARDO_ARRANQUE:
                    set_bomba("1")
                    bomba_encendida = True
                    motivo_ultimo_cambio = "Tanque vacío → ENCENDIENDO bomba"
                    arranque_pendiente = False

            # Tanque lleno
            if bajo and alto and bomba_encendida:
                set_bomba("0")
                bomba_encendida = False
                motivo_ultimo_cambio = "Tanque lleno → APAGANDO bomba"

            # Estado inválido flotadores
            if not bajo and alto and bomba_encendida:
                set_bomba("0")
                bomba_encendida = False
                motivo_ultimo_cambio = "Inconsistencia flotadores → APAGANDO bomba"

            # ================= IMPRESIÓN EN CONSOLA =================
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Flotador BAJO: {bajo} | Flotador ALTO: {alto} | "
                  f"Motor: {motor_estado} | Bomba: {bomba_encendida} | "
                  f"Motivo: {motivo_ultimo_cambio}")

            time.sleep(TIEMPO_ESPERA_CICLO)

        except Exception as e:
            errores_consecutivos += 1
            print(f"[ERROR {errores_consecutivos}] {e}")
            set_bomba("0")  # FAIL-SAFE
            motivo_ultimo_cambio = "ERROR → FAIL-SAFE"
            if errores_consecutivos >= 5:
                client = reiniciar_conexion(client)
                errores_consecutivos = 0
            time.sleep(5)

# ================= EJECUCIÓN =================

if __name__ == "__main__":
    try:
        control_pozo()
    except KeyboardInterrupt:
        print("\n[INFO] Programa detenido manualmente")
