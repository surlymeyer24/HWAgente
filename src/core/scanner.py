import psutil
import platform
import subprocess
import os
import requests
import win32evtlog
import win32evtlogutil
import win32con


# ==================== 1. SALUD DEL DISCO ====================
def obtener_modelos_discos_fisicos():
    """
    Obtiene los modelos de los discos físicos usando WMIC.
    Retorna un diccionario {número_disco: modelo}
    """
    modelos = {}
    try:
        resultado = subprocess.run(
            ['wmic', 'diskdrive', 'get', 'Index,Model'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        lineas = resultado.stdout.strip().split('\n')[1:]  # Saltar encabezado
        
        for linea in lineas:
            linea = linea.strip()
            if linea:
                # Formato: "0  HS-SSD-E3000 512G"
                partes = linea.split(None, 1)  # Dividir en máximo 2 partes
                if len(partes) == 2:
                    indice = partes[0].strip()
                    modelo = partes[1].strip()
                    modelos[indice] = modelo
                    
    except Exception as e:
        print(f"⚠️ No se pudo obtener modelos de discos: {e}")
    
    return modelos


def obtener_disco_de_particion(letra_unidad):
    """
    Obtiene el número de disco físico de una letra de unidad (ej: C:)
    Usa asociación desde la unidad lógica al disco físico.
    """
    try:
        # Limpiar la letra (solo queremos C, D, etc.)
        letra = letra_unidad.replace(':', '').replace('\\', '').strip()
        
        # Método 1: Probar con LogicalDisk to Partition
        resultado = subprocess.run(
            ['wmic', 'logicaldisk', 'where', f'DeviceID="{letra}:"', 'assoc', '/assocclass:Win32_LogicalDiskToPartition'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Buscar DiskIndex en la salida
        for linea in resultado.stdout.split('\n'):
            if 'Disk #' in linea:
                # Formato: "Disk #0, Partition #0"
                try:
                    disk_num = linea.split('Disk #')[1].split(',')[0].strip()
                    return disk_num
                except:
                    pass
        
        # Método 2: Si falló, intentar con partition directamente
        resultado2 = subprocess.run(
            ['wmic', 'partition', 'where', f'Name like "%Disk #%Partition #%"', 'get', 'DiskIndex,DeviceID'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Este método es menos preciso pero funciona como fallback
        # Si solo hay un disco, asumimos que es el 0
        if resultado2.returncode == 0:
            return "0"
            
    except Exception as e:
        print(f"⚠️ Error obteniendo disco de partición {letra_unidad}: {e}")
    
    return None


def obtener_salud_discos():
    """
    Obtiene información detallada de espacio en disco con modelo físico.
    """
    # Primero obtener todos los modelos de discos físicos
    modelos_discos = obtener_modelos_discos_fisicos()
    
    discos = []
    for partition in psutil.disk_partitions():
        if 'fixed' not in partition.opts:
            continue
            
        try:
            uso = psutil.disk_usage(partition.mountpoint)
            
            # Obtener modelo del disco físico
            letra = partition.device
            disco_index = obtener_disco_de_particion(letra)
            modelo = modelos_discos.get(disco_index, "Desconocido") if disco_index else "Desconocido"
            
            discos.append({
                "dispositivo": partition.device,
                "punto_montaje": partition.mountpoint,
                "modelo_disco": modelo,
                "total_gb": round(uso.total / (1024 ** 3), 2),
                "usado_gb": round(uso.used / (1024 ** 3), 2),
                "libre_gb": round(uso.free / (1024 ** 3), 2),
                "porcentaje_usado": uso.percent
            })
        except PermissionError:
            continue
    
    return discos

# ==================== 4. RED ====================
def obtener_info_red():
    """
    Obtiene información de red: adaptadores activos y estadísticas.
    """
    adaptadores = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    
    for interfaz, datos in stats.items():
        if datos.isup:  # Solo interfaces activas
            ips = []
            if interfaz in addrs:
                for addr in addrs[interfaz]:
                    if addr.family == 2:  # AF_INET (IPv4)
                        ips.append(addr.address)
            
            adaptadores.append({
                "nombre": interfaz,
                "activo": datos.isup,
                "velocidad_mbps": datos.speed if datos.speed > 0 else "Desconocida",
                "ips": ips
            })
    
    # Estadísticas de tráfico
    net_io = psutil.net_io_counters()
    trafico = {
        "bytes_enviados_mb": round(net_io.bytes_sent / (1024 ** 2), 2),
        "bytes_recibidos_mb": round(net_io.bytes_recv / (1024 ** 2), 2),
        "paquetes_enviados": net_io.packets_sent,
        "paquetes_recibidos": net_io.packets_recv,
        "errores_entrada": net_io.errin,
        "errores_salida": net_io.errout
    }
    
    return {
        "adaptadores": adaptadores,
        "trafico": trafico
    }


# ==================== 5. ERRORES DEL SISTEMA ====================
def obtener_errores_sistema(limite=10):
    """
    Obtiene los últimos errores del Event Viewer de Windows.
    Solo errores críticos y errores de las últimas 24 horas.
    """
    errores = []
    
    try:
        # Abrir el log de sistema
        hand = win32evtlog.OpenEventLog(None, "System")
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        
        eventos = win32evtlog.ReadEventLog(hand, flags, 0)
        
        for evento in eventos[:100]:  # Revisar últimos 100 eventos
            # Solo errores (tipo 1) y críticos (tipo 16)
            if evento.EventType in [win32con.EVENTLOG_ERROR_TYPE, 
                                     win32con.EVENTLOG_WARNING_TYPE]:
                
                try:
                    mensaje = win32evtlogutil.SafeFormatMessage(evento, "System")
                    if mensaje:
                        # Limitar longitud del mensaje
                        mensaje = mensaje[:200] + "..." if len(mensaje) > 200 else mensaje
                    else:
                        mensaje = "Sin descripción"
                except:
                    mensaje = "Error al leer mensaje"
                
                errores.append({
                    "fecha": evento.TimeGenerated.Format(),
                    "tipo": "Error" if evento.EventType == win32con.EVENTLOG_ERROR_TYPE else "Advertencia",
                    "fuente": evento.SourceName,
                    "evento_id": evento.EventID,
                    "mensaje": mensaje
                })
                
                if len(errores) >= limite:
                    break
        
        win32evtlog.CloseEventLog(hand)
        
    except Exception as e:
        errores.append({
            "error": f"No se pudo leer Event Viewer: {str(e)}"
        })
    
    return errores


# ==================== 6. ESTADO DE SERVICIOS CRÍTICOS ====================
def obtener_estado_servicios():
    """
    Verifica el estado de servicios críticos de seguridad.
    """
    servicios_criticos = {
        "WinDefend": "Windows Defender",
        "wuauserv": "Windows Update",
        "mpssvc": "Firewall de Windows",
        "wscsvc": "Centro de seguridad"
    }
    
    estados = []
    
    for servicio, nombre in servicios_criticos.items():
        try:
            # Usar sc query para verificar estado
            resultado = subprocess.run(
                ['sc', 'query', servicio],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
                
            )
            
            estado = "Detenido"
            if "RUNNING" in resultado.stdout:
                estado = "En ejecución"
            elif "STOPPED" in resultado.stdout:
                estado = "Detenido"
            elif "PAUSED" in resultado.stdout:
                estado = "Pausado"
            
            estados.append({
                "servicio": nombre,
                "estado": estado,
                "critico": estado != "En ejecución"
            })
            
        except Exception as e:
            estados.append({
                "servicio": nombre,
                "estado": f"Error: {str(e)}",
                "critico": True
            })
    
    return estados

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
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
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
    Obtiene aplicaciones usando Performance Counters de Windows (exacto como Admin de Tareas)
    Incluye descripción del producto desde metadatos del ejecutable
    """
    import json
    
    # Script de PowerShell con el contador correcto en español
    powershell_script = """
    $apps = @{}
    
    # Obtener memoria privada (exactamente lo que muestra Admin de Tareas)
    Get-Counter '\\Proceso(*)\\Espacio de trabajo - Privado' -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty CounterSamples | 
        ForEach-Object {
            $name = $_.InstanceName
            # Ignorar procesos del sistema
            if ($name -notin @('idle','_total','system')) {
                if (-not $apps.ContainsKey($name)) {
                    # Obtener descripción del producto
                    $description = $name
                    try {
                        $proc = Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
                        if ($proc -and $proc.Path) {
                            $fileInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($proc.Path)
                            if ($fileInfo.FileDescription) {
                                $description = $fileInfo.FileDescription
                            }
                        }
                    } catch {}
                    
                    $apps[$name] = @{
                        Description = $description
                        RAM = 0
                        Count = 0
                    }
                }
                $apps[$name].RAM += $_.CookedValue
                $apps[$name].Count += 1
            }
        }
    
    # Convertir a lista y formatear
    $result = $apps.GetEnumerator() | ForEach-Object {
        [PSCustomObject]@{
            Name = $_.Key + '.exe'
            Description = $_.Value.Description
            RAM_MB = [math]::Round($_.Value.RAM / 1MB, 1)
            Processes = $_.Value.Count
        }
    } | Where-Object { $_.RAM_MB -gt 5 } | Sort-Object RAM_MB -Descending | Select-Object -First 15
    
    $result | ConvertTo-Json
    """
    
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', powershell_script],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            # Si es un solo objeto, convertir a lista
            if isinstance(datos, dict):
                datos = [datos]
            
            # Formatear para Firebase
            apps_formateadas = []
            for app in datos:
                apps_formateadas.append({
                    'nombre': app['Name'],
                    'descripcion': app.get('Description', app['Name']),
                    'cpu_porcentaje': 0,
                    'ram_mb': app['RAM_MB'],
                    'procesos': app['Processes']
                })
            
            # Agregar CPU con psutil (rápido)
            cpu_data = {}
            for proc in psutil.process_iter(['name']):
                try:
                    proc.cpu_percent()
                except:
                    pass
            
            import time
            time.sleep(0.3)
            
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                try:
                    nombre = proc.info['name']
                    if nombre not in cpu_data:
                        cpu_data[nombre] = 0
                    cpu_data[nombre] += proc.info['cpu_percent']
                except:
                    pass
            
            # Combinar CPU con los datos de RAM
            for app in apps_formateadas:
                nombre_sin_exe = app['nombre'].replace('.exe', '.exe')
                if nombre_sin_exe in cpu_data:
                    app['cpu_porcentaje'] = round(cpu_data[nombre_sin_exe], 1)
            
            return apps_formateadas
        
    except Exception as e:
        print(f"⚠️ Error con Performance Counters: {e}")
    
    # Fallback a psutil
    return obtener_aplicaciones_activas_fallback()
    
    # Fallback: usar el método anterior si PowerShell falla
    return obtener_aplicaciones_activas_fallback()


def obtener_aplicaciones_activas_fallback():
    """
    Método de respaldo usando psutil si PowerShell falla.
    """
    apps_agrupadas = {}
    
    for proc in psutil.process_iter(['name']):
        try:
            proc.cpu_percent()
        except:
            pass
    
    import time
    time.sleep(0.5)
    
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
        try:
            nombre = proc.info['name']
            
            if nombre.lower() in ['svchost.exe', 'conhost.exe', 'idle', 'system', 
                                   'registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
                                   'services.exe', 'lsass.exe', 'dwm.exe']:
                continue
            
            ram_mb = proc.info['memory_info'].rss / (1024 * 1024)
            cpu_pct = proc.info['cpu_percent']
            
            if nombre not in apps_agrupadas:
                apps_agrupadas[nombre] = {
                    'nombre': nombre,
                    'cpu_porcentaje': 0,
                    'ram_mb': 0,
                    'procesos': 0
                }
            
            apps_agrupadas[nombre]['cpu_porcentaje'] += cpu_pct
            apps_agrupadas[nombre]['ram_mb'] += ram_mb
            apps_agrupadas[nombre]['procesos'] += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    apps_con_recursos = []
    for app in apps_agrupadas.values():
        apps_con_recursos.append({
            'nombre': app['nombre'],
            'cpu_porcentaje': round(app['cpu_porcentaje'], 1),
            'ram_mb': round(app['ram_mb'], 1),
            'procesos': app['procesos']
        })
    
    apps_con_recursos.sort(key=lambda x: x['ram_mb'], reverse=True)
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
    """
    Función principal con todos los datos extendidos.
    """
    from src.core.scanner import (
        obtener_ip_publica, 
        obtener_id_anydesk, 
        obtener_id_inventario,
        obtener_aplicaciones_activas,
        obtener_usuarios
    )
    
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
        "cpu_uso_porcentaje": psutil.cpu_percent(interval=1),
        "ram_uso_porcentaje": psutil.virtual_memory().percent,
        "usuarios": obtener_usuarios(),
        
        # NUEVOS DATOS
        "discos": obtener_salud_discos(),
        "red": obtener_info_red(),
        "errores_recientes": obtener_errores_sistema(limite=10),
        "servicios_criticos": obtener_estado_servicios()
    }
    
    return datos