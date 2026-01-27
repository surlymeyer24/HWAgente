import psutil
import platform
import subprocess
import os
import requests
import ctypes
import ctypes.wintypes

def obtener_id_anydesk():
    """
    Obtiene el ID de AnyDesk usando el comando oficial del ejecutable.
    Método más confiable y rápido.
    """
    # Rutas comunes de instalación de AnyDesk
    posibles_rutas_exe = [
        r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe",
        r"C:\Program Files\AnyDesk\AnyDesk.exe",
        os.path.join(os.environ.get('ProgramData', ''), 'AnyDesk', 'AnyDesk.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'AnyDesk', 'AnyDesk.exe')
    ]
    
    # Buscar el ejecutable
    anydesk_exe = None
    for ruta in posibles_rutas_exe:
        if os.path.exists(ruta):
            anydesk_exe = ruta
            break
    
    if not anydesk_exe:
        return "No instalado"
    
    try:
        # Ejecutar comando para obtener el ID
        resultado = subprocess.run(
            [anydesk_exe, '--get-id'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if resultado.returncode == 0:
            anydesk_id = resultado.stdout.strip()
            if anydesk_id and anydesk_id.isdigit():
                return anydesk_id
        
        return "Error al obtener ID"
        
    except subprocess.TimeoutExpired:
        return "Timeout"
    except Exception as e:
        return f"Error: {str(e)}"
    
    
def obtener_ip_publica():
    """
    Intenta obtener la IP pública usando múltiples servicios.
    Retorna la IP como string o un mensaje de error si falla todo.
    """
    # Lista de proveedores confiables (Redundancia)
    servidores_ip = [
        'https://api.ipify.org',
        'https://checkip.amazonaws.com',
        'https://ifconfig.me/ip'
    ]
    
    for url in servidores_ip:
        try:
            # timeout=5 es vital: si el sitio no responde en 5 seg, pasa al siguiente
            respuesta = requests.get(url, timeout=5)
            if respuesta.status_code == 200:
                # .strip() limpia espacios o saltos de línea invisibles
                return respuesta.text.strip()
        except Exception:
            # Si hay error (sin internet o sitio caído), sigue con el próximo
            continue
            
    return "IP no disponible (Sin conexión)"

def obtener_aplicaciones_activas():
    """
    Obtiene aplicaciones y su consumo de recursos.
    Agrupa por nombre de aplicación sumando todos sus procesos.
    Retorna las top 15 por uso de RAM.
    """
    # Lectura previa para que cpu_percent funcione correctamente
    for proc in psutil.process_iter():
        try:
            proc.cpu_percent()
        except:
            pass
    
    # Esperar un momento para tener datos
    import time
    time.sleep(0.5)
    
    apps_agrupadas = {}  # Diccionario para agrupar por nombre
    
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
        try:
            nombre = proc.info['name']
            
            # Filtrar procesos de sistema obvios
            if nombre.lower() in ['svchost.exe', 'conhost.exe', 'idle', 'system', 
                                   'registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
                                   'services.exe', 'lsass.exe', 'dwm.exe']:
                continue
            
            # Convertir bytes a MB
            ram_mb = proc.info['memory_info'].rss / (1024 * 1024)
            cpu_pct = proc.info['cpu_percent']
            
            # Agrupar por nombre
            if nombre not in apps_agrupadas:
                apps_agrupadas[nombre] = {
                    'nombre': nombre,
                    'cpu_porcentaje': 0,
                    'ram_mb': 0,
                    'procesos': 0
                }
            
            # Sumar recursos
            apps_agrupadas[nombre]['cpu_porcentaje'] += cpu_pct
            apps_agrupadas[nombre]['ram_mb'] += ram_mb
            apps_agrupadas[nombre]['procesos'] += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Convertir a lista y redondear
    apps_con_recursos = []
    for app in apps_agrupadas.values():
        apps_con_recursos.append({
            'nombre': app['nombre'],
            'cpu_porcentaje': round(app['cpu_porcentaje'], 1),
            'ram_mb': round(app['ram_mb'], 1),
            'procesos': app['procesos']
        })
    
    # Ordenar por RAM (las que más consumen primero)
    apps_con_recursos.sort(key=lambda x: x['ram_mb'], reverse=True)
    
    # Retornar top 15
    return apps_con_recursos[:15]

def obtener_usuarios():
    try:
        usuario_actual = os.getlogin()
        
        usuarios_activos = [u.name for u in psutil.users()]
        
        return {
            "usuario_actual": usuario_actual,
            "usuarios_activos": list(set(usuarios_activos))
        }
    except Exception:
        return {"usuario_actual": "Desconocido", "usuarios_activos": [] }

def obtener_id_inventario():
    try:
        cmd = 'wmic csproduct get uuid'
        resultado = subprocess.check_output(cmd, shell=True).decode().split('\n')
        uuid = resultado[1].strip()
        return uuid
    except Exception as e:
        print(f"Error obteniendo UUID: {e}")
        return platform.node()

def obtener_datos_pc():
    ip = obtener_ip_publica()
    anydesk_id = obtener_id_anydesk()
    
    datos = {
        "uuid": obtener_id_inventario(),
        "hostname": platform.node(),
        "sistema_operativo": f"{platform.system()} {platform.release()}",
        "arquitectura": platform.machine(),
        "ip_publica": ip,
        "anydesk_id": anydesk_id,
        "aplicaciones_activas": obtener_aplicaciones_activas(),
        "procesador": platform.processor(),
        "nucleos_fisicos": psutil.cpu_count(logical=False),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "discos": [],
        "cpu_uso_porcentaje": psutil.cpu_percent(interval=1),
        "ram_uso_porcentaje": psutil.virtual_memory().percent,
    }
    
    datos["usuarios"] = obtener_usuarios()
    
    for partition in psutil.disk_partitions():
        if 'fixed' not in partition.opts:
            continue
            
        try:
            uso = psutil.disk_usage(partition.mountpoint)
            datos["discos"].append({
                "dispositivo": partition.device,
                "punto_montaje": partition.mountpoint,
                "total_gb": round(uso.total / (1024 ** 3), 2)
            })
        except PermissionError:
            continue
        
    return datos

if __name__ == "__main__":
    print("----- Escaneo de Datos de la PC -----")
    info = obtener_datos_pc()
    
    for clave, valor in info.items():
        if clave != "discos":
            print(f"{clave.replace('_', ' ').capitalize()}: {valor}")
    
    print("Discos detectados: {len(info['discos'])}")
    for d in info['discos']:
        print(f"  - Dispositivo: {d['dispositivo']}Total: {d['total_gb']} GB")