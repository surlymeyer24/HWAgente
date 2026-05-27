import time
import sys
import subprocess
import os
import threading

# --- 1. PREVENCIÓN DE ERRORES EN MODO INVISIBLE ---
from config.config import DEBUG_MODE

if getattr(sys, 'frozen', False) and not DEBUG_MODE:
    sys.stdin = None
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# --- 2. DETECCIÓN DE MÓDULOS DE SERVICIO ---
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    RUNNING_AS_SERVICE = True
except ImportError:
    RUNNING_AS_SERVICE = False

# --- 3. FUNCIONES DE UTILIDAD ---
def log_arranque(mensaje):
    """Escribe al archivo de debug sin depender de Firebase (disponible desde el primer instante)."""
    try:
        path = "C:\\agente_debug.txt"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [ARRANQUE] {mensaje}\n")
    except:
        pass

def verificar_permisos_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except: 
        return False

def solicitar_permisos_admin():
    import ctypes
    if sys.argv[-1] != 'asadmin':
        script = sys.executable
        params = f'"{sys.argv[0]}" asadmin'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
        return True
    return False

def servicio_esta_instalado():
    try:
        res = subprocess.run('sc query "AgenteMonitoreo"',
                             shell=True, capture_output=True, text=True,
                             encoding='utf-8', errors='replace',
                             creationflags=subprocess.CREATE_NO_WINDOW)
        return "AgenteMonitoreo" in res.stdout
    except: 
        return False

def instalar_servicio_automaticamente():
    exe_path = sys.executable
    log_arranque(f"INSTALACION_INICIADA — exe: {exe_path}")

    r_stop = subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW)
    log_arranque(f"SC_STOP — {r_stop.stdout.strip() or r_stop.stderr.strip() or 'sin salida'}")
    time.sleep(1)

    r_del = subprocess.run('sc delete "AgenteMonitoreo"', shell=True, capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           creationflags=subprocess.CREATE_NO_WINDOW)
    log_arranque(f"SC_DELETE — {r_del.stdout.strip() or r_del.stderr.strip() or 'sin salida'}")

    cmd = f'sc create "AgenteMonitoreo" binPath= "{exe_path}" start= auto DisplayName= "AgenteBacar"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                         encoding='utf-8', errors='replace',
                         creationflags=subprocess.CREATE_NO_WINDOW)
    log_arranque(f"SC_CREATE — returncode: {res.returncode} | stdout: {res.stdout.strip()} | stderr: {res.stderr.strip()}")

    if "SUCCESS" in res.stdout or "CORRECTO" in res.stdout:
        r_start = subprocess.run('sc start "AgenteMonitoreo"', shell=True, capture_output=True,
                                 text=True, encoding='utf-8', errors='replace',
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        log_arranque(f"SC_START — returncode: {r_start.returncode} | stdout: {r_start.stdout.strip()} | stderr: {r_start.stderr.strip()}")
        log_arranque("INSTALACION_EXITOSA")
        return True

    log_arranque(f"INSTALACION_FALLIDA — SC_CREATE no devolvió SUCCESS/CORRECTO")
    return False

# --- 4. CLASE DEL SERVICIO ---
if RUNNING_AS_SERVICE:
    class AgenteMonitoreoService(win32serviceutil.ServiceFramework):
        _svc_name_ = "AgenteMonitoreo"
        _svc_display_name_ = "AgenteBacar"
        _svc_description_ = "Sincronización de hardware con Firebase."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.running = True

        def SvcStop(self):
            self.running = False
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            # NOTIFICAR INICIO A WINDOWS INMEDIATAMENTE PARA EVITAR ERROR 1053
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            log_arranque(f"SVCRUN_INICIO — PID: {os.getpid()}")

            try:
                # Importaciones tardías para no demorar el arranque
                from src.database.firebase_client import (
                    enviar_datos_pc,
                    escuchar_comandos_remotos,
                    log_centralizado,
                    log_debug,
                    registrar_log_actualizacion,
                    reportar_post_actualizacion_agente_si_aplica,
                    resolver_machine_id,
                    set_machine_uuid,
                    VERSION_AGENTE,
                )
                from src.core.scanner import obtener_datos_pc
                log_arranque("SVCRUN_FIREBASE_OK — módulos cargados")

                # AVISAR QUE YA ESTÁ CORRIENDO
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                log_debug("Servicio en estado RUNNING.")
                log_arranque("SVCRUN_RUNNING — servicio activo")

                datos = obtener_datos_pc()
                uuid_final = resolver_machine_id(datos.get("uuid", ""), datos.get("hostname", ""))
                datos["uuid"] = uuid_final
                set_machine_uuid(uuid_final)
                log_centralizado("Info", "Servicio", "AgenteBacar iniciado")
                reportar_post_actualizacion_agente_si_aplica(uuid_final)
                registrar_log_actualizacion(
                    "ARRANQUE_SERVICIO",
                    "AgenteBacar iniciado correctamente",
                    uuid=datos.get("uuid"),
                    hostname=datos.get("hostname"),
                    extra={"version": VERSION_AGENTE or "?", "pid": os.getpid()},
                )
                log_arranque(f"SVCRUN_SYNC_INICIAL — uuid: {uuid_final}")
                enviar_datos_pc(datos)
                # Evento para despertar el bucle cuando Firebase envíe ACTUALIZAR_AGENTE
                try:
                    import win32event as wevt
                    h_update = wevt.CreateEvent(None, 0, 0, None)
                except Exception:
                    h_update = None
                escuchar_comandos_remotos(datos['uuid'], evento_actualizar=h_update)

                while self.running:
                    if h_update is not None:
                        rc = win32event.WaitForMultipleObjects(
                            [self.hWaitStop, h_update], False, 300000
                        )
                    else:
                        rc = win32event.WaitForSingleObject(self.hWaitStop, 300000)
                    if rc == win32event.WAIT_OBJECT_0:
                        break
                    # PyInstaller: frozen y/o _MEIPASS; sin esto el .exe podría no disparar la descarga
                    _exe_empaquetado = getattr(sys, "frozen", False) or getattr(
                        sys, "_MEIPASS", None
                    ) is not None
                    if h_update is not None and rc == win32event.WAIT_OBJECT_0 + 1 and not _exe_empaquetado:
                        try:
                            from src.database.firebase_client import (
                                _info_actualizacion_pendiente,
                                log_debug,
                            )
                            log_debug(
                                "ACTUALIZAR_AGENTE: evento Win32 recibido pero el proceso no es ejecutable "
                                "empaquetado (sin frozen/_MEIPASS); se descarta URL pendiente."
                            )
                            _info_actualizacion_pendiente()
                        except Exception:
                            pass
                        continue
                    if (
                        h_update is not None
                        and rc == win32event.WAIT_OBJECT_0 + 1
                        and _exe_empaquetado
                    ):
                        try:
                            from src.database.firebase_client import (
                                _info_actualizacion_pendiente,
                                log_debug,
                            )
                            from src.core.auto_update import download_and_apply_update
                            info_actualizacion = _info_actualizacion_pendiente()
                            url = info_actualizacion.get("url")
                            sha256 = info_actualizacion.get("sha256")
                            firma = info_actualizacion.get("firma")

                            if not url:
                                try:
                                    from src.database.firebase_client import log_debug
                                    log_debug("ACTUALIZAR_AGENTE: evento recibido pero URL pendiente vacía (condición de carrera).")
                                except Exception:
                                    pass
                                continue
                            if getattr(self, "_hilo_descarga", None) and self._hilo_descarga.is_alive():
                                try:
                                    log_debug("ACTUALIZAR_AGENTE: descarga ya en curso, se descarta solicitud duplicada.")
                                except Exception:
                                    pass
                                continue
                            _uuid = datos.get("uuid")
                            _hostname = datos.get("hostname")
                            _url, _sha256, _firma = url, sha256, firma

                            def _hilo_descarga_fn():
                                try:
                                    from src.database.firebase_client import log_debug
                                    exito = download_and_apply_update(
                                        _url,
                                        uuid=_uuid,
                                        hostname=_hostname,
                                        sha256_esperado=_sha256,
                                        firma_esperada=_firma,
                                    )
                                    if exito:
                                        log_debug("Actualizacion programada; reinicio en breve.")
                                        self.running = False
                                        win32event.SetEvent(self.hWaitStop)
                                except Exception as e:
                                    try:
                                        from src.database.firebase_client import (
                                            fallo_actualizacion_agente_remota,
                                            log_debug,
                                        )
                                        log_debug(f"Error actualizando agente: {e}")
                                        fallo_actualizacion_agente_remota(
                                            _uuid,
                                            _hostname,
                                            "EXCEPCION_HILO_ACTUALIZACION",
                                            str(e),
                                            {"tipo_excepcion": type(e).__name__},
                                        )
                                    except Exception:
                                        pass

                            self._hilo_descarga = threading.Thread(
                                target=_hilo_descarga_fn, daemon=True, name="AgentUpdate"
                            )
                            self._hilo_descarga.start()
                        except Exception as e:
                            try:
                                from src.database.firebase_client import (
                                    fallo_actualizacion_agente_remota,
                                    log_debug,
                                )
                                log_debug(f"Error actualizando agente: {e}")
                                fallo_actualizacion_agente_remota(
                                    datos.get("uuid"),
                                    datos.get("hostname"),
                                    "EXCEPCION_HILO_ACTUALIZACION",
                                    str(e),
                                    {"tipo_excepcion": type(e).__name__},
                                )
                            except Exception:
                                pass
                        continue
                    datos_ciclo = obtener_datos_pc()
                    datos_ciclo["uuid"] = uuid_final
                    enviar_datos_pc(datos_ciclo)
                    
            except Exception as e:
                log_arranque(f"SVCRUN_ERROR — {type(e).__name__}: {e}")
                try:
                    from src.database.firebase_client import log_centralizado, log_debug
                    log_debug(f"Error general en SvcDoRun: {e}")
                    log_centralizado("Error", "Servicio", f"Error general en SvcDoRun: {e}", e)
                except Exception:
                    pass

# --- 5. PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    # Caso A: Comandos de instalación manual (sc install, remove, etc)
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['install', 'update', 'remove', 'start', 'stop']:
        if RUNNING_AS_SERVICE:
            win32serviceutil.HandleCommandLine(AgenteMonitoreoService)
        sys.exit(0)

    # Caso B: Ejecución como servicio de Windows (SCM)
    # Solo entra aquí si Windows SCM lo llama
    if RUNNING_AS_SERVICE and len(sys.argv) == 1:
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(AgenteMonitoreoService)
            servicemanager.StartServiceCtrlDispatcher()
            sys.exit(0)
        except:
            pass  # Si falla, continúa al Caso C

    if "--dev" in sys.argv:
        emulator = os.getenv("FIRESTORE_EMULATOR_HOST")
        log_arranque(f"DEV_MODE — FIRESTORE_EMULATOR_HOST: {emulator or '(no seteado — usará BD real)'}")
        print("FIRESTORE_EMULATOR_HOST:", emulator)
        print("Importando firebase_client...")
        from src.database.firebase_client import (
            enviar_datos_pc, escuchar_comandos_remotos,
            resolver_machine_id, set_machine_uuid
        )
        print("Importando scanner...")
        from src.core.scanner import obtener_datos_pc
        print("Obteniendo datos PC...")
        datos = obtener_datos_pc()
        print("Resolviendo machine ID...")
        uuid_final = resolver_machine_id(datos.get("uuid", ""), datos.get("hostname", ""))
        datos["uuid"] = uuid_final
        set_machine_uuid(uuid_final)
        print("Enviando datos...")
        enviar_datos_pc(datos)
        log_arranque("DEV_MODE — datos enviados OK")
        print("Listo. Cerrá esta ventana o presioná Enter para salir...")
        try:
            input()
        except (RuntimeError, EOFError):
            # exe sin consola (console=False en spec) — mantener proceso activo
            log_arranque("DEV_MODE — sin stdin, esperando señal de cierre (Ctrl+C o cerrar proceso)")
            import signal
            signal.pause() if hasattr(signal, "pause") else time.sleep(3600)
        sys.exit(0)

    # Caso C: Usuario ejecuta el .exe con doble clic
    if not servicio_esta_instalado():
        if not verificar_permisos_admin():
            log_arranque("CASO_C — sin permisos admin, solicitando elevación")
            solicitar_permisos_admin()
        else:
            if instalar_servicio_automaticamente():
                print("Servicio instalado y corriendo.")
                time.sleep(3)
            else:
                log_arranque("CASO_C — instalar_servicio_automaticamente() devolvió False")
    else:
        log_arranque("CASO_C — servicio ya instalado, ejecutando SC_START")
        r = subprocess.run('sc start "AgenteMonitoreo"', shell=True, capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           creationflags=subprocess.CREATE_NO_WINDOW)
        log_arranque(f"SC_START (ya instalado) — returncode: {r.returncode} | {r.stdout.strip() or r.stderr.strip()}")
        sys.exit(0)