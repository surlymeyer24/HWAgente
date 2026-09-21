"""Tests de detección degradada de CPU y guarda anti-falso-positivo."""

from unittest.mock import patch

from src.core.hardware_audit import procesar_auditoria_procesador
from src.core.hardware_fingerprint import fingerprint_procesador
from src.core.scanner import es_lectura_cpu_degradada, es_nombre_cpu_degradado


def test_es_nombre_cpu_degradado_identifier():
    assert es_nombre_cpu_degradado(
        "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel"
    )
    assert not es_nombre_cpu_degradado("Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz")
    assert es_nombre_cpu_degradado("")
    assert es_nombre_cpu_degradado("Desconocido")


def test_es_lectura_cpu_degradada_por_origen():
    assert es_lectura_cpu_degradada({
        "nombre_completo": "Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz",
        "origen_deteccion": "platform",
    })
    assert not es_lectura_cpu_degradada({
        "nombre_completo": "Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz",
        "origen_deteccion": "wmi",
        "nucleos_fisicos": 4,
    })


def _snap_cpu(nombre, nucleos=4, origen="wmi", gama="i5", modelo="7400"):
    data = {
        "nombre_completo": nombre,
        "nucleos_fisicos": nucleos,
        "gama": gama,
        "modelo": modelo,
        "origen_deteccion": origen,
    }
    data["fingerprint"] = fingerprint_procesador(data)
    return {
        "version": 1,
        "procesador": data,
    }


def test_cpu_degradada_no_emite_ni_pisa_snapshot_bueno():
    bueno = "Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz"
    malo = "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel"
    snap_ant = _snap_cpu(bueno, origen="wmi")
    datos = {
        "hostname": "CANDE-REARTES",
        "procesador_detallado": {
            "nombre_completo": malo,
            "nucleos_fisicos": 4,
            "gama": "",
            "modelo": "",
            "origen_deteccion": "platform",
        },
    }

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar") as mock_guardar, \
         patch("src.core.hardware_audit._emitir_si_hay") as mock_emit, \
         patch("src.core.hardware_audit._audit_log") as mock_log:
        cambios = procesar_auditoria_procesador(datos, "uuid-1", "CANDE-REARTES")
        assert cambios == []
        mock_emit.assert_not_called()
        mock_guardar.assert_not_called()
        assert any(
            "AUDIT_CPU_DEGRADADA" in (c.args[0] if c.args else "")
            for c in mock_log.call_args_list
        )


def test_cpu_degradada_baseline_omitido():
    malo = "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel"
    datos = {
        "hostname": "PC-NUEVA",
        "procesador_detallado": {
            "nombre_completo": malo,
            "nucleos_fisicos": 4,
            "gama": "",
            "modelo": "",
            "origen_deteccion": "platform",
        },
    }

    with patch("src.core.hardware_snapshot.cargar", return_value=None), \
         patch("src.core.hardware_snapshot.guardar") as mock_guardar, \
         patch("src.core.hardware_audit._emitir_si_hay") as mock_emit:
        cambios = procesar_auditoria_procesador(datos, "uuid-2", "PC-NUEVA")
        assert cambios == []
        mock_emit.assert_not_called()
        mock_guardar.assert_not_called()
