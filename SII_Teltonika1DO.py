#!/usr/bin/env python3
import time
import subprocess
from pymodbus.client import ModbusSerialClient

# ================= CONFIGURACIÓN =================

MODBUS_PORT = "/dev/ttyHS0"   # RS485 real del TRB145
BAUDRATE = 9600
SLAVE_ID = 32                # Flotadores tanque

TIEMPO_CICLO = 5             # segundos entre lecturas

# ================= FUNCIONES =================

def iniciar_modbus():
    client = ModbusSerialClient(
        method="rtu",
        port=MODBUS_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=2
    )
    return client


def leer_flotadores(client):
    rr = client.read_discrete_inputs(
        address=0,
        count=2,
        unit=SLAVE_ID
    )

    if rr.isError():
        raise Exception("Error leyendo flotadores Modbus")

    bajo = rr.bits[0]
    alto = rr.bits[1]
    return bajo, alto


def set_bomba(valor):
    # valor = "1" enciende / "0" apaga
    subprocess.run(
        [
            "ubus", "call", "ioman.gpio.dio0", "update",
            f'{{"value":"{valor}"}}'
        ],
        check=True
    )

# ================= PROGRAMA PRINCIPAL =================

def main():
    print("=== PRUEBA POZO–TANQUE TELTONIKA ===")

    client = iniciar_modbus()

    if not client.connect():
        print("ERROR: No conecta Modbus")
        return

    print("Modbus conectado correctamente\n")

    try:
        while True:
            bajo, alto = leer_flotadores(client)

            print(f"Flotadores → Bajo: {bajo} | Alto: {alto}")

            # SOLO PRUEBA DE CONTROL
            if not bajo and not alto:
                print("Tanque vacío → ENCENDER bomba (prueba)")
                set_bomba("1")
            else:
                print("Tanque NO vacío → APAGAR bomba (prueba)")
                set_bomba("0")

            print("-" * 40)
            time.sleep(TIEMPO_CICLO)

    except KeyboardInterrupt:
        print("\nPrograma detenido por usuario")
        set_bomba("0")

    except Exception as e:
        print(f"ERROR: {e}")
        set_bomba("0")

    finally:
        client.close()
        print("Modbus cerrado")


if __name__ == "__main__":
    main()
