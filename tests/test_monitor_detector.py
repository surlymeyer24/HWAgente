"""Tests del detector de monitores v2 — deteccion asimetrica."""

from datetime import datetime, timedelta, timezone

from src.core.detectores.monitor_detector import detectar_cambios_monitores
from src.core.hardware_fingerprint import fingerprint_monitor

_AHORA = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
_RECIENTE = (_AHORA - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
_VIEJO = (_AHORA - timedelta(hours=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
_AHORA_ISO = _AHORA.strftime("%Y-%m-%dT%H:%M:%SZ")


def _monitor(serial=None, instance=None, nombre="LG 24", pulgadas=24, ultima_vez_visto=None):
    data = {"nombre": nombre, "fabricante": "LG", "pulgadas": pulgadas}
    if serial:
        data["numero_serie"] = serial
    if instance:
        data["instance_name"] = instance
    data["fingerprint"] = fingerprint_monitor(data)
    if ultima_vez_visto:
        data["ultima_vez_visto"] = ultima_vez_visto
    return data


def test_monitor_agregado_inmediato():
    ant = [_monitor(serial="ABC", ultima_vez_visto=_RECIENTE)]
    act = [_monitor(serial="ABC"), _monitor(serial="NEW")]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"
    assert cambios[0].fingerprint == "SN:NEW"
    assert len(updated) == 2


def test_monitor_ausente_bajo_umbral():
    ant = [_monitor(serial="ABC", ultima_vez_visto=_RECIENTE), _monitor(serial="OLD", ultima_vez_visto=_RECIENTE)]
    act = [_monitor(serial="ABC")]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 0
    fps = {m["fingerprint"] for m in updated}
    assert "SN:OLD" in fps
    assert "SN:ABC" in fps


def test_monitor_ausente_sobre_umbral():
    ant = [_monitor(serial="OLD", ultima_vez_visto=_VIEJO)]
    act = []
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "removido"
    assert cambios[0].fingerprint == "SN:OLD"
    assert len(updated) == 0


def test_monitor_modificado_inmediato():
    ant = [_monitor(serial="ABC", nombre="LG 24", ultima_vez_visto=_RECIENTE)]
    act = [_monitor(serial="ABC", nombre="LG 27", pulgadas=27)]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "modificado"


def test_monitor_vuelve_antes_umbral():
    ant = [_monitor(serial="ABC", ultima_vez_visto=_RECIENTE)]
    act = [_monitor(serial="ABC")]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 0
    assert len(updated) == 1
    assert updated[0]["ultima_vez_visto"] == _AHORA_ISO


def test_ultima_vez_visto_en_snapshot():
    ant = []
    act = [_monitor(serial="NEW")]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(updated) == 1
    assert updated[0]["ultima_vez_visto"] == _AHORA_ISO


def test_migracion_snapshot_sin_campo():
    ant = [_monitor(serial="OLD")]
    act = []
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 0
    assert len(updated) == 1
    assert updated[0]["ultima_vez_visto"] == _AHORA_ISO


def test_ultima_vez_visto_no_dispara_modificado():
    ant = [_monitor(serial="ABC", ultima_vez_visto=_VIEJO)]
    act = [_monitor(serial="ABC")]
    cambios, updated = detectar_cambios_monitores(ant, act, ahora=_AHORA)
    assert len(cambios) == 0


def test_instance_name_en_fingerprint():
    fp = fingerprint_monitor(_monitor(instance="DISPLAY\\LG0"))
    assert fp == "INST:DISPLAY\\LG0"
