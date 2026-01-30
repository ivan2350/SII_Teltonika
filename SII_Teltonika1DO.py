#!/usr/bin/env python3
import time
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live

# ================= CONFIGURACIÓN =================

TIEMPO_REARRANQUE = 300  # segundos (ej. 5 minutos)

# ================= ESTADOS =================

bomba_encendida = False
ultimo_apagado = None  # datetime cuando se apagó la bomba

# Simulación de flotadores (CAMBIAR POR LECTURA REAL)
flotador_bajo = False
flotador_alto = False

console = Console()

# ================= FUNCIONES =================

def puede_rearrancar():
    """Verifica si ya transcurrió el tiempo de rearranque"""
    if ultimo_apagado is None:
        return True
    return datetime.now() >= ultimo_apagado + timedelta(seconds=TIEMPO_REARRANQUE)

def encender_bomba():
    global bomba_encendida
    if not bomba_encendida:
        bomba_encendida = True
        console.log("🟢 [bold green]Bomba ENCENDIDA[/bold green]")

def apagar_bomba():
    global bomba_encendida, ultimo_apagado
    if bomba_encendida:
        bomba_encendida = False
        ultimo_apagado = datetime.now()
        console.log("🔴 [bold red]Bomba APAGADA[/bold red]")

def crear_tabla():
    table = Table(title="💧 Control de Bomba", expand=True)

    table.add_column("Parámetro", justify="left", style="cyan", no_wrap=True)
    table.add_column("Estado", justify="center", style="white")

    table.add_row(
        "Flotador Bajo",
        "⬆️ ACTIVO" if flotador_bajo else "⬇️ INACTIVO"
    )
    table.add_row(
        "Flotador Alto",
        "⬆️ ACTIVO" if flotador_alto else "⬇️ INACTIVO"
    )
    table.add_row(
        "Bomba",
        "🟢 ENCENDIDA" if bomba_encendida else "🔴 APAGADA"
    )

    if ultimo_apagado:
        restante = max(
            0,
            int((ultimo_apagado + timedelta(seconds=TIEMPO_REARRANQUE) - datetime.now()).total_seconds())
        )
        table.add_row(
            "Rearranque",
            f"⏳ {restante} s"
        )
    else:
        table.add_row(
            "Rearranque",
            "✔️ Disponible"
        )

    return table

# ================= LOOP PRINCIPAL =================

with Live(crear_tabla(), refresh_per_second=2, console=console) as live:
    while True:

        # ================= LÓGICA DE CONTROL =================
        # Apagado por flotador alto
        if flotador_alto:
            apagar_bomba()

        # Encendido por flotador bajo (solo si ya pasó el rearranque)
        elif flotador_bajo and puede_rearrancar():
            encender_bomba()

        # ================= ACTUALIZAR TABLA =================
        live.update(crear_tabla())

        # ================= SIMULACIÓN =================
        # (Quitar esto cuando conectes flotadores reales)
        time.sleep(1)
