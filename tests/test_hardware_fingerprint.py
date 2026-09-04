"""Tests de fingerprints de hardware."""

from src.core.hardware_fingerprint import (
    fingerprint_disco,
    fingerprint_monitor,
    fingerprint_procesador,
    fingerprint_ram,
)


def test_fingerprint_monitor_con_serial():
    fp = fingerprint_monitor({"numero_serie": "ABC123", "nombre": "LG"})
    assert fp == "SN:ABC123"


def test_fingerprint_monitor_sin_serial_usa_instance():
    fp = fingerprint_monitor({
        "nombre": "LG 24",
        "instance_name": "DISPLAY\\LG123",
        "fabricante": "LG",
        "pulgadas": 24,
    })
    assert fp == "INST:DISPLAY\\LG123"


def test_fingerprint_monitor_fallback():
    fp = fingerprint_monitor({"nombre": "Monitor Genérico", "fabricante": "Dell", "pulgadas": 24})
    assert fp.startswith("FALLBACK:")


def test_fingerprint_ram_con_serial():
    fp = fingerprint_ram({"locator": "ChannelA-DIMM0", "numero_serie": "XYZ", "capacidad_gb": 16})
    assert "SN:XYZ" in fp


def test_fingerprint_ram_sin_serial():
    fp = fingerprint_ram({"locator": "DIMM_A1", "numero_serie": "N/A", "capacidad_gb": 8, "modelo": "KVR"})
    assert fp == "RAM:DIMM_A1|8|KVR"


def test_fingerprint_disco_con_serial():
    fp = fingerprint_disco({"numero_serie": "DISK001", "device_id": "0"})
    assert fp == "DISK:SN:DISK001"


def test_fingerprint_disco_sin_serial():
    fp = fingerprint_disco({"device_id": "1", "modelo": "Samsung SSD", "tipo": "SSD"})
    assert fp == "DISK:1|Samsung SSD|SSD"


def test_fingerprint_procesador():
    fp = fingerprint_procesador({"nombre_completo": "Intel i5-10400", "nucleos_fisicos": 6})
    assert fp == "CPU:Intel i5-10400|6"


def test_dos_monitores_fallback_iguales():
    m1 = fingerprint_monitor({"nombre": "Dell P2422H", "fabricante": "Dell", "pulgadas": 24})
    m2 = fingerprint_monitor({"nombre": "Dell P2422H", "fabricante": "Dell", "pulgadas": 24})
    assert m1 == m2
