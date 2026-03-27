"""
Actualización del agente por comando desde Firebase.

No busca actualizaciones solo. Tú disparas la actualización:
  1. En Firestore: config/agente_hw con campo "url" (prioridad); fallback config/agente.
  2. En tareas/{uuid}: comando = "ACTUALIZAR_AGENTE".

El agente descarga ese .exe, se reemplaza y reinicia el servicio.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

SERVICIO_NOMBRE = "AgenteMonitoreo"
_MIN_BYTES_EXE = 100000


def download_and_apply_update(url, uuid=None, hostname=None):
    """
    Descarga el .exe desde url, escribe un .bat que para el servicio,
    reemplaza el exe y arranca de nuevo. Lanza el .bat desacoplado y retorna True.
    El proceso debe terminar después para que el batch pueda reemplazar el exe.
    Solo tiene sentido cuando getattr(sys, 'frozen', False).
    """
    if not getattr(sys, "frozen", False):
        return False

    exe_actual = sys.executable
    carpeta = os.path.dirname(exe_actual)
    nombre_exe = os.path.basename(exe_actual)
    nuevo_exe = os.path.join(carpeta, nombre_exe.replace(".exe", "_new.exe"))

    def _ctx_base():
        try:
            from src.database.firebase_client import VERSION_AGENTE as va

            ver = va or "?"
        except Exception:
            ver = "?"
        p = urlparse(url or "")
        return {
            "url_completa": url or "",
            "url_scheme": p.scheme or "",
            "url_host": p.netloc or "",
            "url_path": (p.path or "")[:300],
            "exe_antes": exe_actual,
            "carpeta_instalacion": carpeta,
            "nombre_exe": nombre_exe,
            "ruta_nuevo_temp": nuevo_exe,
            "version_en_ejecucion": ver,
            "servicio_windows": SERVICIO_NOMBRE,
            "tam_minimo_bytes": _MIN_BYTES_EXE,
        }

    def _log_ok(evento, detalle, ctx=None):
        base = _ctx_base()
        if ctx:
            base.update(ctx)
        try:
            from src.database.firebase_client import registrar_log_actualizacion

            registrar_log_actualizacion(evento, detalle, uuid=uuid, hostname=hostname, extra=base)
        except Exception:
            pass

    def _fail(evento, detalle, ctx=None):
        base = _ctx_base()
        if ctx:
            base.update(ctx)
        try:
            from src.database.firebase_client import fallo_actualizacion_agente_remota

            fallo_actualizacion_agente_remota(uuid, hostname, evento, detalle, base)
        except Exception:
            try:
                from src.database.firebase_client import registrar_log_actualizacion

                registrar_log_actualizacion(evento, detalle, uuid=uuid, hostname=hostname, extra=base)
            except Exception:
                pass

    try:
        from src.database.firebase_client import log_centralizado

        log_centralizado("Info", "Update", f"Descarga de actualización iniciada → {urlparse(url or '').netloc or url[:60]}")
    except Exception:
        pass

    _log_ok(
        "DESCARGA_INICIADA",
        f"GET stream timeout=120s hacia host {urlparse(url or '').netloc or '(sin host)'}",
    )

    try:
        import requests

        r = requests.get(url, timeout=120, stream=True)
        hdr_status = r.status_code
        hdr_ct = (r.headers.get("Content-Type") or "").strip()
        hdr_cl = (r.headers.get("Content-Length") or "").strip()
        try:
            r.raise_for_status()
        except requests.HTTPError as he:
            body = ""
            if he.response is not None:
                try:
                    body = (he.response.text or "")[:400]
                except Exception:
                    body = ""
            _fail(
                "DESCARGA_HTTP_ERROR",
                f"HTTP {hdr_status} al descargar la actualización: {he!s}",
                {
                    "http_status": hdr_status,
                    "http_content_type": hdr_ct,
                    "http_content_length_header": hdr_cl,
                    "http_body_snippet": body,
                },
            )
            try:
                r.close()
            except Exception:
                pass
            try:
                os.remove(nuevo_exe)
            except Exception:
                pass
            return False

        sha = hashlib.sha256()
        nbytes = 0
        try:
            with open(nuevo_exe, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        sha.update(chunk)
                        nbytes += len(chunk)
        finally:
            try:
                r.close()
            except Exception:
                pass

    except Exception as e:
        tipo = type(e).__name__
        _fail(
            "DESCARGA_FALLIDA",
            f"{tipo}: {e!s}",
            {"tipo_excepcion": tipo},
        )
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    sha_hex = sha.hexdigest()
    if not os.path.isfile(nuevo_exe) or nbytes < _MIN_BYTES_EXE:
        tam = os.path.getsize(nuevo_exe) if os.path.isfile(nuevo_exe) else 0
        _fail(
            "DESCARGA_ARCHIVO_INVALIDO",
            f"Tamaño en disco {tam} bytes (mínimo exigido {_MIN_BYTES_EXE}); descarga incompleta o URL incorrecta.",
            {
                "bytes_escritos": nbytes,
                "bytes_en_disco": tam,
                "sha256": sha_hex,
            },
        )
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    _log_ok(
        "DESCARGA_EXITOSA",
        f"HTTP {hdr_status}; {nbytes} bytes; SHA256={sha_hex}",
        {
            "http_status": hdr_status,
            "http_content_type": hdr_ct,
            "http_content_length_header": hdr_cl,
            "bytes_descargados": nbytes,
            "sha256": sha_hex,
        },
    )

    from src.database.firebase_client import FLAG_POST_AGENT_UPDATE

    flag_path = os.path.join(carpeta, FLAG_POST_AGENT_UPDATE)
    espera_ping = 6
    bat_lines = [
        "@echo off",
        f"ping 127.0.0.1 -n {espera_ping + 1} > nul",
        f'sc stop "{SERVICIO_NOMBRE}"',
        "timeout /t 5 /nobreak > nul",
        # Forzar terminación si el proceso sigue vivo
        f'taskkill /IM "{nombre_exe}" /F >nul 2>&1',
        "timeout /t 3 /nobreak > nul",
        # Reintentar copy hasta 3 veces (el exe puede tardar en liberarse)
        f'copy /Y "{nuevo_exe}" "{exe_actual}"',
        "if not errorlevel 1 goto :copy_ok",
        "timeout /t 5 /nobreak > nul",
        f'copy /Y "{nuevo_exe}" "{exe_actual}"',
        "if not errorlevel 1 goto :copy_ok",
        "timeout /t 5 /nobreak > nul",
        f'copy /Y "{nuevo_exe}" "{exe_actual}"',
        "if not errorlevel 1 goto :copy_ok",
        # Si los 3 intentos fallaron, arrancar el servicio con el exe viejo
        f'sc start "{SERVICIO_NOMBRE}"',
        "goto :cleanup",
        ":copy_ok",
        f'type nul > "{flag_path}"',
        f'sc start "{SERVICIO_NOMBRE}"',
        ":cleanup",
        f'del /F /Q "{nuevo_exe}"',
        "del /F /Q \"%~f0\"",
    ]
    bat_content = "\r\n".join(bat_lines)
    fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="agente_update_", text=True)
    try:
        os.write(fd, bat_content.encode("utf-8"))
        os.close(fd)
    except Exception as e:
        _fail(
            "ERROR_BAT_ESCRITURA",
            f"No se pudo crear el script de reemplazo: {e!s}",
            {"bat_path_temp": bat_path, "tipo_excepcion": type(e).__name__},
        )
        os.close(fd)
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    try:
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
            cwd=os.path.dirname(bat_path),
        )
        _log_ok(
            "REEMPLAZO_INICIADO",
            f".bat lanzado (desacoplado): espera ~{espera_ping}s, sc stop, copy al exe en uso, flag si copy OK, sc start, borra _new y el .bat.",
            {
                "bat_path_temp": bat_path,
                "espera_inicial_seg": espera_ping,
                "espera_tras_stop_seg": espera_stop,
                "flag_marcador": flag_path,
                "sha256_descarga": sha_hex,
                "bytes_a_instalar": nbytes,
            },
        )
    except Exception as e:
        _fail(
            "ERROR_BAT_EJECUCION",
            f"No se pudo lanzar el proceso cmd con el .bat: {e!s}",
            {"bat_path_temp": bat_path, "tipo_excepcion": type(e).__name__},
        )
        try:
            os.remove(bat_path)
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    return True
