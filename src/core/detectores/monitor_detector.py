"""Detector de cambios en monitores — v2: solo alertar lo nuevo.

Emite 'agregado' inmediato, 'modificado' inmediato, 'removido' diferido
(solo tras N horas de ausencia continua). Evita falsos positivos por
monitores apagados desde el boton fisico (limitacion HPD).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.hardware_diff import CambioHardware

_CAMPOS_IGNORAR = frozenset({"resolucion", "ultima_vez_visto", "fingerprint"})


def _comparable(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in _CAMPOS_IGNORAR}


def _parse_iso(ts: str | None, fallback: datetime) -> datetime:
    if not ts:
        return fallback
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return fallback


def detectar_cambios_monitores(
    anteriores: list[dict],
    actuales: list[dict],
    umbral_horas: int = 48,
    ahora: datetime | None = None,
) -> tuple[list[CambioHardware], list[dict]]:
    """Retorna (cambios, monitores_para_snapshot).

    - agregado:   fingerprint nuevo → inmediato
    - modificado: campos no-volatiles cambiaron → inmediato
    - removido:   ausente mas de umbral_horas → diferido
    """
    if ahora is None:
        ahora = datetime.now(timezone.utc)
    ahora_iso = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")

    map_ant = {i["fingerprint"]: i for i in anteriores if i.get("fingerprint")}
    map_act = {i["fingerprint"]: i for i in actuales if i.get("fingerprint")}

    cambios: list[CambioHardware] = []
    monitores_snapshot: list[dict] = []

    for fp, item in map_act.items():
        entry = dict(item)
        entry["ultima_vez_visto"] = ahora_iso

        if fp not in map_ant:
            cambios.append(CambioHardware("monitor", "agregado", fp, None, item))
        elif _comparable(map_ant[fp]) != _comparable(item):
            cambios.append(CambioHardware("monitor", "modificado", fp, map_ant[fp], item))

        monitores_snapshot.append(entry)

    for fp, item in map_ant.items():
        if fp not in map_act:
            visto = _parse_iso(item.get("ultima_vez_visto"), fallback=ahora)
            horas_ausente = (ahora - visto).total_seconds() / 3600

            if horas_ausente >= umbral_horas:
                cambios.append(CambioHardware("monitor", "removido", fp, item, None))
            else:
                kept = dict(item)
                if "ultima_vez_visto" not in kept:
                    kept["ultima_vez_visto"] = ahora_iso
                monitores_snapshot.append(kept)

    return cambios, monitores_snapshot
