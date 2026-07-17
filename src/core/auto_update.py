"""
Actualización del agente por comando desde Firebase.

No busca actualizaciones solo. Tú disparas la actualización:
  1. En Firestore: config/agente_hw con campo "url" (prioridad); fallback config/agente.
  2. En tareas/{uuid}: comando = "ACTUALIZAR_AGENTE".

El agente descarga ese .exe, se reemplaza y reinicia el servicio.

SEGURIDAD:
  - La URL de descarga debe usar HTTPS y estar en la whitelist de dominios (config.UPDATE_ALLOWED_DOMAINS).
  - El campo sha256 en Firestore es OBLIGATORIO; si falta, la actualización se rechaza antes de descargar.
  - El campo firma (ECDSA P-256) en Firestore es OBLIGATORIO; si falta o es inválida, el binario se borra.
"""
import hashlib
import ipaddress
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

SERVICIO_NOMBRE = "AgenteMonitoreo"
_MIN_BYTES_EXE = 100000


def _validar_url_segura(url: str) -> str | None:
    """
    Valida que la URL sea segura antes de intentar cualquier descarga.
    Retorna None si es válida, o un string con el motivo del rechazo.

    Controles:
      1. Esquema debe ser 'https' (no http, ftp, file, etc.).
      2. El host no puede ser una IP privada, loopback ni link-local.
      3. El host debe pertenecer a la whitelist UPDATE_ALLOWED_DOMAINS.
    """
    try:
        from config.config import UPDATE_ALLOWED_DOMAINS
    except Exception:
        UPDATE_ALLOWED_DOMAINS = [
            "objects.githubusercontent.com",
            "github.com",
            "releases.githubusercontent.com",
            "api.github.com",
        ]

    if not url or not url.strip():
        return "URL vacía."

    p = urlparse(url.strip())

    # 1. Solo HTTPS
    if p.scheme != "https":
        return (
            f"Esquema no permitido: '{p.scheme}'. "
            "Solo se acepta 'https'. Posible intento de intercepción o URL maliciosa."
        )

    host = (p.hostname or "").lower()
    if not host:
        return "URL sin host válido."

    # 2. Bloquear IPs privadas / loopback / link-local
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast:
            return (
                f"IP no pública no permitida: '{host}'. "
                "Las actualizaciones solo pueden descargarse desde hosts públicos."
            )
    except ValueError:
        pass  # Es un nombre de dominio, no una IP — continuar

    # 3. Whitelist de dominios
    dominios_permitidos = [d.lower() for d in UPDATE_ALLOWED_DOMAINS]
    if not any(
        host == dominio or host.endswith("." + dominio)
        for dominio in dominios_permitidos
    ):
        return (
            f"Dominio '{host}' no está en la whitelist de dominios permitidos: "
            f"{dominios_permitidos}. "
            "Actualizá UPDATE_ALLOWED_DOMAINS en config/config.py si el dominio es legítimo."
        )

    return None  # URL válida


# CLAVE PÚBLICA PARA VERIFICAR FIRMAS DIGITALES (Reemplazar con la generada por el script)
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAESWeBodI+wXtNdNr5yffdepePfjQN75hwF/cJBkH4
k/WwQ3Dsan21CiUeseXQuxlDdmsaayhzmR/WcmFy9Al1Hg==
-----END PUBLIC KEY-----"""

def _comparar_versiones(local: str, remota: str) -> bool:
    """Retorna True si la versión remota es más nueva que la local."""
    def _parsear(v: str):
        limpio = v.strip().lstrip("vV")
        partes = []
        for p in limpio.split("."):
            try:
                partes.append(int(p))
            except ValueError:
                partes.append(0)
        return tuple(partes)

    try:
        return _parsear(remota) > _parsear(local)
    except Exception:
        return False


def verificar_actualizacion_al_inicio(uuid=None, hostname=None):
    """
    Verifica en Firestore si hay una versión más nueva del agente.
    Si la hay, dispara la descarga y actualización automáticamente.
    Retorna True si se programó una actualización, False en caso contrario.
    No lanza excepciones — cualquier error se loguea y retorna False.
    """
    try:
        from src.database.firebase_client import (
            _leer_url_y_meta_actualizacion_agente,
            VERSION_AGENTE,
            log_debug,
            registrar_log_actualizacion,
        )

        version_local = VERSION_AGENTE or ""
        if not version_local:
            log_debug("Auto-update inicio: no se pudo determinar la versión local, se omite verificación.")
            return False

        url, meta = _leer_url_y_meta_actualizacion_agente()
        version_remota = meta.get("version_publicada_config") or ""

        if not version_remota:
            log_debug("Auto-update inicio: no hay versión publicada en config/agente_hw, se omite.")
            return False

        if not _comparar_versiones(version_local, version_remota):
            log_debug(
                f"Auto-update inicio: versión local ({version_local}) >= remota ({version_remota}), no se actualiza."
            )
            return False

        if not url:
            log_debug(
                f"Auto-update inicio: versión remota ({version_remota}) > local ({version_local}) "
                f"pero no hay URL de descarga configurada."
            )
            return False

        sha256 = meta.get("sha256_esperado")
        firma = meta.get("firma_esperada")

        registrar_log_actualizacion(
            "AUTO_UPDATE_INICIO_DETECTADO",
            f"Versión remota ({version_remota}) > local ({version_local}). Iniciando actualización automática.",
            uuid=uuid,
            hostname=hostname,
            extra={
                "version_local": version_local,
                "version_remota": version_remota,
                "url": (url or "")[:200],
                "tiene_sha256": bool(sha256),
                "tiene_firma": bool(firma),
            },
        )

        exito = download_and_apply_update(
            url,
            uuid=uuid,
            hostname=hostname,
            sha256_esperado=sha256,
            firma_esperada=firma,
        )

        if exito:
            log_debug(
                f"Auto-update inicio: actualización de {version_local} → {version_remota} programada; "
                f"reinicio en breve."
            )
        else:
            log_debug("Auto-update inicio: download_and_apply_update retornó False.")

        return exito

    except Exception as e:
        try:
            from src.database.firebase_client import log_debug

            log_debug(f"Auto-update inicio: excepción no bloqueante — {type(e).__name__}: {e}")
        except Exception:
            pass
        return False


def download_and_apply_update(url, uuid=None, hostname=None, sha256_esperado=None, firma_esperada=None):
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
            "sha256_esperado": sha256_esperado,
            "firma_esperada": firma_esperada,
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

    # -----------------------------------------------------------------------
    # BLOQUE DE SEGURIDAD — todas las validaciones ANTES de tocar la red
    # -----------------------------------------------------------------------

    # 1. Validar URL (esquema, dominio, no IPs privadas)
    error_url = _validar_url_segura(url or "")
    if error_url:
        _fail(
            "SEGURIDAD_URL_INVALIDA",
            f"URL rechazada por política de seguridad: {error_url}",
            {"url_rechazada": (url or "")[:200], "motivo": error_url},
        )
        return False

    # 2. SHA-256 obligatorio — sin él no se puede verificar integridad
    if not sha256_esperado or not sha256_esperado.strip():
        _fail(
            "SEGURIDAD_SHA256_REQUERIDO",
            "El campo 'sha256' no está presente en config/agente_hw de Firestore. "
            "La actualización fue rechazada por política de seguridad. "
            "Usá scripts/firmar_release.py para generar SHA-256 y firma antes de publicar.",
            {"url": (url or "")[:200]},
        )
        return False

    # 3. Firma ECDSA obligatoria — sin ella no se puede verificar autenticidad
    if not firma_esperada or not firma_esperada.strip():
        _fail(
            "SEGURIDAD_FIRMA_REQUERIDA",
            "El campo 'firma' (ECDSA P-256) no está presente en config/agente_hw de Firestore. "
            "La actualización fue rechazada por política de seguridad. "
            "Usá scripts/firmar_release.py para generar SHA-256 y firma antes de publicar.",
            {"url": (url or "")[:200], "sha256_recibido": (sha256_esperado or "")[:20] + "..."},
        )
        return False

    # -----------------------------------------------------------------------
    # Fin bloque de seguridad — proceder con la descarga
    # -----------------------------------------------------------------------

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

    if sha256_esperado:
        if sha_hex.lower() != sha256_esperado.lower():
            _fail(
                "DESCARGA_ARCHIVO_INVALIDO",
                f"El SHA256 del archivo descargado ({sha_hex}) no coincide con el esperado ({sha256_esperado}). Posible binario corrupto o interceptado.",
                {
                    "sha256_calculado": sha_hex,
                    "sha256_esperado": sha256_esperado,
                    "bytes_descargados": nbytes,
                },
            )
            try:
                os.remove(nuevo_exe)
            except Exception:
                pass
            return False

    if firma_esperada:
        try:
            import ecdsa
            import base64
            vk = ecdsa.VerifyingKey.from_pem(PUBLIC_KEY_PEM)
            firma_bytes = base64.b64decode(firma_esperada)
            
            with open(nuevo_exe, "rb") as f:
                file_data = f.read()
                
            # Verifica que la firma coincida con los bytes del archivo descargado
            vk.verify(firma_bytes, file_data, hashfunc=hashlib.sha256)
            
        except Exception as e:
            _fail(
                "FIRMA_DIGITAL_INVALIDA",
                f"Fallo la validación de la firma digital ({type(e).__name__}). El binario fue rechazado por seguridad.",
                {
                    "tipo_excepcion": type(e).__name__,
                    "bytes_descargados": nbytes,
                },
            )
            try:
                os.remove(nuevo_exe)
            except Exception:
                pass
            return False

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
    espera_ping = 3
    bat_lines = [
        "@echo off",
        f"ping 127.0.0.1 -n {espera_ping + 1} > nul",
        f'sc stop "{SERVICIO_NOMBRE}" >nul 2>&1',
        "set /a INTENTOS=0",
        ":loop",
        "set /a INTENTOS+=1",
        f'taskkill /IM "{nombre_exe}" /F >nul 2>&1',
        "timeout /t 2 /nobreak > nul",
        f'copy /Y "{nuevo_exe}" "{exe_actual}" >nul 2>&1',
        "if not errorlevel 1 goto :copy_ok",
        "if %INTENTOS% LSS 15 goto :loop",
        # Falló tras los intentos, reanuda el servicio viejo
        f'sc start "{SERVICIO_NOMBRE}" >nul 2>&1',
        "goto :cleanup",
        ":copy_ok",
        f'type nul > "{flag_path}"',
        f'sc start "{SERVICIO_NOMBRE}" >nul 2>&1',
        ":cleanup",
        f'del /F /Q "{nuevo_exe}" >nul 2>&1',
        '(goto) 2>nul & del "%~f0"',
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
            f".bat lanzado (desacoplado): espera {espera_ping}s, sc stop, bucle de reintentos inteligente para copiar, flag si copy OK, sc start, auto-borrado.",
            {
                "bat_path_temp": bat_path,
                "espera_inicial_seg": espera_ping,
                "espera_tras_stop_seg": 5,
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
