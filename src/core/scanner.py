import psutil
import platform
import subprocess
import os
import requests

def obtener_datos_remotos():
    # --- IP PÚBLICA ---
    try:
        # Intentamos con ipify, si falla probamos otro
        ip_publica = requests.get('https://api.ipify.org', timeout=5).text
    except:
        try:
            ip_publica = requests.get('https://ifconfig.me/ip', timeout=5).text
        except:
            ip_publica = "No disponible"

    # --- ANYDESK ID ---
    anydesk_id = "No instalado"
    # Ruta A: Instalación de sistema
    ruta_sistema = r'C:\ProgramData\AnyDesk\system.conf'
    # Ruta B: Instalación de usuario
    ruta_usuario = os.path.expandvars(r'%APPDATA%\AnyDesk\system.conf')
    
    for ruta in [ruta_sistema, ruta_usuario]:
        if os.path.exists(ruta):
            try:
                with open(ruta, 'r', encoding='utf-8') as f:
                    for linea in f:
                        if 'ad.anydesk.id' in linea:
                            anydesk_id = linea.split('=')[1].strip()
                            break
            except:
                continue
    
    return ip_publica, anydesk_id

def obtener_aplicaciones_activas():
    apps = set()
    for proc in psutil.process_iter(['name']):
        try:
            nombre = proc.info['name']
            if nombre.lower().endswith('.exe'):
                if nombre.lower() not in ['svchost.exe', 'conhost.exe', 'idle']:
                    apps.add(nombre)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return sorted(list(apps))[:15] # Retorna las primeras 15 alfabéticamente

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
    ip, anydesk_id = obtener_datos_remotos()
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