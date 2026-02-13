import psutil
import platform
import subprocess
import os
import requests
import win32evtlog
import win32evtlogutil
import win32con
import gc

try:
    from src.core.perifericos import obtener_todos_los_perifericos
    PERIFERICOS_DISPONIBLE = True
except ImportError:
    PERIFERICOS_DISPONIBLE = False

# ==================== CACHÉ GLOBAL ====================
_CACHE_ESTATICO = {}

def inicializar_cache():
    """Cachea datos que nunca cambian (se llama 1 vez al inicio)"""
    global _CACHE_ESTATICO
    if not _CACHE_ESTATICO:
        _CACHE_ESTATICO = {
            'hostname': platform.node(),
            'sistema_operativo': f"{platform.system()} {platform.release()}",
            'arquitectura': platform.machine(),
            'procesador': platform.processor(),
            'nucleos_fisicos': psutil.cpu_count(logical=False),
            'ram_total_gb': round(psutil.virtual_memory().total / (1024 ** 3), 2),
            'modelos_discos': obtener_modelos_discos_fisicos()  # Cacheamos modelos
        }
    return _CACHE_ESTATICO


# ==================== 1. SALUD DEL DISCO ====================
def obtener_modelos_discos_fisicos():
    """Obtiene los modelos de los discos físicos usando WMIC (se ejecuta 1 vez)"""
    modelos = {}
    try:
        resultado = subprocess.run(
            ['wmic', 'diskdrive', 'get', 'Index,Model'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        lineas = resultado.stdout.strip().split('\n')[1:]
        
        for linea in lineas:
            linea = linea.strip()
            if linea:
                partes = linea.split(None, 1)
                if len(partes) == 2:
                    indice = partes[0].strip()
                    modelo = partes[1].strip()
                    modelos[indice] = modelo
                    
    except Exception as e:
        print(f"⚠️ No se pudo obtener modelos de discos: {e}")
    
    return modelos


def obtener_disco_de_particion(letra_unidad):
    """Obtiene el número de disco físico de una letra de unidad"""
    try:
        letra = letra_unidad.replace(':', '').replace('\\', '').strip()
        
        resultado = subprocess.run(
            ['wmic', 'logicaldisk', 'where', f'DeviceID="{letra}:"', 'assoc', '/assocclass:Win32_LogicalDiskToPartition'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        for linea in resultado.stdout.split('\n'):
            if 'Disk #' in linea:
                try:
                    disk_num = linea.split('Disk #')[1].split(',')[0].strip()
                    return disk_num
                except:
                    pass
        
        return "0"  # Fallback
            
    except Exception as e:
        print(f"⚠️ Error obteniendo disco de partición {letra_unidad}: {e}")
    
    return None


def obtener_salud_discos():
    """Obtiene información de espacio en disco usando caché de modelos"""
    cache = inicializar_cache()
    modelos_discos = cache['modelos_discos']
    
    discos = []
    for partition in psutil.disk_partitions():
        if 'fixed' not in partition.opts:
            continue
            
        try:
            uso = psutil.disk_usage(partition.mountpoint)
            
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
    """Obtiene información de red optimizada"""
    adaptadores = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    
    for interfaz, datos in stats.items():
        if datos.isup:
            ips = []
            if interfaz in addrs:
                for addr in addrs[interfaz]:
                    if addr.family == 2:  # IPv4
                        ips.append(addr.address)
            
            adaptadores.append({
                "nombre": interfaz,
                "activo": datos.isup,
                "velocidad_mbps": datos.speed if datos.speed > 0 else "Desconocida",
                "ips": ips
            })
    
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
def obtener_errores_sistema(limite=5):  # REDUCIDO DE 10 A 5
    """Obtiene errores críticos recientes (optimizado)"""
    errores = []
    
    try:
        hand = win32evtlog.OpenEventLog(None, "System")
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        
        eventos = win32evtlog.ReadEventLog(hand, flags, 0)
        
        for evento in eventos[:50]:  # REDUCIDO DE 100 A 50
            if evento.EventType == win32con.EVENTLOG_ERROR_TYPE:  # SOLO ERRORES, NO WARNINGS
                try:
                    mensaje = win32evtlogutil.SafeFormatMessage(evento, "System")
                    if mensaje:
                        mensaje = mensaje[:150] + "..." if len(mensaje) > 150 else mensaje
                    else:
                        mensaje = "Sin descripción"
                except:
                    mensaje = "Error al leer mensaje"
                
                errores.append({
                    "fecha": evento.TimeGenerated.Format(),
                    "tipo": "Error",
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
    """Verifica servicios críticos de seguridad"""
    servicios_criticos = {
        "WinDefend": "Windows Defender",
        "wuauserv": "Windows Update",
        "mpssvc": "Firewall de Windows",
        "wscsvc": "Centro de seguridad"
    }
    
    estados = []
    
    for servicio, nombre in servicios_criticos.items():
        try:
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
    """Obtiene el ID de AnyDesk (cacheado en memoria)"""
    posibles_rutas_exe = [
        r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe",
        r"C:\Program Files\AnyDesk\AnyDesk.exe",
        os.path.join(os.environ.get('ProgramData', ''), 'AnyDesk', 'AnyDesk.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'AnyDesk', 'AnyDesk.exe')
    ]
    
    anydesk_exe = None
    for ruta in posibles_rutas_exe:
        if os.path.exists(ruta):
            anydesk_exe = ruta
            break
    
    if not anydesk_exe:
        return "No instalado"
    
    try:
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
    """Obtiene IP pública con timeout corto"""
    servidores_ip = [
        'https://api.ipify.org',
        'https://checkip.amazonaws.com'
    ]
    
    for url in servidores_ip:
        try:
            respuesta = requests.get(url, timeout=3)  # REDUCIDO DE 5 A 3
            if respuesta.status_code == 200:
                return respuesta.text.strip()
        except Exception:
            continue
            
    return "IP no disponible"


def obtener_aplicaciones_activas():
    """Obtiene top 10 apps (REDUCIDO DE 15)"""
    import json
    
    powershell_script = """
    $apps = @{}
    
    Get-Counter '\\Proceso(*)\\Espacio de trabajo - Privado' -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty CounterSamples | 
        ForEach-Object {
            $name = $_.InstanceName
            if ($name -notin @('idle','_total','system')) {
                if (-not $apps.ContainsKey($name)) {
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
    
    $result = $apps.GetEnumerator() | ForEach-Object {
        [PSCustomObject]@{
            Name = $_.Key + '.exe'
            Description = $_.Value.Description
            RAM_MB = [math]::Round($_.Value.RAM / 1MB, 1)
            Processes = $_.Value.Count
        }
    } | Where-Object { $_.RAM_MB -gt 5 } | Sort-Object RAM_MB -Descending | Select-Object -First 10
    
    $result | ConvertTo-Json
    """
    
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', powershell_script],
            capture_output=True,
            text=True,
            timeout=10,  # REDUCIDO DE 15 A 10
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            apps_formateadas = []
            for app in datos:
                apps_formateadas.append({
                    'nombre': app['Name'],
                    'descripcion': app.get('Description', app['Name']),
                    'cpu_porcentaje': 0,
                    'ram_mb': app['RAM_MB'],
                    'procesos': app['Processes']
                })
            
            # CPU rápido con psutil
            cpu_data = {}
            for proc in psutil.process_iter(['name']):
                try:
                    proc.cpu_percent()
                except:
                    pass
            
            import time
            time.sleep(0.2)  # REDUCIDO DE 0.3 A 0.2
            
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                try:
                    nombre = proc.info['name']
                    if nombre not in cpu_data:
                        cpu_data[nombre] = 0
                    cpu_data[nombre] += proc.info['cpu_percent']
                except:
                    pass
            
            for app in apps_formateadas:
                nombre_sin_exe = app['nombre'].replace('.exe', '.exe')
                if nombre_sin_exe in cpu_data:
                    app['cpu_porcentaje'] = round(cpu_data[nombre_sin_exe], 1)
            
            return apps_formateadas
        
    except Exception as e:
        print(f"⚠️ Error con Performance Counters: {e}")
    
    return obtener_aplicaciones_activas_fallback()


def obtener_aplicaciones_activas_fallback():
    """Fallback usando psutil"""
    apps_agrupadas = {}
    
    for proc in psutil.process_iter(['name']):
        try:
            proc.cpu_percent()
        except:
            pass
    
    import time
    time.sleep(0.3)
    
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
    return apps_con_recursos[:10]  # REDUCIDO DE 15 A 10


def obtener_usuarios():
    try:
        usuario_actual = os.getlogin()
        usuarios_activos = [u.name for u in psutil.users()]
        
        return {
            "usuario_actual": usuario_actual,
            "usuarios_activos": list(set(usuarios_activos))
        }
    except Exception:
        return {"usuario_actual": "Desconocido", "usuarios_activos": []}


def obtener_id_inventario():
    try:
        cmd = 'wmic csproduct get uuid'
        resultado = subprocess.check_output(cmd, shell=True).decode().split('\n')
        uuid = resultado[1].strip()
        return uuid
    except Exception as e:
        print(f"Error obteniendo UUID: {e}")
        return platform.node()


def obtener_datos_pc(incluir_pesados=True):
    """
    Función principal optimizada.
    
    Args:
        incluir_pesados: Si False, omite aplicaciones activas y errores (para sincronización rápida)
    """
    # Inicializar caché si es primera vez
    cache = inicializar_cache()
    
    # Datos base (SIEMPRE)
    datos = {
        "uuid": obtener_id_inventario(),
        "hostname": cache['hostname'],
        "sistema_operativo": cache['sistema_operativo'],
        "arquitectura": cache['arquitectura'],
        "procesador": cache['procesador'],
        "nucleos_fisicos": cache['nucleos_fisicos'],
        "ram_total_gb": cache['ram_total_gb'],
        
        # Datos dinámicos ligeros
        "cpu_uso_porcentaje": psutil.cpu_percent(interval=0.5),  # REDUCIDO DE 1 A 0.5
        "ram_uso_porcentaje": psutil.virtual_memory().percent,
        "usuarios": obtener_usuarios(),
        "discos": obtener_salud_discos(),
        "red": obtener_info_red(),
        "servicios_criticos": obtener_estado_servicios()
    }
    
    # Datos pesados (CONDICIONAL)
    if incluir_pesados:
        datos["ip_publica"] = obtener_ip_publica()
        datos["anydesk_id"] = obtener_id_anydesk()
        datos["aplicaciones_activas"] = obtener_aplicaciones_activas()
        datos["errores_recientes"] = obtener_errores_sistema(limite=5)

        if PERIFERICOS_DISPONIBLE:
            datos["perifericos"] = obtener_todos_los_perifericos()

    # Liberar memoria
    gc.collect()
    
    return datos