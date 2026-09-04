"""Fingerprints estables por componente de hardware para auditoría."""

import re


def _serial_valido(serial: str | None) -> bool:
    s = (serial or "").strip()
    if not s:
        return False
    return not set(s) <= {"0"}


def _normalizar_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", (nombre or "").strip().lower())


def fingerprint_monitor(m: dict) -> str:
    serial = (m.get("numero_serie") or "").strip()
    if _serial_valido(serial):
        return f"SN:{serial}"
    instance = (m.get("instance_name") or "").strip()
    if instance:
        return f"INST:{instance}"
    fabricante = (m.get("fabricante") or "").strip()
    pulgadas = m.get("pulgadas") or 0
    nombre = _normalizar_nombre(m.get("nombre") or "")
    return f"FALLBACK:{fabricante}|{pulgadas}|{nombre}"


def fingerprint_ram(m: dict) -> str:
    locator = (m.get("locator") or m.get("slot") or "N/A").strip()
    serial = (m.get("numero_serie") or "").strip()
    if serial and serial != "N/A" and _serial_valido(serial):
        return f"RAM:{locator}|SN:{serial}"
    capacidad = m.get("capacidad_gb") or 0
    modelo = (m.get("modelo") or "N/A").strip()
    return f"RAM:{locator}|{capacidad}|{modelo}"


def fingerprint_disco(d: dict) -> str:
    serial = (d.get("numero_serie") or "").strip()
    if _serial_valido(serial):
        return f"DISK:SN:{serial}"
    device_id = str(d.get("device_id") or "").strip()
    modelo = (d.get("modelo") or "Desconocido").strip()
    tipo = (d.get("tipo") or "Desconocido").strip()
    return f"DISK:{device_id}|{modelo}|{tipo}"


def fingerprint_procesador(p: dict) -> str:
    nombre = (p.get("nombre_completo") or "Desconocido").strip()
    nucleos = p.get("nucleos_fisicos") or 0
    return f"CPU:{nombre}|{nucleos}"


def enriquecer_con_fingerprint(seccion: str, item: dict) -> dict:
    """Añade campo fingerprint al dict del snapshot."""
    resultado = dict(item)
    if seccion == "monitores":
        resultado["fingerprint"] = fingerprint_monitor(item)
    elif seccion == "ram":
        resultado["fingerprint"] = fingerprint_ram(item)
    elif seccion == "discos":
        resultado["fingerprint"] = fingerprint_disco(item)
    elif seccion == "procesador":
        resultado["fingerprint"] = fingerprint_procesador(item)
    return resultado
