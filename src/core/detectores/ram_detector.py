"""Detector de cambios en módulos RAM (ranuras ocupadas)."""

from src.core.hardware_diff import CambioHardware, diff_listas


def detectar_cambios_ram(anteriores: list, actuales: list) -> list[CambioHardware]:
    return diff_listas("ram", anteriores, actuales)
