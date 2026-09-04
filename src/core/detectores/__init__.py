"""Detectores de cambios por componente."""

from src.core.detectores.disco_detector import detectar_cambios_discos
from src.core.detectores.monitor_detector import detectar_cambios_monitores
from src.core.detectores.procesador_detector import detectar_cambios_procesador
from src.core.detectores.ram_detector import detectar_cambios_ram

__all__ = [
    "detectar_cambios_monitores",
    "detectar_cambios_ram",
    "detectar_cambios_discos",
    "detectar_cambios_procesador",
]
