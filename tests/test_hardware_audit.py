"""Tests del orquestador de auditoría."""

from unittest.mock import patch

from src.core.hardware_audit import construir_snapshot_actual, detectar_cambios, procesar_auditoria_hardware
from src.core.hardware_diff import CambioHardware


def _datos_pc_base(monitores=None):
    default_monitores = [
        {"nombre": "LG 24", "numero_serie": "ABC", "fabricante": "LG", "pulgadas": 24},
    ]
    return {
        "hostname": "TEST-PC",
        "procesador_detallado": {
            "nombre_completo": "Intel i5-10400",
            "nucleos_fisicos": 6,
            "gama": "i5",
            "modelo": "10400",
        },
        "modulos_ram": [
            {"ocupado": True, "slot": "Slot 1", "locator": "DIMM_A1", "capacidad_gb": 16, "modelo": "KVR", "numero_serie": "S1"},
        ],
        "perifericos": {
            "monitores": default_monitores if monitores is None else monitores,
        },
    }


def test_baseline_no_emite_eventos():
    with patch("src.core.hardware_snapshot.cargar", return_value=None), \
         patch("src.core.hardware_snapshot.guardar", return_value=True) as mock_guardar, \
         patch("src.core.hardware_audit._emitir_si_hay") as mock_emit:
        cambios = procesar_auditoria_hardware(_datos_pc_base(), "uuid-1", "TEST-PC", secciones=("monitores",))
        assert cambios == []
        mock_guardar.assert_called_once()
        mock_emit.assert_not_called()


def test_detectar_cambios_monitor_agregado():
    snap_ant = construir_snapshot_actual(_datos_pc_base(), ("monitores",))
    datos_nuevos = _datos_pc_base(monitores=[
        {"nombre": "LG 24", "numero_serie": "ABC", "fabricante": "LG", "pulgadas": 24},
        {"nombre": "Samsung", "numero_serie": "NEW", "fabricante": "Samsung", "pulgadas": 27},
    ])
    snap_act = construir_snapshot_actual(datos_nuevos, ("monitores",))
    cambios = detectar_cambios(snap_ant, snap_act, ("monitores",))
    assert any(c.tipo_evento == "agregado" for c in cambios)


def test_procesar_emite_y_guarda_snapshot():
    snap_ant = construir_snapshot_actual(_datos_pc_base(), ("monitores",))
    datos_nuevos = _datos_pc_base(monitores=[])

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar", return_value=True) as mock_guardar, \
         patch("src.core.hardware_audit._emitir_si_hay", return_value=True) as mock_emit:
        cambios = procesar_auditoria_hardware(datos_nuevos, "uuid-1", "TEST-PC", secciones=("monitores",))
        assert len(cambios) >= 1
        mock_emit.assert_called_once()
        mock_guardar.assert_called_once()


def test_emit_fallido_no_guarda_snapshot():
    snap_ant = construir_snapshot_actual(_datos_pc_base(), ("monitores",))
    datos_nuevos = _datos_pc_base(monitores=[])

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar", return_value=True) as mock_guardar, \
         patch("src.core.hardware_audit._emitir_si_hay", return_value=False):
        procesar_auditoria_hardware(datos_nuevos, "uuid-1", "TEST-PC", secciones=("monitores",))
        mock_guardar.assert_not_called()


def test_seccion_nueva_baseline_sin_eventos():
    """PC con snapshot v5.6 (solo monitores): RAM/discos se agregan sin alertar."""
    snap_ant = construir_snapshot_actual(_datos_pc_base(), ("monitores",))
    datos = _datos_pc_base()

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar", return_value=True), \
         patch("src.core.scanner.obtener_discos_fisicos_auditoria", return_value=[
             {"device_id": "0", "modelo": "SSD Test", "tipo": "SSD", "numero_serie": ""},
         ]), \
         patch("src.core.hardware_audit._emitir_si_hay") as mock_emit:
        cambios = procesar_auditoria_hardware(
            datos, "uuid-1", "TEST-PC", secciones=("monitores", "ram", "discos"),
        )
        assert cambios == []
        mock_emit.assert_not_called()


def test_guardar_fallido_tras_emit():
    snap_ant = construir_snapshot_actual(_datos_pc_base(), ("monitores",))
    datos_nuevos = _datos_pc_base(monitores=[])

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar", return_value=False), \
         patch("src.core.hardware_audit._emitir_si_hay", return_value=True), \
         patch("src.core.hardware_audit._audit_log") as mock_log:
        cambios = procesar_auditoria_hardware(datos_nuevos, "uuid-1", "TEST-PC", secciones=("monitores",))
        assert len(cambios) >= 1
        assert any(
            "AUDIT_SNAPSHOT_FAIL" in (c.args[0] if c.args else "")
            for c in mock_log.call_args_list
        )


def test_procesador_baseline_sin_eventos_en_upgrade():
    """Snapshot v5.7 sin procesador: primer arranque v5.8 no alerta CPU."""
    snap_ant = {
        "version": 1,
        "monitores": [],
        "ram": [],
        "discos": [],
    }
    datos = _datos_pc_base()

    with patch("src.core.hardware_snapshot.cargar", return_value=snap_ant), \
         patch("src.core.hardware_snapshot.guardar", return_value=True), \
         patch("src.core.hardware_audit._emitir_si_hay") as mock_emit:
        from src.core.hardware_audit import procesar_auditoria_procesador
        cambios = procesar_auditoria_procesador(datos, "uuid-1", "TEST-PC")
        assert cambios == []
        mock_emit.assert_not_called()
