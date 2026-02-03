import time
import sys
import subprocess
import os

# --- 1. PREVENCIÓN DE ERRORES EN MODO INVISIBLE ---
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
            self.contador_ciclos = 0  # Para controlar frecuencias

        def SvcStop(self):
            self.running = False
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            
            try:
                from src.database.firebase_client import enviar_datos_pc, escuchar_comandos_remotos, log_debug
                from src.core.scanner import obtener_datos_pc
                
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                log_debug("Servicio en estado RUNNING (optimizado).")
                
                # PRIMERA SINCRONIZACIÓN COMPLETA
                datos = obtener_datos_pc(incluir_pesados=True)
                enviar_datos_pc(datos, forzar_completo=True)
                escuchar_comandos_remotos(datos['uuid'])
                
                # LOOP OPTIMIZADO
                while self.running:
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 300000)  # 5 min
                    if rc == win32event.WAIT_OBJECT_0:
                        break
                    
                    self.contador_ciclos += 1
                    
                    # Determinar si incluir datos pesados
                    # Cada 3 ciclos (15 min) incluye aplicaciones
                    # Cada 6 ciclos (30 min) incluye errores
                    incluir_pesados = (self.contador_ciclos % 3 == 0)
                    
                    datos = obtener_datos_pc(incluir_pesados=incluir_pesados)
                    enviar_datos_pc(datos)
                    
            except Exception as e:
                from src.database.firebase_client import log_debug
                log_debug(f"Error general en SvcDoRun: {e}")

# --- 5. PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    # Caso A: Comandos de instalación manual
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['install', 'update', 'remove', 'start', 'stop']:
        if RUNNING_AS_SERVICE:
            win32serviceutil.HandleCommandLine(AgenteMonitoreoService)
        sys.exit(0)

    # Caso B: Ejecución como servicio de Windows (SCM)
    if RUNNING_AS_SERVICE and len(sys.argv) == 1:
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(AgenteMonitoreoService)
            servicemanager.StartServiceCtrlDispatcher()
            sys.exit(0)
        except:
            pass

    # Caso C: Usuario ejecuta el .exe con doble clic
    if not servicio_esta_instalado():
        if not verificar_permisos_admin():
            solicitar_permisos_admin()
        else:
            if instalar_servicio_automaticamente():
                print("Servicio instalado y corriendo (optimizado).")
                time.sleep(3)
    else:
        subprocess.run('sc start "AgenteMonitoreo"', shell=True, 
                      creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)