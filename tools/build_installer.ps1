# Construit l'exécutable puis l'installeur Windows (Inno Setup).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    throw "Inno Setup 6 introuvable. Installez-le (winget install JRSoftware.InnoSetup) puis relancez."
}

Write-Host "Icône…"
python tools/make_icon.py

Write-Host "Exécutable PyInstaller…"
python -m PyInstaller --noconfirm --clean SpoolManager.spec

Write-Host "Installeur Inno Setup…"
# OneDrive et Windows Defender verrouillent souvent un gros .exe LZMA en cours
# d'écriture dans Documents : on compile une copie hors du dossier, en zip.
$work = Join-Path $env:TEMP ("sm-innosetup-work-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force -Path "$work\dist","$work\docs","$work\installer" | Out-Null
cmd /c "robocopy `"dist\SpoolManager`" `"$work\dist\SpoolManager`" /E /NFL /NDL /NJH /NJS /nc /ns /np" | Out-Null
Copy-Item "docs\spoolmanager.ico" "$work\docs\"
Copy-Item "installer\spoolmanager.iss" "$work\installer\"
$out = Join-Path $work "out"
& $iscc "/DOutputDirOverride=$out" "$work\installer\spoolmanager.iss"
if ($LASTEXITCODE -ne 0) { throw "Compilation de l'installeur échouée." }

$dest = Join-Path $root "installer\output"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $out "*.exe") $dest -ErrorAction SilentlyContinue

Get-ChildItem $out -Filter *.exe | ForEach-Object {
    Write-Host "Prêt : $($_.FullName) ($([math]::Round($_.Length/1MB, 1)) Mo)"
}
