"""Detector de cambios en procesador (diff al arranque del servicio)."""

from src.core.hardware_diff import CambioHardware, diff_procesador


def detectar_cambios_procesador(anterior: dict | None, actual: dict | None) -> list[CambioHardware]:
    return diff_procesador(anterior, actual)
