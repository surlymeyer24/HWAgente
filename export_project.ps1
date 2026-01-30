# Script para consolidar código Python
$outputFile = "codigo_completo_python.txt"
$excludeFolders = @("venv", ".venv", "__pycache__", ".git")

Get-ChildItem -Recurse -Filter *.py | Where-Object { 
    $path = $_.FullName
    $shouldExclude = $false
    foreach ($folder in $excludeFolders) {
        if ($path -like "*\$folder\*") { $shouldExclude = $true; break }
    }
    -not $shouldExclude
} | ForEach-Object {
    "--- INICIO ARCHIVO: $($_.FullName) ---"
    Get-Content $_.FullName
    "--- FIN ARCHIVO ---"
    "`n"
} | Out-File $outputFile -Encoding utf8

Write-Host "Consolidación completada con éxito en: $outputFile" -ForegroundColor Green