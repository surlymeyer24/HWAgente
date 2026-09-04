"""Tests del detector de RAM."""

from src.core.detectores.ram_detector import detectar_cambios_ram
from src.core.hardware_fingerprint import fingerprint_ram


def _modulo(locator="DIMM_A1", serial="SN1", capacidad=16, modelo="KVR"):
    data = {
        "slot": "Slot 1",
        "locator": locator,
        "numero_serie": serial,
        "capacidad_gb": capacidad,
        "modelo": modelo,
    }
    data["fingerprint"] = fingerprint_ram(data)
    return data


def test_ram_modulo_agregado():
    ant = [_modulo()]
    act = [_modulo(), _modulo(locator="DIMM_B1", serial="SN2", capacidad=8)]
    cambios = detectar_cambios_ram(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"
    assert cambios[0].tipo_componente == "ram"


def test_ram_modulo_removido():
    ant = [_modulo(), _modulo(locator="DIMM_B1", serial="SN2")]
    act = [_modulo()]
    cambios = detectar_cambios_ram(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "removido"


def test_ram_cambio_capacidad_misma_ranura():
    ant = [_modulo(capacidad=8)]
    act = [_modulo(capacidad=16, serial="SN1")]
    # Mismo serial → mismo fingerprint; capacidad distinta → modificado
    cambios = detectar_cambios_ram(ant, act)
    assert any(c.tipo_evento == "modificado" for c in cambios)
