"""Tests del detector de procesador."""

from src.core.detectores.procesador_detector import detectar_cambios_procesador
from src.core.hardware_fingerprint import fingerprint_procesador


def _cpu(nombre="Intel i5-10400", nucleos=6):
    data = {
        "nombre_completo": nombre,
        "nucleos_fisicos": nucleos,
        "gama": "i5",
        "modelo": "10400",
    }
    data["fingerprint"] = fingerprint_procesador(data)
    return data


def test_procesador_sin_cambios():
    cpu = _cpu()
    assert detectar_cambios_procesador(cpu, dict(cpu)) == []


def test_procesador_modificado():
    ant = _cpu()
    act = _cpu(nombre="Intel i7-12700", nucleos=8)
    cambios = detectar_cambios_procesador(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "modificado"
    assert cambios[0].tipo_componente == "procesador"


def test_procesador_agregado():
    cambios = detectar_cambios_procesador(None, _cpu())
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"
