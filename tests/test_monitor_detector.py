"""Tests del detector de monitores."""

from src.core.detectores.monitor_detector import detectar_cambios_monitores
from src.core.hardware_fingerprint import fingerprint_monitor


def _monitor(serial=None, instance=None, nombre="LG 24", pulgadas=24):
    data = {"nombre": nombre, "fabricante": "LG", "pulgadas": pulgadas}
    if serial:
        data["numero_serie"] = serial
    if instance:
        data["instance_name"] = instance
    data["fingerprint"] = fingerprint_monitor(data)
    return data


def test_monitor_conectado():
    ant = [_monitor(serial="ABC")]
    act = [_monitor(serial="ABC"), _monitor(serial="NEW")]
    cambios = detectar_cambios_monitores(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"
    assert cambios[0].tipo_componente == "monitor"


def test_monitor_desconectado():
    ant = [_monitor(serial="ABC"), _monitor(serial="OLD")]
    act = [_monitor(serial="ABC")]
    cambios = detectar_cambios_monitores(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "removido"


def test_instance_name_en_fingerprint():
    fp = fingerprint_monitor(_monitor(instance="DISPLAY\\LG0"))
    assert fp == "INST:DISPLAY\\LG0"
