"""
Actualización del agente por comando desde Firebase.

No busca actualizaciones solo. Tú disparas la actualización:
  1. En Firestore: config/agente con campo "url" (URL pública del .exe).
  2. En tareas/{uuid}: comando = "ACTUALIZAR_AGENTE".

El agente descarga ese .exe, se reemplaza y reinicia el servicio.
"""
import os
import sys
import subprocess
import tempfile

SERVICIO_NOMBRE = "AgenteMonitoreo"


def download_and_apply_update(url, uuid=None, hostname=None):
    """
    Descarga el .exe desde url, escribe un .bat que para el servicio,
    reemplaza el exe y arranca de nuevo. Lanza el .bat desacoplado y retorna True.
    El proceso debe terminar después para que el batch pueda reemplazar el exe.
    Solo tiene sentido cuando getattr(sys, 'frozen', False).
    """
    def _log(evento, detalle=""):
        try:
            from src.database.firebase_client import registrar_log_actualizacion
            registrar_log_actualizacion(evento, detalle, uuid=uuid, hostname=hostname)
        except Exception:
            pass

    if not getattr(sys, "frozen", False):
        return False
    exe_actual = sys.executable
    carpeta = os.path.dirname(exe_actual)
    nombre_exe = os.path.basename(exe_actual)
    nuevo_exe = os.path.join(carpeta, nombre_exe.replace(".exe", "_new.exe"))

    _log("DESCARGA_INICIADA", f"Descargando desde: {url[:80]}")
    try:
        import requests
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        try:
            with open(nuevo_exe, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        finally:
            r.close()  # Liberar conexión y buffers
    except Exception as e:
        _log("DESCARGA_FALLIDA", f"Error al descargar: {e}")
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    if not os.path.isfile(nuevo_exe) or os.path.getsize(nuevo_exe) < 100000:
        _log("DESCARGA_FALLIDA", "Archivo descargado inválido o demasiado pequeño")
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    _log("DESCARGA_EXITOSA", f"Archivo descargado: {os.path.getsize(nuevo_exe)} bytes")

    # Batch: esperar, parar servicio, copiar exe, arrancar servicio
    bat_lines = [
        "@echo off",
        "ping 127.0.0.1 -n 6 > nul",
        f'sc stop "{SERVICIO_NOMBRE}"',
        "timeout /t 3 /nobreak > nul",
        f'copy /Y "{nuevo_exe}" "{exe_actual}"',
        f'sc start "{SERVICIO_NOMBRE}"',
        f'del /F /Q "{nuevo_exe}"',
        "del /F /Q \"%~f0\"",
    ]
    bat_content = "\r\n".join(bat_lines)
    fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="agente_update_", text=True)
    try:
        os.write(fd, bat_content.encode("utf-8"))
        os.close(fd)
    except Exception as e:
        _log("ERROR", f"Error creando script de instalación: {e}")
        os.close(fd)
        try:
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    # Lanzar batch desacoplado (no esperar, no matar al cerrar)
    try:
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
            cwd=os.path.dirname(bat_path),
        )
        _log("REEMPLAZO_INICIADO", "Script de reemplazo lanzado; el servicio se reiniciará")
    except Exception as e:
        _log("ERROR", f"Error lanzando script de instalación: {e}")
        try:
            os.remove(bat_path)
            os.remove(nuevo_exe)
        except Exception:
            pass
        return False

    return True
