"""Detector de cambios en discos físicos."""

from src.core.hardware_diff import CambioHardware, diff_listas


def detectar_cambios_discos(anteriores: list, actuales: list) -> list[CambioHardware]:
    return diff_listas("disco", anteriores, actuales)
