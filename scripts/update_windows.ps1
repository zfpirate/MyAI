param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$ArchivePath,
    [Parameter(Mandatory = $true)][string]$ExpectedSha256,
    [Parameter(Mandatory = $true)][string]$InstallDirectory,
    [Parameter(Mandatory = $true)][string]$StagingDirectory,
    [Parameter(Mandatory = $true)][string]$ExecutableName
)

$ErrorActionPreference = "Stop"
$backupDirectory = "$InstallDirectory.backup-$([guid]::NewGuid().ToString('N'))"
$stagedApplication = Join-Path $StagingDirectory "CAPRI"
$executablePath = Join-Path $InstallDirectory $ExecutableName
$movedOldApplication = $false

try {
    $deadline = (Get-Date).AddMinutes(2)
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        if ((Get-Date) -ge $deadline) {
            throw "CAPRI ne s'est pas fermée à temps."
        }
        Start-Sleep -Milliseconds 250
    }

    $actualSha256 = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash
    if ($actualSha256 -ne $ExpectedSha256) {
        throw "La vérification SHA-256 de l'archive a échoué."
    }

    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $StagingDirectory -Force
    if (-not (Test-Path -LiteralPath (Join-Path $stagedApplication $ExecutableName) -PathType Leaf)) {
        throw "Le paquet ne contient pas CAPRI.exe."
    }

    Move-Item -LiteralPath $InstallDirectory -Destination $backupDirectory
    $movedOldApplication = $true

    try {
        Move-Item -LiteralPath $stagedApplication -Destination $InstallDirectory
    }
    catch {
        Move-Item -LiteralPath $backupDirectory -Destination $InstallDirectory
        $movedOldApplication = $false
        throw
    }

    Start-Process -FilePath $executablePath
    Remove-Item -LiteralPath $backupDirectory -Recurse -Force
}
catch {
    if ($movedOldApplication -and -not (Test-Path -LiteralPath $InstallDirectory)) {
        Move-Item -LiteralPath $backupDirectory -Destination $InstallDirectory
    }

    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "La mise à jour de CAPRI a échoué : $($_.Exception.Message)",
        "Mise à jour de CAPRI",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null

    if (Test-Path -LiteralPath $executablePath -PathType Leaf) {
        Start-Process -FilePath $executablePath
    }
}
finally {
    Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$ArchivePath.sha256" -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StagingDirectory -Recurse -Force -ErrorAction SilentlyContinue
}
