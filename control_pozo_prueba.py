import subprocess
import time

DO_RELAY = "dio0"   # Salida digital (Motor 1)

def set_bomba(valor):
    try:
        subprocess.run(
            [
                "ubus",
                "call",
                f"ioman.gpio.{DO_RELAY}",
                "update",
                f'{{"value":"{valor}"}}'
            ],
            check=True
        )
        print(f"Bomba {'ENCENDIDA' if valor == '1' else 'APAGADA'}")
    except Exception as e:
        print(f"Error controlando bomba: {e}")

def leer_flotadores():
    """
    SIMULACIÓN DE FLOTADORES
    Cámbialos para probar lógica
    """
    flotador_bajo = true   # False = sin agua
    flotador_alto = true   # False = no lleno
    return flotador_bajo, flotador_alto


print("Control de pozo iniciado (modo prueba)")
print("Ctrl+C para salir\n")

try:
    while True:
        bajo, alto = leer_flotadores()
        print(f"Flotadores → Bajo: {bajo} | Alto: {alto}")

        if not bajo and not alto:
            print("Tanque vacío → ENCENDER bomba")
            set_bomba("1")

        elif alto:
            print("Tanque lleno → APAGAR bomba")
            set_bomba("0")

        time.sleep(5)

except KeyboardInterrupt:
    print("\nPrograma detenido manualmente")
    set_bomba("0")
