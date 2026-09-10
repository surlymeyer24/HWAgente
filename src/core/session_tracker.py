"""Tracking de estado de sesión — estudio de bloqueo de PCs.

Detecta si la sesión de consola está activa (desbloqueada), bloqueada
o sin usuario. Acumula estadísticas diarias para entender el patrón
real de uso y bloqueo del parque.
"""

from __future__ import annotations

import ctypes
import time
from datetime import date

import psutil

_estado_anterior: str | None = None
_estado_desde: float | None = None
_resumen: dict | None = None
_fecha_resumen: str | None = None
_timeout_leido: bool = False
_timeout_cache: int | None = None


def _detectar_estado_sesion() -> str:
    """Detecta estado de la sesión de consola desde un servicio Windows (Session 0).

    - "activa": usuario logueado con escritorio desbloqueado
    - "bloqueada": usuario logueado pero pantalla bloqueada (LogonUI corriendo)
    - "sin_usuario": no hay sesión de consola activa
    """
    try:
        session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        if session_id == 0xFFFFFFFF:
            return "sin_usuario"
    except Exception:
        return "sin_usuario"

    try:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == 'logonui.exe':
                    return "bloqueada"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    return "activa"


def _leer_timeout_bloqueo() -> int | None:
    """Lee el timeout de bloqueo automático configurado (minutos).

    Busca en GPO (HKLM) y screensaver seguro del usuario (HKEY_USERS).
    Retorna el menor timeout encontrado, o None si no hay bloqueo configurado.
    """
    import winreg

    timeouts: list[int] = []

    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
        )
        valor, _ = winreg.QueryValueEx(key, "InactivityTimeoutSecs")
        winreg.CloseKey(key)
        if isinstance(valor, int) and valor > 0:
            timeouts.append(valor // 60)
    except (FileNotFoundError, OSError):
        pass

    try:
        i = 0
        while True:
            try:
                sid = winreg.EnumKey(winreg.HKEY_USERS, i)
            except OSError:
                break
            i += 1

            if sid.startswith('.') or sid.endswith('_Classes') or len(sid) < 20:
                continue

            try:
                desk_key = winreg.OpenKey(
                    winreg.HKEY_USERS,
                    f"{sid}\\Control Panel\\Desktop",
                )
                try:
                    secure, _ = winreg.QueryValueEx(desk_key, "ScreenSaverIsSecure")
                    is_secure = str(secure) == "1"
                except (FileNotFoundError, OSError):
                    is_secure = False

                if is_secure:
                    try:
                        timeout_str, _ = winreg.QueryValueEx(desk_key, "ScreenSaveTimeOut")
                        timeout_sec = int(timeout_str)
                        if timeout_sec > 0:
                            timeouts.append(timeout_sec // 60)
                    except (FileNotFoundError, OSError, ValueError):
                        pass

                winreg.CloseKey(desk_key)
            except (FileNotFoundError, OSError):
                pass
    except Exception:
        pass

    return min(timeouts) if timeouts else None


def _resetear_resumen() -> dict:
    return {
        "fecha": date.today().isoformat(),
        "horas_activa": 0.0,
        "horas_bloqueada": 0.0,
        "horas_sin_usuario": 0.0,
        "transiciones": 0,
        "max_horas_activa_continua": 0.0,
        "_racha_activa": 0.0,
    }


def obtener_datos_sesion() -> dict:
    """Datos de sesión para incluir en el payload de cada ciclo.

    Retorna dict con sesion_estado, sesion_bloqueo_auto_min
    y sesion_resumen_hoy.
    """
    global _estado_anterior, _estado_desde
    global _resumen, _fecha_resumen
    global _timeout_leido, _timeout_cache

    ahora = time.time()
    estado = _detectar_estado_sesion()

    if not _timeout_leido:
        try:
            _timeout_cache = _leer_timeout_bloqueo()
        except Exception:
            _timeout_cache = None
        _timeout_leido = True

    hoy = date.today().isoformat()
    if _resumen is None or _fecha_resumen != hoy:
        _resumen = _resetear_resumen()
        _fecha_resumen = hoy
        _estado_anterior = None
        _estado_desde = None

    if _estado_anterior is not None and _estado_desde is not None:
        duracion_horas = (ahora - _estado_desde) / 3600

        if _estado_anterior == "activa":
            _resumen["horas_activa"] += duracion_horas
            _resumen["_racha_activa"] += duracion_horas
        elif _estado_anterior == "bloqueada":
            _resumen["horas_bloqueada"] += duracion_horas
            _resumen["_racha_activa"] = 0.0
        elif _estado_anterior == "sin_usuario":
            _resumen["horas_sin_usuario"] += duracion_horas
            _resumen["_racha_activa"] = 0.0

        if estado != _estado_anterior:
            _resumen["transiciones"] += 1
            if _estado_anterior == "activa":
                if _resumen["_racha_activa"] > _resumen["max_horas_activa_continua"]:
                    _resumen["max_horas_activa_continua"] = _resumen["_racha_activa"]
                _resumen["_racha_activa"] = 0.0

    _estado_anterior = estado
    _estado_desde = ahora

    if estado == "activa" and _resumen["_racha_activa"] > _resumen["max_horas_activa_continua"]:
        _resumen["max_horas_activa_continua"] = _resumen["_racha_activa"]

    resumen_output = {
        k: (round(v, 2) if isinstance(v, float) else v)
        for k, v in _resumen.items()
        if not k.startswith("_")
    }

    return {
        "sesion_estado": estado,
        "sesion_bloqueo_auto_min": _timeout_cache,
        "sesion_resumen_hoy": resumen_output,
    }
