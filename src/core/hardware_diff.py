"""Diff genérico de hardware: agregado / removido / modificado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.hardware_fingerprint import (
    enriquecer_con_fingerprint,
    fingerprint_disco,
    fingerprint_monitor,
    fingerprint_procesador,
    fingerprint_ram,
)

# Campos volátiles que no disparan evento "modificado"
_CAMPOS_IGNORAR: dict[str, frozenset[str]] = {
    "monitor": frozenset({"resolucion"}),
    "disco": frozenset({"total_gb", "usado_gb", "libre_gb", "porcentaje_usado", "capacidad_gb"}),
    "ram": frozenset({"velocidad_mhz"}),
}


@dataclass
class CambioHardware:
    tipo_componente: str
    tipo_evento: str
    fingerprint: str
    antes: dict | None
    despues: dict | None


def _dict_comparable(item: dict, tipo_componente: str) -> dict:
    ignorar = _CAMPOS_IGNORAR.get(tipo_componente, frozenset())
    return {k: v for k, v in item.items() if k not in ignorar and k != "fingerprint"}


def _items_modificados(anterior: dict, actual: dict, tipo_componente: str) -> bool:
    return _dict_comparable(anterior, tipo_componente) != _dict_comparable(actual, tipo_componente)


def diff_listas(
    tipo_componente: str,
    anteriores: list[dict],
    actuales: list[dict],
) -> list[CambioHardware]:
    """Indexa por fingerprint; detecta agregado, removido y modificado."""
    map_ant = {i.get("fingerprint"): i for i in anteriores if i.get("fingerprint")}
    map_act = {i.get("fingerprint"): i for i in actuales if i.get("fingerprint")}
    cambios: list[CambioHardware] = []

    for fp, item in map_act.items():
        if fp not in map_ant:
            cambios.append(CambioHardware(tipo_componente, "agregado", fp, None, item))
        elif _items_modificados(map_ant[fp], item, tipo_componente):
            cambios.append(CambioHardware(tipo_componente, "modificado", fp, map_ant[fp], item))

    for fp, item in map_ant.items():
        if fp not in map_act:
            cambios.append(CambioHardware(tipo_componente, "removido", fp, item, None))

    return cambios


def diff_procesador(anterior: dict | None, actual: dict | None) -> list[CambioHardware]:
    if not anterior and not actual:
        return []
    if not anterior and actual:
        fp = actual.get("fingerprint") or fingerprint_procesador(actual)
        return [CambioHardware("procesador", "agregado", fp, None, actual)]
    if anterior and not actual:
        fp = anterior.get("fingerprint") or fingerprint_procesador(anterior)
        return [CambioHardware("procesador", "removido", fp, anterior, None)]
    fp_ant = anterior.get("fingerprint") or fingerprint_procesador(anterior)
    fp_act = actual.get("fingerprint") or fingerprint_procesador(actual)
    if fp_ant != fp_act:
        return [CambioHardware("procesador", "modificado", fp_act, anterior, actual)]
    if _items_modificados(anterior, actual, "procesador"):
        return [CambioHardware("procesador", "modificado", fp_act, anterior, actual)]
    return []


def _payload_evento(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {k: v for k, v in item.items() if k != "fingerprint"}


def cambios_a_eventos_firestore(
    cambios: list[CambioHardware],
    uuid: str,
    hostname: str,
    version_agente: str,
    ttl_dias: int = 90,
) -> list[dict]:
    """Arma payloads listos para emitir_eventos_hardware."""
    ahora = datetime.now(timezone.utc)
    expire = ahora + timedelta(days=ttl_dias)
    eventos = []
    for c in cambios:
        eventos.append({
            "uuid": uuid,
            "hostname": hostname,
            "tipo_componente": c.tipo_componente,
            "tipo_evento": c.tipo_evento,
            "fingerprint": c.fingerprint,
            "antes": _payload_evento(c.antes),
            "despues": _payload_evento(c.despues),
            "origen": "agente",
            "version_agente": version_agente or "?",
            "estado_seguimiento": "pendiente",
            "leido": False,
            "_expire_at_local": expire,
        })
    return eventos


def normalizar_lista_seccion(seccion: str, items: list[dict]) -> list[dict]:
    """Enriquece items con fingerprint y ordena por fingerprint."""
    enriquecidos = [enriquecer_con_fingerprint(seccion, i) for i in items]
    return sorted(enriquecidos, key=lambda x: x.get("fingerprint", ""))
