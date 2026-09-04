"""Orquestador de auditoría de hardware: snapshot, diff, emisión a Firestore."""

from __future__ import annotations

from datetime import datetime, timezone

from config.config import HARDWARE_AUDIT_ENABLED, HARDWARE_AUDIT_TTL_DIAS
from src.core import hardware_snapshot
from src.core.hardware_diff import (
    CambioHardware,
    cambios_a_eventos_firestore,
    diff_listas,
    normalizar_lista_seccion,
)
from src.core.hardware_fingerprint import enriquecer_con_fingerprint
from src.core.detectores.disco_detector import detectar_cambios_discos
from src.core.detectores.monitor_detector import detectar_cambios_monitores
from src.core.detectores.procesador_detector import detectar_cambios_procesador
from src.core.detectores.ram_detector import detectar_cambios_ram
from src.core.scanner import obtener_secciones_auditoria

SECCIONES_CICLO = ("monitores", "ram", "discos")
SECCIONES_MONITORES = ("monitores",)
SECCIONES_ARRANQUE = ("procesador",)

_SECCION_A_TIPO = {
    "monitores": "monitor",
    "ram": "ram",
    "discos": "disco",
    "procesador": "procesador",
}

_DETECTORES_LISTA = {
    "monitores": detectar_cambios_monitores,
    "ram": detectar_cambios_ram,
    "discos": detectar_cambios_discos,
}


def _audit_log(mensaje: str) -> None:
    try:
        from src.database.firebase_client import log_debug
        log_debug(mensaje)
    except Exception:
        pass


def _seccion_en_snapshot(anterior: dict, sec: str) -> bool:
    """True si la sección ya existía en un snapshot previo (baseline hecho)."""
    return sec in anterior


def construir_snapshot_actual(datos_pc: dict, secciones: tuple) -> dict:
    """Retorna dict con version, actualizado_en, y solo las secciones pedidas."""
    secciones_raw = obtener_secciones_auditoria(datos_pc)
    snap: dict = {
        "version": 1,
        "actualizado_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for sec in secciones:
        if sec == "procesador":
            proc = secciones_raw.get("procesador") or {}
            if proc:
                snap["procesador"] = enriquecer_con_fingerprint("procesador", proc)
        elif sec in secciones_raw:
            snap[sec] = normalizar_lista_seccion(sec, secciones_raw.get(sec) or [])
    return snap


def _merge_snapshots(anterior: dict, actual: dict, secciones: tuple) -> dict:
    """Fusiona secciones actualizadas sobre snapshot previo."""
    merged = dict(anterior)
    merged["version"] = actual.get("version", 1)
    merged["actualizado_en"] = actual.get("actualizado_en")
    for sec in secciones:
        if sec in actual:
            merged[sec] = actual[sec]
    return merged


def detectar_cambios(
    snapshot_anterior: dict,
    snapshot_actual: dict,
    secciones: tuple,
) -> list[CambioHardware]:
    """Combina diffs por sección; retorna cambios detectados (sin escribir)."""
    cambios: list[CambioHardware] = []

    for sec in secciones:
        if not _seccion_en_snapshot(snapshot_anterior, sec):
            continue
        if sec == "procesador":
            cambios.extend(
                detectar_cambios_procesador(
                    snapshot_anterior.get("procesador"),
                    snapshot_actual.get("procesador"),
                )
            )
        elif sec in _DETECTORES_LISTA:
            ant = snapshot_anterior.get(sec) or []
            act = snapshot_actual.get(sec) or []
            cambios.extend(_DETECTORES_LISTA[sec](ant, act))
        else:
            tipo = _SECCION_A_TIPO.get(sec, sec)
            ant = snapshot_anterior.get(sec) or []
            act = snapshot_actual.get(sec) or []
            cambios.extend(diff_listas(tipo, ant, act))

    return cambios


def _emitir_si_hay(eventos_raw: list[CambioHardware], uuid: str, hostname: str, version_agente: str) -> bool:
    if not eventos_raw:
        return True
    from src.database.firebase_client import emitir_eventos_hardware

    payloads = cambios_a_eventos_firestore(
        eventos_raw,
        uuid,
        hostname,
        version_agente,
        ttl_dias=HARDWARE_AUDIT_TTL_DIAS,
    )
    return emitir_eventos_hardware(payloads)


def procesar_auditoria_hardware(
    datos_pc: dict,
    uuid: str,
    hostname: str,
    secciones: tuple = SECCIONES_CICLO,
    version_agente: str = "?",
) -> list[CambioHardware]:
    """
    Flujo completo: cargar snapshot, comparar, emitir eventos, guardar snapshot.
    Retorna lista de cambios detectados (vacía en baseline).
    """
    if not HARDWARE_AUDIT_ENABLED:
        return []

    try:
        snapshot_actual = construir_snapshot_actual(datos_pc, secciones)
    except Exception as e:
        _audit_log(f"AUDIT_ERROR — construir snapshot: {type(e).__name__}: {e}")
        return []

    try:
        snapshot_anterior = hardware_snapshot.cargar()
    except Exception as e:
        _audit_log(f"AUDIT_ERROR — cargar snapshot: {type(e).__name__}: {e}")
        return []

    if snapshot_anterior is None:
        if hardware_snapshot.guardar(snapshot_actual):
            _audit_log(f"AUDIT_BASELINE — secciones={','.join(secciones)} uuid={uuid}")
        else:
            _audit_log(f"AUDIT_BASELINE_FAIL — uuid={uuid}")
        return []

    try:
        cambios = detectar_cambios(snapshot_anterior, snapshot_actual, secciones)
    except Exception as e:
        _audit_log(f"AUDIT_ERROR — detectar cambios: {type(e).__name__}: {e}")
        return []

    if cambios:
        emit_ok = _emitir_si_hay(cambios, uuid, hostname, version_agente)
        if not emit_ok:
            _audit_log(
                f"AUDIT_EMIT_RETRY — {len(cambios)} cambio(s) pendientes; "
                "snapshot no actualizado"
            )
            return cambios

    snapshot_final = _merge_snapshots(snapshot_anterior, snapshot_actual, secciones)
    if not hardware_snapshot.guardar(snapshot_final):
        if cambios:
            _audit_log(
                "AUDIT_SNAPSHOT_FAIL — eventos emitidos OK pero snapshot local no persistido; "
                "posibles duplicados hasta próximo ciclo"
            )
        else:
            _audit_log("AUDIT_SNAPSHOT_FAIL — sin cambios pero falló guardar snapshot")
    return cambios


def procesar_auditoria_procesador(
    datos_pc: dict,
    uuid: str,
    hostname: str,
    version_agente: str = "?",
) -> list[CambioHardware]:
    """Diff de CPU solo al arranque del servicio."""
    return procesar_auditoria_hardware(
        datos_pc,
        uuid,
        hostname,
        secciones=SECCIONES_ARRANQUE,
        version_agente=version_agente,
    )
