$ErrorActionPreference = "Stop"

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Impossible d'installer les dépendances de compilation."
}

python -m PyInstaller --noconfirm --clean CAPRI.spec
if ($LASTEXITCODE -ne 0) {
    throw "La compilation de CAPRI.exe a échoué."
}

$output = Join-Path $PSScriptRoot "dist\CAPRI-windows-x64.zip"
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Force
}
Compress-Archive -Path (Join-Path $PSScriptRoot "dist\CAPRI") `
    -DestinationPath $output -CompressionLevel Optimal

$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$output.sha256" -Value "$hash  CAPRI-windows-x64.zip" -Encoding ASCII
Write-Output "Application compilée : $output"
