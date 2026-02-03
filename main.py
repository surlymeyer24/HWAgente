import time
import sys
import subprocess
import os

# --- 1. PREVENCIÓN DE ERRORES EN MODO INVISIBLE ---
# Se define antes que nada para evitar crasheos por falta de consola 
from config.config import DEBUG_MODE
if getattr(sys, 'frozen', False) and not DEBUG_MODE:
    sys.stdin = None
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

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
                             creationflags=subprocess.CREATE_NO_WINDOW)
        return "AgenteMonitoreo" in res.stdout
    except: 
        return False

def instalar_servicio_automaticamente():
    exe_path = sys.executable
    subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True, 
                   creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1)
    subprocess.run('sc delete "AgenteMonitoreo"', shell=True, capture_output=True, 
                   creationflags=subprocess.CREATE_NO_WINDOW)
    
    cmd = f'sc create "AgenteMonitoreo" binPath= "{exe_path}" start= auto DisplayName= "Agente de Monitoreo IT"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                        creationflags=subprocess.CREATE_NO_WINDOW)
    
    if "SUCCESS" in res.stdout or "CORRECTO" in res.stdout:
        subprocess.run('sc start "AgenteMonitoreo"', shell=True, 
                      creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    return False

# --- 4. CLASE DEL SERVICIO ---
if RUNNING_AS_SERVICE:
    class AgenteMonitoreoService(win32serviceutil.ServiceFramework):
        _svc_name_ = "AgenteMonitoreo"
        _svc_display_name_ = "Agente de Monitoreo IT"
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
            
            try:
                # Importaciones tardías para no demorar el arranque 
                from src.database.firebase_client import enviar_datos_pc, escuchar_comandos_remotos, log_debug
                from src.core.scanner import obtener_datos_pc
                
                # AVISAR QUE YA ESTÁ CORRIENDO
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                log_debug("Servicio en estado RUNNING.")
                
                datos = obtener_datos_pc()
                enviar_datos_pc(datos)
                escuchar_comandos_remotos(datos['uuid'])
                
                while self.running:
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 300000)
                    if rc == win32event.WAIT_OBJECT_0:
                        break
                    enviar_datos_pc(obtener_datos_pc())
                    
            except Exception as e:
                from src.database.firebase_client import log_debug
                log_debug(f"Error general en SvcDoRun: {e}")

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

    # Caso C: Usuario ejecuta el .exe con doble clic
    if not servicio_esta_instalado():
        if not verificar_permisos_admin():
            solicitar_permisos_admin()
        else:
            if instalar_servicio_automaticamente():
                print("Servicio instalado y corriendo.")
                time.sleep(3)
    else:
        # Asegurarse de que el servicio esté iniciado
        subprocess.run('sc start "AgenteMonitoreo"', shell=True, 
                      creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)