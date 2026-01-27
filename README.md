# HWAgente
Get-ChildItem -Recurse -Filter *.py | % { "--- INICIO ARCHIVO: $($_.FullName) ---"; Get-Content $_.FullName; "--- FIN ARCHIVO ---"; "`n" } | Out-File codigo_completo_python.txt -Encoding utf8
