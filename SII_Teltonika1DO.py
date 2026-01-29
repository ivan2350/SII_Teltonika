import subprocess
import time

GPIO = "dio0"   # Relay Motor 1

def set_bomba(valor):
    subprocess.run(
        ["ubus", "call", f"ioman.gpio.{GPIO}", "update", f'{{"value":"{valor}"}}'],
        check=True
    )
    print(f"Bomba {'ENCENDIDA' if valor == '1' else 'APAGADA'}")

print("PRUEBA DE RELAY - Ctrl+C para salir")

while True:
    set_bomba("1")
    time.sleep(5)

    set_bomba("0")
    time.sleep(5)
