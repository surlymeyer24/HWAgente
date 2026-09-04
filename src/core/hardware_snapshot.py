"""Persistencia local del snapshot de hardware (registro Windows + fallback archivo)."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

_REGISTRY_KEY = r"SOFTWARE\AgenteBacar"
_REGISTRY_VALUE = "hardware_snapshot"
_REGISTRY_STORAGE = "hardware_snapshot_storage"
_FILE_PATH = r"C:\ProgramData\AgenteBacar\hardware_snapshot.json"
_SIZE_WARN_BYTES = 12 * 1024
_SCHEMA_VERSION = 1

_cache_memoria: dict | None = None


def _log(mensaje: str) -> None:
    try:
        path = "C:\\agente_debug.txt" if os.path.exists("C:\\") else "agente_debug.txt"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.ctime()}: [HardwareSnapshot] {mensaje}\n")
    except Exception:
        pass


def _leer_registro_valor(nombre: str) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY) as k:
            val, _ = winreg.QueryValueEx(k, nombre)
            return val.strip() if val and str(val).strip() else None
    except Exception:
        return None


def _escribir_registro_valor(nombre: str, valor: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY) as k:
            winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, valor)
        return True
    except Exception as e:
        _log(f"No se pudo escribir registro {nombre}: {e}")
        return False


def _leer_registro() -> str | None:
    return _leer_registro_valor(_REGISTRY_VALUE)


def _leer_archivo() -> str | None:
    try:
        if os.path.isfile(_FILE_PATH):
            with open(_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        _log(f"Error leyendo archivo snapshot: {e}")
    return None


def _escribir_archivo(json_str: str) -> bool:
    try:
        os.makedirs(os.path.dirname(_FILE_PATH), exist_ok=True)
        with open(_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(json_str)
        return True
    except Exception as e:
        _log(f"Error escribiendo archivo snapshot: {e}")
        return False


def _normalizar_snapshot(raw: dict) -> dict:
    """Asegura version, actualizado_en ISO8601 UTC."""
    snap = dict(raw)
    snap["version"] = _SCHEMA_VERSION
    snap["actualizado_en"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for lista in ("monitores", "ram", "discos"):
        if lista in snap and isinstance(snap[lista], list):
            snap[lista] = sorted(
                snap[lista],
                key=lambda x: x.get("fingerprint", "") if isinstance(x, dict) else "",
            )
    return snap


def invalidar_cache() -> None:
    global _cache_memoria
    _cache_memoria = None


def borrar_persistencia() -> None:
    """Elimina snapshot local (p. ej. tras RESETEAR_ID)."""
    global _cache_memoria
    _cache_memoria = None
    if sys.platform != "win32":
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
            for nombre in (_REGISTRY_VALUE, _REGISTRY_STORAGE):
                try:
                    winreg.DeleteValue(k, nombre)
                except FileNotFoundError:
                    pass
    except Exception as e:
        _log(f"Error borrando snapshot del registro: {e}")
    try:
        if os.path.isfile(_FILE_PATH):
            os.remove(_FILE_PATH)
    except Exception as e:
        _log(f"Error borrando archivo snapshot: {e}")


def cargar() -> dict | None:
    """Memoria → registro → archivo. None si no existe (baseline)."""
    global _cache_memoria
    if _cache_memoria is not None:
        return _cache_memoria

    storage = _leer_registro_valor(_REGISTRY_STORAGE)
    json_str = None

    if storage == "file":
        json_str = _leer_archivo()
    if not json_str:
        json_str = _leer_registro()
    if not json_str:
        json_str = _leer_archivo()

    if not json_str:
        return None

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            _cache_memoria = data
            return data
    except json.JSONDecodeError as e:
        _log(f"Snapshot corrupto: {e}")
    return None


def guardar(snapshot: dict) -> bool:
    """Serializa JSON compacto, valida tamaño, escribe registro o fallback file."""
    global _cache_memoria
    snap = _normalizar_snapshot(snapshot)
    json_str = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    size = len(json_str.encode("utf-8"))

    if size > _SIZE_WARN_BYTES:
        _log(f"ADVERTENCIA: snapshot JSON {size} bytes (> {_SIZE_WARN_BYTES}); usando archivo fallback")

    ok = False
    if size <= _SIZE_WARN_BYTES:
        ok = _escribir_registro_valor(_REGISTRY_VALUE, json_str)
        if ok:
            _escribir_registro_valor(_REGISTRY_STORAGE, "registry")

    if not ok:
        ok = _escribir_archivo(json_str)
        if ok:
            _escribir_registro_valor(_REGISTRY_STORAGE, "file")
            # Puntero mínimo en registro si cabe
            if size > _SIZE_WARN_BYTES:
                _escribir_registro_valor(_REGISTRY_VALUE, '{"storage":"file"}')

    if ok:
        _cache_memoria = snap
        _log("AUDIT_SNAPSHOT_SAVED")
    else:
        _log("AUDIT_SNAPSHOT_FAIL")

    return ok
