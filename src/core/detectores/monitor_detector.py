"""Detector de cambios en monitores conectados."""

from src.core.hardware_diff import CambioHardware, diff_listas


def detectar_cambios_monitores(anteriores: list, actuales: list) -> list[CambioHardware]:
    return diff_listas("monitor", anteriores, actuales)
