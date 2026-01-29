#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIG =================
MODBUS_PORT = "/dev/ttyHS0"
BAUDRATE = 9600
MODBUS_SLAVE = 32

RETARDO_ARRANQUE = 60        # segundos
CICLO_LECTURA = 2            # segundos
TIMEOUT_MODBUS = 2
REINTENTO_ERROR = 10
MAX_ERRORES = 5

DO_BOMBA = "ioman.gpio.dio0"
DI_MOTOR = "ioman.gpio.dio1"

# ================= FUNCIONES =================
def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def iniciar_modbus():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=TIMEOUT_MODBUS
    )

def set_bomba(valor):
    try:
        subprocess.run(
            ["ubus", "call", DO_BOMBA, "update", f'{{"value":"{valor}"}}'],
            check=True
        )
    except Exception as e:
        log(f"ERROR control bomba: {e}")

def get_estado_motor():
    try:
        r = subprocess.check_output(
            ["ubus", "call", DI_MOTOR, "status"],
            text=True
        )
        return '"value": "1"' in r
    except:
        return None

# ================= PROGRAMA PRINCIPAL =================
def main():
    client = iniciar_modbus()
    errores = 0

    bomba_encendida = False
    arranque_pendiente = False
    tiempo_arranque = 0

    last_bajo = None
    last_alto = None

    log("Sistema Pozo–Tanque iniciado")

    while True:
        try:
            if not client.connect():
                raise Exception("No conecta Modbus")

            lectura = client.read_discrete_inputs(
                address=0,
                count=2,
                slave=MODBUS_SLAVE
            )

            if lectura.isError():
                raise Exception("Error Modbus lectura tanque")

            errores = 0

            bajo = lectura.bits[0]
            alto = lectura.bits[1]
            motor = get_estado_motor()

            # ================= LOG INFO =================
            status_msg = f"Flotador BAJO: {bajo} | Flotador ALTO: {alto} | Motor: {motor} | Bomba: {'Encendida' if bomba_encendida else 'Apagada'}"
            
            # ================= DETECCIÓN DE CAMBIO =================
            if bajo == last_bajo and alto == last_alto:
                log(status_msg + " → Sin cambios")
            else:
                log(status_msg)

            # ================= CONTROL BOMBA =================
            # Tanque lleno o estado inválido
            if (bajo and alto) or (not bajo and alto):
                if bomba_encendida:
                    log("Tanque lleno / estado inválido → APAGAR bomba")
                    set_bomba("0")
                    bomba_encendida = False
                    arranque_pendiente = False
                else:
                    log("Tanque lleno / estado inválido → Bomba ya apagada")

            # Tanque vacío → arranque programado
            elif not bajo and not alto:
                if not bomba_encendida and not arranque_pendiente:
                    arranque_pendiente = True
                    tiempo_arranque = time.time()
                    log(f"Arranque programado en {RETARDO_ARRANQUE}s")
                elif arranque_pendiente:
                    if time.time() - tiempo_arranque >= RETARDO_ARRANQUE:
                        log("Encendiendo bomba")
                        set_bomba("1")
                        bomba_encendida = True
                        arranque_pendiente = False
                    else:
                        log(f"Esperando retardo de arranque ({RETARDO_ARRANQUE - int(time.time() - tiempo_arranque)}s restantes)")

            # Actualizar última lectura
            last_bajo = bajo
            last_alto = alto

            time.sleep(CICLO_LECTURA)

        except Exception as e:
            errores += 1
            log(f"ERROR ({errores}/{MAX_ERRORES}): {e}")

            log("FAIL-SAFE → apagando bomba")
            set_bomba("0")
            bomba_encendida = False
            arranque_pendiente = False

            if errores >= MAX_ERRORES:
                log("Reiniciando conexión Modbus")
                try:
                    client.close()
                except:
                    pass
                time.sleep(5)
                client = iniciar_modbus()
                errores = 0

            time.sleep(REINTENTO_ERROR)

# ================= EJECUCIÓN =================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Programa detenido manualmente")
        set_bomba("0")
