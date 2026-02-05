#!/usr/bin/env python3
import time
from pymodbus.client.sync import ModbusSerialClient

# ================= CONFIGURACIÓN =================

PUERTO = "/dev/ttyHS0"
BAUDIOS = 9600
SLAVE_ID = 1

# DIOs
DIO_CONTROL = 0   # DIO0 -> Control motor/bomba
DIO_ESTADO  = 1   # DIO1 -> Estado motor/bomba

TIEMPO_REARRANQUE = 300     # segundos (ej. 5 minutos)
INTERVALO_CICLO   = 2       # segundos entre lecturas
MAX_INTENTOS_MODBUS = 10

# ================================================

def crear_cliente():
    return ModbusSerialClient(
        method="rtu",
        port=PUERTO,
        baudrate=BAUDIOS,
        timeout=1,
        parity='N',
        stopbits=1,
        bytesize=8
    )

cliente = crear_cliente()
cliente.connect()

intentos_modbus = 0
falla_modbus = False

ultimo_control = None
inicio_rearranque = None

print(">>> Sistema de control iniciado")

while True:
    try:
        rr = cliente.read_coils(DIO_CONTROL, 2, unit=SLAVE_ID)

        if rr.isError():
            raise Exception("Error Modbus")

        intentos_modbus = 0
        if falla_modbus:
            print("✔ Comunicación Modbus restablecida")
            falla_modbus = False

        control = rr.bits[0]  # DIO0
        estado  = rr.bits[1]  # DIO1

        print(f"Control: {control} | Estado: {estado}")

        # ================= LÓGICA DE REARRANQUE =================

        if not control:
            # Control APAGADO → puede iniciar conteo
            if ultimo_control is True:
                inicio_rearranque = time.time()
                print("⏱ Control apagado, inicia conteo de rearranque")

            if inicio_rearranque is not None:
                tiempo_transcurrido = time.time() - inicio_rearranque
                restante = TIEMPO_REARRANQUE - tiempo_transcurrido

                if restante > 0:
                    print(f"⏳ Rearranque disponible en {int(restante)} s")
                else:
                    print("✅ Rearranque permitido")
        else:
            # Control ENCENDIDO → se cancela conteo
            inicio_rearranque = None

        ultimo_control = control

    except Exception as e:
        intentos_modbus += 1

        if not falla_modbus:
            print("⚠ Falla de comunicación Modbus")
            falla_modbus = True

        print(f"Intento Modbus fallido #{intentos_modbus}")

        # ===== Reinicio del puerto Modbus en intento 10 =====
        if intentos_modbus >= MAX_INTENTOS_MODBUS:
            print("🔄 Reiniciando puerto Modbus...")
            try:
                cliente.close()
                time.sleep(2)
                cliente = crear_cliente()
                cliente.connect()
                intentos_modbus = 0
                print("🔁 Puerto Modbus reiniciado")
            except Exception as ex:
                print("❌ Error al reiniciar Modbus:", ex)

    time.sleep(INTERVALO_CICLO)
