#!/usr/bin/env python3
import time

# ================= CONFIGURACIÓN =================

TIEMPO_REARRANQUE = 300   # segundos (ej. 5 minutos)
INTERVALO_LOOP = 1        # segundos

# ================= ESTADOS =================

motor_DO = False          # Salida digital (control automático)
motor_DI = False          # Entrada digital (estado real)
en_rearranque = False
fin_rearranque = 0

# ================= FUNCIONES HARDWARE =================
# 🔧 ADAPTA ESTAS FUNCIONES A TU SISTEMA REAL

def leer_DI_motor():
    """
    Retorna True si el motor está ENCENDIDO (DI)
    """
    # EJEMPLO:
    # return ioman.gpio.input(DI_MOTOR)
    return motor_DI_simulado()


def leer_flotadores():
    """
    Retorna:
    - True  → nivel ALTO (debe encender)
    - False → nivel BAJO (debe apagar)
    """
    # EJEMPLO:
    # return ioman.gpio.input(FLOTADOR_ALTO)
    return flotador_simulado()


def DO_motor(estado):
    """
    Controla la salida digital del motor
    """
    global motor_DO
    motor_DO = estado
    # EJEMPLO:
    # gpio.output(DO_MOTOR, estado)

# ================= CONTROL MOTOR =================

def encender_motor():
    global motor_DO
    if not motor_DO:
        DO_motor(True)
        print("🟢 Motor ENCENDIDO (automático)")


def apagar_motor():
    global en_rearranque, fin_rearranque

    if motor_DO:
        DO_motor(False)
        en_rearranque = True
        fin_rearranque = time.time() + TIEMPO_REARRANQUE
        print("🔴 Motor APAGADO (automático)")
        print(f"⏳ Rearranque iniciado ({TIEMPO_REARRANQUE} s)")


# ================= LOOP PRINCIPAL =================

print("🚀 Sistema de control iniciado")

while True:
    ahora = time.time()

    # ----- Lecturas SIEMPRE activas -----
    motor_DI = leer_DI_motor()
    flotador_alto = leer_flotadores()

    # ----- Fin de rearranque -----
    if en_rearranque and ahora >= fin_rearranque:
        en_rearranque = False
        print("✅ Rearranque finalizado (esperando flotadores)")

    # ----- Control AUTOMÁTICO -----
    if not en_rearranque:
        if flotador_alto and not motor_DO:
            encender_motor()

        elif not flotador_alto and motor_DO:
            apagar_motor()

    # ----- ALERTA MANUAL -----
    if motor_DI and not motor_DO:
        print("⚠️ ALERTA: Motor ENCENDIDO en MANUAL (DI=ON / DO=OFF)")

    # ----- Estado informativo -----
    print(
        f"📊 Estado | "
        f"DO={'ON' if motor_DO else 'OFF'} | "
        f"DI={'ON' if motor_DI else 'OFF'} | "
        f"Flotador={'ALTO' if flotador_alto else 'BAJO'} | "
        f"Rearranque={'SI' if en_rearranque else 'NO'}"
    )

    time.sleep(INTERVALO_LOOP)

# ================== SIMULADORES ==================
# ❌ ELIMINA ESTO EN PRODUCCIÓN

def motor_DI_simulado():
    return motor_DO  # simula que el motor sigue al DO

def flotador_simulado():
    return True  # cambia a False para simular nivel bajo
