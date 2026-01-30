#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================== CONFIGURACIÓN ==================
MODBUS_PORT = "/dev/ttyHS0"
BAUDRATE = 9600
ID_TANQUE = 32

RETARDO_REARRANQUE = 60     # segundos
CICLO_LECTURA = 2
TIMEOUT_MODBUS = 2
MAX_ERRORES = 5

DO_BOMBA = "ioman.gpio.dio0"

# ================== UTILIDADES ==================
def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def conectar_modbus():
    return ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=TIMEOUT_MODBUS
    )

def bomba_on():
    subprocess.run(
        ["ubus", "call", DO_BOMBA, "update", '{"value":"1"}'],
        stdout=subprocess.DEVNULL
    )

def bomba_off():
    subprocess.run(
        ["ubus", "call", DO_BOMBA, "update", '{"value":"0"}'],
        stdout=subprocess.DEVNULL
    )

# ================== PROGRAMA PRINCIPAL ==================
def main():
    client = conectar_modbus()
    errores = 0

    bomba_encendida = False
    ultimo_apagado = 0
    motivo_apagado = "N/A"

    log("Sistema Pozo–Tanque iniciado")

    while True:
        try:
            if not client.connect():
                raise Exception("No conecta Modbus")

            lectura = client.read_discrete_inputs(
                address=0,
                count=2,
                device_id=ID_TANQUE
            )

            if lectura.isError():
                raise Exception("Error lectura Modbus")

            errores = 0

            flotador_bajo = lectura.bits[0]
            flotador_alto = lectura.bits[1]

            # ================== DETERMINAR ESTADO ==================
            if not flotador_bajo and not flotador_alto:
                estado = "VACIO"
            elif flotador_bajo and not flotador_alto:
                estado = "LLENANDO"
            elif flotador_bajo and flotador_alto:
                estado = "LLENO"
            else:
                estado = "INCONSISTENTE"

            # ================== MOSTRAR ESTADO ==================
            estado_bomba = "ENCENDIDA" if bomba_encendida else "APAGADA"
            print(
                f"BAJO:{int(flotador_bajo)} "
                f"ALTO:{int(flotador_alto)} | "
                f"Tanque:{estado:<12} | "
                f"Bomba:{estado_bomba:<9} | "
                f"Motivo:{motivo_apagado}"
            )

            ahora = time.time()

            # ================== LÓGICA DE CONTROL ==================
            if estado == "LLENO":
                if bomba_encendida:
                    bomba_off()
                    bomba_encendida = False
                    ultimo_apagado = ahora
                    motivo_apagado = "Tanque lleno"
                    log("Bomba apagada → tanque lleno")

            elif estado == "INCONSISTENTE":
                if bomba_encendida:
                    bomba_off()
                    bomba_encendida = False
                    ultimo_apagado = ahora
                    motivo_apagado = "Inconsistencia flotadores"
                    log("Bomba apagada → inconsistencia flotadores")

            elif estado == "VACIO":
                if not bomba_encendida:
                    restante = RETARDO_REARRANQUE - (ahora - ultimo_apagado)
                    if restante <= 0:
                        bomba_on()
                        bomba_encendida = True
                        motivo_apagado = "N/A"
                        log("Bomba encendida → tanque vacío")
                    else:
                        log(f"Esperando rearme ({int(restante)}s)")

            # estado LLENANDO → no se hace nada
            time.sleep(CICLO_LECTURA)

        except Exception as e:
            errores += 1
            log(f"ERROR ({errores}/{MAX_ERRORES}): {e}")

            if bomba_encendida:
                bomba_off()
                bomba_encendida = False
                ultimo_apagado = time.time()
                motivo_apagado = "Falla Modbus"
                log("FAIL-SAFE → bomba apagada")

            if errores >= MAX_ERRORES:
                log("Reiniciando cliente Modbus")
                try:
                    client.close()
                except:
                    pass
                time.sleep(5)
                client = conectar_modbus()
                errores = 0

            time.sleep(5)

# ================== EJECUCIÓN ==================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Sistema detenido manualmente")
        bomba_off()
