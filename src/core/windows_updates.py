import subprocess
import json
import time


def _ejecutar_powershell(script, timeout=30):
    """Ejecuta un script PowerShell y devuelve el JSON parseado"""
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', script],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            if isinstance(datos, dict):
                datos = [datos]
            return datos
    except json.JSONDecodeError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return []


# ==================== UPDATES PENDIENTES ====================
def obtener_updates_pendientes():
    """
    Lista updates pendientes de instalar.
    Usa el COM object Microsoft.Update.Session (built-in en Windows).
    """
    ps_script = """
    try {
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $result = $searcher.Search("IsInstalled=0 AND IsHidden=0")

        $updates = @()
        foreach ($update in $result.Updates) {
            $severidad = switch ($update.MsrcSeverity) {
                "Critical"  { "Critico" }
                "Important" { "Importante" }
                "Moderate"  { "Moderado" }
                "Low"       { "Bajo" }
                default     { "Sin clasificar" }
            }

            $categorias = @()
            foreach ($cat in $update.Categories) {
                $categorias += $cat.Name
            }

            $updates += [PSCustomObject]@{
                Titulo     = $update.Title
                KB         = if ($update.KBArticleIDs.Count -gt 0) { "KB" + $update.KBArticleIDs.Item(0) } else { "N/A" }
                Severidad  = $severidad
                Tamano_MB  = [math]::Round($update.MaxDownloadSize / 1MB, 1)
                Categorias = ($categorias -join ", ")
                Fecha      = if ($update.LastDeploymentChangeTime) { $update.LastDeploymentChangeTime.ToString("yyyy-MM-dd") } else { "N/A" }
                EsCritico  = ($update.MsrcSeverity -eq "Critical")
            }
        }

        if ($updates.Count -eq 0) {
            ConvertTo-Json @(@{ Titulo = "NINGUNO"; KB = "N/A"; Severidad = "N/A"; Tamano_MB = 0; Categorias = ""; Fecha = "N/A"; EsCritico = $false })
        } else {
            $updates | ConvertTo-Json
        }
    } catch {
        ConvertTo-Json @(@{ error = $_.Exception.Message })
    }
    """
    datos = _ejecutar_powershell(ps_script, timeout=60)

    if not datos or (len(datos) == 1 and datos[0].get('Titulo') == 'NINGUNO'):
        return []

    if datos and datos[0].get('error'):
        return [{'error': datos[0]['error']}]

    updates = []
    for u in datos:
        updates.append({
            'titulo': u.get('Titulo', ''),
            'kb': u.get('KB', 'N/A'),
            'severidad': u.get('Severidad', 'Sin clasificar'),
            'tamano_mb': u.get('Tamano_MB', 0),
            'categorias': u.get('Categorias', ''),
            'fecha_publicacion': u.get('Fecha', 'N/A'),
            'es_critico': u.get('EsCritico', False)
        })

    updates.sort(key=lambda x: (
        0 if x['severidad'] == 'Critico' else
        1 if x['severidad'] == 'Importante' else
        2 if x['severidad'] == 'Moderado' else 3
    ))

    return updates


# ==================== HISTORIAL DE UPDATES ====================
def obtener_historial_updates(limite=20):
    """Obtiene las ultimas N updates instaladas"""
    ps_script = f"""
    try {{
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $total = $searcher.GetTotalHistoryCount()
        $historial = $searcher.QueryHistory(0, [Math]::Min($total, {limite}))

        $resultados = @()
        foreach ($entry in $historial) {{
            if (-not $entry.Title) {{ continue }}

            $estado = switch ($entry.ResultCode) {{
                2 {{ "Instalado" }}
                3 {{ "Instalado con errores" }}
                4 {{ "Fallido" }}
                5 {{ "Abortado" }}
                default {{ "Desconocido" }}
            }}

            $tipo = switch ($entry.Operation) {{
                1 {{ "Instalacion" }}
                2 {{ "Desinstalacion" }}
                default {{ "Otro" }}
            }}

            $resultados += [PSCustomObject]@{{
                Titulo = $entry.Title
                Fecha  = $entry.Date.ToString("yyyy-MM-dd HH:mm")
                Estado = $estado
                Tipo   = $tipo
            }}
        }}

        if ($resultados.Count -eq 0) {{
            ConvertTo-Json @(@{{ Titulo = "SIN_HISTORIAL" }})
        }} else {{
            $resultados | ConvertTo-Json
        }}
    }} catch {{
        ConvertTo-Json @(@{{ error = $_.Exception.Message }})
    }}
    """
    datos = _ejecutar_powershell(ps_script, timeout=30)

    if not datos or (len(datos) == 1 and datos[0].get('Titulo') == 'SIN_HISTORIAL'):
        return []

    if datos and datos[0].get('error'):
        return [{'error': datos[0]['error']}]

    historial = []
    for h in datos:
        historial.append({
            'titulo': h.get('Titulo', ''),
            'fecha': h.get('Fecha', ''),
            'estado': h.get('Estado', 'Desconocido'),
            'tipo': h.get('Tipo', 'Otro')
        })

    return historial


# ==================== INSTALAR UPDATES ====================
def instalar_updates():
    """
    Descarga e instala todos los updates pendientes.
    Retorna resultado de la operacion.
    Pensado para ejecucion remota via comando Firebase.
    """
    ps_script = """
    try {
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $result = $searcher.Search("IsInstalled=0 AND IsHidden=0")

        if ($result.Updates.Count -eq 0) {
            ConvertTo-Json @{ estado = "sin_updates"; mensaje = "No hay updates pendientes"; instalados = 0 }
            return
        }

        $updatesToDownload = New-Object -ComObject Microsoft.Update.UpdateColl
        foreach ($update in $result.Updates) {
            if ($update.EulaAccepted -eq $false) { $update.AcceptEula() }
            $updatesToDownload.Add($update) | Out-Null
        }

        # Descargar
        $downloader = $session.CreateUpdateDownloader()
        $downloader.Updates = $updatesToDownload
        $downloadResult = $downloader.Download()

        # Instalar
        $updatesToInstall = New-Object -ComObject Microsoft.Update.UpdateColl
        foreach ($update in $updatesToDownload) {
            if ($update.IsDownloaded) {
                $updatesToInstall.Add($update) | Out-Null
            }
        }

        $installer = $session.CreateUpdateInstaller()
        $installer.Updates = $updatesToInstall
        $installResult = $installer.Install()

        $estado = switch ($installResult.ResultCode) {
            2 { "exito" }
            3 { "exito_con_errores" }
            4 { "fallido" }
            default { "desconocido" }
        }

        ConvertTo-Json @{
            estado = $estado
            mensaje = "Instalacion completada"
            instalados = $updatesToInstall.Count
            requiere_reinicio = $installResult.RebootRequired
        }
    } catch {
        ConvertTo-Json @{ estado = "error"; mensaje = $_.Exception.Message; instalados = 0 }
    }
    """
    datos = _ejecutar_powershell(ps_script, timeout=600)

    if datos and len(datos) > 0:
        d = datos[0]
        return {
            'estado': d.get('estado', 'error'),
            'mensaje': d.get('mensaje', ''),
            'instalados': d.get('instalados', 0),
            'requiere_reinicio': d.get('requiere_reinicio', False)
        }

    return {'estado': 'error', 'mensaje': 'Sin respuesta de PowerShell', 'instalados': 0}


# ==================== RESUMEN PARA SCANNER ====================
def obtener_resumen_updates():
    """
    Resumen completo para enviar a Firebase.
    Incluye flag de alerta si hay criticos pendientes.
    """
    pendientes = obtener_updates_pendientes()
    historial = obtener_historial_updates(limite=10)

    criticos = [u for u in pendientes if u.get('es_critico')]
    importantes = [u for u in pendientes if u.get('severidad') == 'Importante']

    return {
        'pendientes': pendientes,
        'total_pendientes': len(pendientes),
        'criticos_pendientes': len(criticos),
        'importantes_pendientes': len(importantes),
        'alerta_criticos': len(criticos) > 0,
        'historial_reciente': historial,
        'ultima_verificacion': time.strftime('%Y-%m-%d %H:%M:%S')
    }


# ==================== TESTING ====================
if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("WINDOWS UPDATES")
    print("=" * 60)

    print("\n[PENDIENTES]")
    pendientes = obtener_updates_pendientes()
    if pendientes:
        for u in pendientes:
            marca = "(!)" if u.get('es_critico') else "   "
            print(f"  {marca} [{u['severidad']}] {u['kb']} - {u['titulo']}")
    else:
        print("  Sin updates pendientes")

    print(f"\n[HISTORIAL] (ultimos 10)")
    historial = obtener_historial_updates(limite=10)
    if historial:
        for h in historial:
            print(f"  [{h['estado']}] {h['fecha']} - {h['titulo'][:60]}")
    else:
        print("  Sin historial")

    print(f"\n[RESUMEN]")
    resumen = obtener_resumen_updates()
    print(f"  Pendientes: {resumen['total_pendientes']}")
    print(f"  Criticos:   {resumen['criticos_pendientes']}")
    print(f"  Alerta:     {'SI' if resumen['alerta_criticos'] else 'No'}")
