"""Tests del motor de diff de hardware."""

from src.core.hardware_diff import (
    diff_listas,
    diff_procesador,
    normalizar_lista_seccion,
)


def _monitor(fp, nombre="LG", resolucion="1920x1080"):
    return {"fingerprint": fp, "nombre": nombre, "resolucion": resolucion, "pulgadas": 24}


def test_diff_agregado():
    ant = []
    act = [_monitor("SN:NEW")]
    cambios = diff_listas("monitor", ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "agregado"


def test_diff_removido():
    ant = [_monitor("SN:OLD")]
    act = []
    cambios = diff_listas("monitor", ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "removido"


def test_diff_sin_cambios():
    item = _monitor("SN:SAME")
    cambios = diff_listas("monitor", [item], [dict(item)])
    assert cambios == []


def test_resolucion_cambia_sin_evento():
    ant = [_monitor("SN:SAME", resolucion="1920x1080")]
    act = [_monitor("SN:SAME", resolucion="2560x1440")]
    cambios = diff_listas("monitor", ant, act)
    assert cambios == []


def test_diff_agregado_y_removido_mismo_ciclo():
    ant = [_monitor("SN:A")]
    act = [_monitor("SN:B")]
    cambios = diff_listas("monitor", ant, act)
    tipos = {c.tipo_evento for c in cambios}
    assert tipos == {"agregado", "removido"}


def test_diff_procesador_modificado():
    ant = {"fingerprint": "CPU:Intel i5|6", "nombre_completo": "Intel i5", "nucleos_fisicos": 6}
    act = {"fingerprint": "CPU:Intel i7|8", "nombre_completo": "Intel i7", "nucleos_fisicos": 8}
    cambios = diff_procesador(ant, act)
    assert len(cambios) == 1
    assert cambios[0].tipo_evento == "modificado"


def test_normalizar_lista_ordena_por_fingerprint():
    items = [{"nombre": "B"}, {"nombre": "A", "numero_serie": "111"}]
    norm = normalizar_lista_seccion("monitores", items)
    fps = [i["fingerprint"] for i in norm]
    assert fps == sorted(fps)
