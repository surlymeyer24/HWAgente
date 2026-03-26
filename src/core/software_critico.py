import subprocess
import json
import time


def _ejecutar_powershell(script, timeout=20):
    """Ejecuta un script PowerShell y devuelve el JSON parseado"""
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', script],
            capture_output=True,
            text=True,
            encoding='utf-8', errors='replace',
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            if isinstance(datos, dict):
                datos = [datos]
            return datos
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        pass
    return []


# ==================== NAVEGADORES ====================
def obtener_navegadores():
    """Detecta navegadores instalados con su version"""
    ps_script = """
    $navegadores = @(
        @{ Nombre = "Google Chrome";    Ruta = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe" },
        @{ Nombre = "Mozilla Firefox";  Ruta = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\firefox.exe" },
        @{ Nombre = "Microsoft Edge";   Ruta = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe" },
        @{ Nombre = "Brave";            Ruta = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\brave.exe" },
        @{ Nombre = "Opera";            Ruta = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\opera.exe" }
    )

    $resultado = @()
    foreach ($nav in $navegadores) {
        try {
            $regPath = Get-ItemProperty -Path $nav.Ruta -ErrorAction Stop
            $exePath = $regPath.'(default)'
            if ($exePath -and (Test-Path $exePath)) {
                $version = (Get-Item $exePath).VersionInfo.ProductVersion
                $resultado += [PSCustomObject]@{
                    Nombre  = $nav.Nombre
                    Version = $version
                    Ruta    = $exePath
                }
            }
        } catch { }
    }

    if ($resultado.Count -eq 0) {
        ConvertTo-Json @(@{ Nombre = "NINGUNO" })
    } else {
        $resultado | ConvertTo-Json
    }
    """
    datos = _ejecutar_powershell(ps_script)

    if not datos or (len(datos) == 1 and datos[0].get('Nombre') == 'NINGUNO'):
        return []

    return [{
        'nombre': d.get('Nombre', ''),
        'version': d.get('Version', 'Desconocida'),
        'ruta': d.get('Ruta', '')
    } for d in datos]


# ==================== MICROSOFT OFFICE ====================
def obtener_office():
    """Detecta instalaciones de Microsoft Office"""
    ps_script = """
    $office = @()

    # Office Click-to-Run (365, 2019, 2021, 2024)
    $c2r = Get-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration" -ErrorAction SilentlyContinue
    if ($c2r) {
        $office += [PSCustomObject]@{
            Producto = if ($c2r.ProductReleaseIds) { $c2r.ProductReleaseIds } else { "Office 365/2019+" }
            Version  = if ($c2r.VersionToReport) { $c2r.VersionToReport } else { "Desconocida" }
            Canal    = if ($c2r.UpdateChannel) { $c2r.UpdateChannel.Split("/")[-1] } else { "N/A" }
            Tipo     = "Click-to-Run"
        }
    }

    # Office MSI (2016 y anteriores)
    $rutas_msi = @(
        "HKLM:\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\InstallRoot",
        "HKLM:\\SOFTWARE\\Microsoft\\Office\\15.0\\Common\\InstallRoot",
        "HKLM:\\SOFTWARE\\Microsoft\\Office\\14.0\\Common\\InstallRoot"
    )
    $versiones_nombre = @{ "16.0" = "Office 2016"; "15.0" = "Office 2013"; "14.0" = "Office 2010" }

    foreach ($ruta in $rutas_msi) {
        try {
            $reg = Get-ItemProperty -Path $ruta -ErrorAction Stop
            if ($reg.Path) {
                $ver = ($ruta -split "\\\\")[4]
                $office += [PSCustomObject]@{
                    Producto = $versiones_nombre[$ver]
                    Version  = $ver
                    Canal    = "N/A"
                    Tipo     = "MSI"
                }
            }
        } catch { }
    }

    if ($office.Count -eq 0) {
        ConvertTo-Json @(@{ Producto = "NO_INSTALADO" })
    } else {
        $office | ConvertTo-Json
    }
    """
    datos = _ejecutar_powershell(ps_script)

    if not datos or (len(datos) == 1 and datos[0].get('Producto') == 'NO_INSTALADO'):
        return []

    return [{
        'producto': d.get('Producto', ''),
        'version': d.get('Version', 'Desconocida'),
        'canal': d.get('Canal', 'N/A'),
        'tipo': d.get('Tipo', '')
    } for d in datos]


# ==================== ANTIVIRUS ====================
def obtener_antivirus():
    """
    Detecta antivirus instalados.
    Usa SecurityCenter2 para terceros + WMI para Defender.
    """
    ps_script = """
    $antivirus = @()

    # Defender
    try {
        $defender = Get-MpComputerStatus -ErrorAction Stop
        $dias_firma = (New-TimeSpan -Start $defender.AntivirusSignatureLastUpdated -End (Get-Date)).Days

        $antivirus += [PSCustomObject]@{
            Nombre              = "Windows Defender"
            Habilitado          = $defender.AntivirusEnabled
            ProteccionTiempoReal = $defender.RealTimeProtectionEnabled
            VersionFirmas       = $defender.AntivirusSignatureVersion
            UltimaActFirmas     = $defender.AntivirusSignatureLastUpdated.ToString("yyyy-MM-dd HH:mm")
            DiasDesdeActFirmas  = $dias_firma
            FirmasDesactualizadas = ($dias_firma -gt 3)
            UltimoEscaneo       = if ($defender.FullScanEndTime) { $defender.FullScanEndTime.ToString("yyyy-MM-dd HH:mm") } else { "Nunca" }
        }
    } catch { }

    # Antivirus de terceros via SecurityCenter2
    try {
        $terceros = Get-CimInstance -Namespace "root/SecurityCenter2" -ClassName AntiVirusProduct -ErrorAction Stop
        foreach ($av in $terceros) {
            if ($av.displayName -eq "Windows Defender") { continue }

            $hexState = "0x{0:X}" -f $av.productState
            $habilitado = ($hexState.Substring(2,2) -in @("10","11"))
            $firmasOk = ($hexState.Substring(4,2) -eq "00")

            $antivirus += [PSCustomObject]@{
                Nombre              = $av.displayName
                Habilitado          = $habilitado
                ProteccionTiempoReal = $habilitado
                VersionFirmas       = "N/A"
                UltimaActFirmas     = "N/A"
                DiasDesdeActFirmas  = -1
                FirmasDesactualizadas = (-not $firmasOk)
                UltimoEscaneo       = "N/A"
            }
        }
    } catch { }

    if ($antivirus.Count -eq 0) {
        ConvertTo-Json @(@{ Nombre = "NINGUNO" })
    } else {
        $antivirus | ConvertTo-Json
    }
    """
    datos = _ejecutar_powershell(ps_script, timeout=15)

    if not datos or (len(datos) == 1 and datos[0].get('Nombre') == 'NINGUNO'):
        return [{'nombre': 'Sin antivirus detectado', 'alerta': True}]

    resultado = []
    for d in datos:
        habilitado = d.get('Habilitado', False)
        proteccion_rt = d.get('ProteccionTiempoReal', False)
        firmas_viejas = d.get('FirmasDesactualizadas', False)

        alerta = not habilitado or not proteccion_rt or firmas_viejas

        resultado.append({
            'nombre': d.get('Nombre', ''),
            'habilitado': habilitado,
            'proteccion_tiempo_real': proteccion_rt,
            'version_firmas': d.get('VersionFirmas', 'N/A'),
            'ultima_act_firmas': d.get('UltimaActFirmas', 'N/A'),
            'dias_desde_act_firmas': d.get('DiasDesdeActFirmas', -1),
            'firmas_desactualizadas': firmas_viejas,
            'ultimo_escaneo': d.get('UltimoEscaneo', 'N/A'),
            'alerta': alerta
        })

    return resultado


# ==================== RESUMEN PARA SCANNER ====================
def obtener_software_critico():
    """
    Resumen completo de software critico para enviar a Firebase.
    Incluye alertas por antivirus deshabilitado o firmas viejas.
    """
    navegadores = obtener_navegadores()
    office = obtener_office()
    antivirus = obtener_antivirus()

    alertas = []
    for av in antivirus:
        if av.get('alerta'):
            if av.get('nombre') == 'Sin antivirus detectado':
                alertas.append("Sin antivirus detectado")
            else:
                motivos = []
                if not av.get('habilitado'):
                    motivos.append("deshabilitado")
                if not av.get('proteccion_tiempo_real'):
                    motivos.append("sin proteccion en tiempo real")
                if av.get('firmas_desactualizadas'):
                    motivos.append("firmas desactualizadas")
                alertas.append(f"{av['nombre']}: {', '.join(motivos)}")

    return {
        'navegadores': navegadores,
        'office': office,
        'antivirus': antivirus,
        'alertas_seguridad': alertas,
        'tiene_alertas': len(alertas) > 0,
        'ultima_verificacion': time.strftime('%Y-%m-%d %H:%M:%S')
    }


# ==================== TESTING ====================
if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("SOFTWARE CRITICO")
    print("=" * 60)

    print("\n[NAVEGADORES]")
    for nav in obtener_navegadores():
        print(f"  {nav['nombre']} v{nav['version']}")

    print("\n[OFFICE]")
    office = obtener_office()
    if office:
        for o in office:
            print(f"  {o['producto']} v{o['version']} ({o['tipo']})")
    else:
        print("  No instalado")

    print("\n[ANTIVIRUS]")
    for av in obtener_antivirus():
        estado = "OK" if not av.get('alerta') else "ALERTA"
        print(f"  [{estado}] {av['nombre']}")
        if av.get('version_firmas') and av['version_firmas'] != 'N/A':
            print(f"         Firmas: {av['version_firmas']} ({av.get('ultima_act_firmas', '')})")

    print("\n[RESUMEN]")
    resumen = obtener_software_critico()
    print(f"  Alertas: {resumen['alertas_seguridad'] if resumen['alertas_seguridad'] else 'Ninguna'}")
