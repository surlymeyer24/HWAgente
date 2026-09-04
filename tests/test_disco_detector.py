"""Tests del detector de discos."""

from src.core.detectores.disco_detector import detectar_cambios_discos
from src.core.hardware_fingerprint import fingerprint_disco


def _disco(device_id="0", serial="", modelo="Samsung SSD", tipo="SSD"):
    data = {
        "device_id": device_id,
        "modelo": modelo,
        "tipo": tipo,
        "numero_serie": serial,
    }
    data["fingerprint"] = fingerprint_disco(data)
    return data


def test_disco_agregado():
    ant = [_disco(device_id="0")]
    act = [_disco(device_id="0"), _disco(device_id="1", serial="DISK2")]
    cambios = detectar_cambios_discos(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"
    assert cambios[0].tipo_componente == "disco"


def test_disco_removido():
    ant = [_disco(device_id="0"), _disco(device_id="1", serial="X")]
    act = [_disco(device_id="0")]
    cambios = detectar_cambios_discos(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "removido"


def test_disco_por_serial():
    d = _disco(serial="ABC123")
    assert d["fingerprint"] == "DISK:SN:ABC123"
