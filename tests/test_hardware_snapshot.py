"""Tests de persistencia del snapshot (mock winreg)."""

import json
from unittest.mock import MagicMock, patch

from src.core import hardware_snapshot


def test_cargar_desde_memoria():
    hardware_snapshot.invalidar_cache()
    snap = {"version": 1, "monitores": []}
    hardware_snapshot._cache_memoria = snap
    assert hardware_snapshot.cargar() == snap
    hardware_snapshot.invalidar_cache()


def test_guardar_y_cargar_registro():
    hardware_snapshot.invalidar_cache()
    almacen = {}

    def mock_set_value(key, name, reserved, typ, val):
        almacen[name] = val

    def mock_query_value(key, name):
        if name not in almacen:
            raise FileNotFoundError
        return almacen[name], 1

    mock_key = MagicMock()
    mock_key.__enter__ = MagicMock(return_value=mock_key)
    mock_key.__exit__ = MagicMock(return_value=False)
    mock_key.SetValueEx = mock_set_value
    mock_key.QueryValueEx = mock_query_value

    with patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.CreateKey", return_value=mock_key), \
         patch("winreg.HKEY_LOCAL_MACHINE", 0), \
         patch("winreg.REG_SZ", 1):
        snap = {"version": 1, "monitores": [{"fingerprint": "SN:1", "nombre": "LG"}]}
        ok = hardware_snapshot.guardar(snap)
        assert ok is True
        hardware_snapshot.invalidar_cache()
        loaded = hardware_snapshot.cargar()
        assert loaded is not None
        assert loaded["monitores"][0]["nombre"] == "LG"

    hardware_snapshot.invalidar_cache()


def test_snapshot_json_compacto_menor_12kb():
    monitores = [
        {"nombre": f"M{i}", "numero_serie": f"S{i}", "fabricante": "LG", "pulgadas": 24, "instance_name": ""}
        for i in range(20)
    ]
    snap = {"version": 1, "monitores": monitores}
    json_str = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    assert len(json_str.encode("utf-8")) < 12 * 1024
