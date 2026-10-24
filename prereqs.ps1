# Smart CCTV AI :: prerequisite installer (Windows 11)
#
# Checks for Python 3.11, Git, Node 20 LTS, ffmpeg, Ollama. Installs any
# missing one via winget (no manual clicks), then refreshes this session's
# PATH so you can immediately run setup.bat.
#
# Usage:  .\prereqs.bat     (wraps this; or run this .ps1 directly)
# Policy: user-scope installs; no admin elevation needed for most packages.

$ErrorActionPreference = "Stop"

function Info($m)  { Write-Host "[i] $m" -ForegroundColor Cyan }
function Ok($m)    { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m)  { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m)   { Write-Host "[ERR] $m" -ForegroundColor Red }

function Have-Cmd($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    # Pull fresh PATH from registry into current session (so freshly-installed
    # tools are usable immediately, without reopening the terminal).
    $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$m;$u"
}

function Need-Winget {
    if (-not (Have-Cmd winget)) {
        Err "winget not available. Install 'App Installer' from Microsoft Store, then rerun."
        exit 1
    }
}

function Install-Winget($id, $label) {
    Info "installing $label  (winget id: $id)"
    winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Warn "winget returned $LASTEXITCODE for $id; retrying without --silent"
        winget install -e --id $id --accept-package-agreements --accept-source-agreements
    }
    Refresh-Path
}

Write-Host ""
Write-Host "=== Smart CCTV AI :: prerequisite check ===" -ForegroundColor Magenta
Write-Host ""
Need-Winget

# ----- Python 3.11 (required, specific version) -----
$pyOk = $false
if (Have-Cmd py) {
    $v = (& py -3.11 --version 2>&1)
    if ($LASTEXITCODE -eq 0 -and $v -match "3\.11\.") {
        Ok "python 3.11 present ($v)"
        $pyOk = $true
    }
}
if (-not $pyOk) {
    Install-Winget "Python.Python.3.11" "Python 3.11"
    if (Have-Cmd py) {
        $v = (& py -3.11 --version 2>&1)
        if ($v -match "3\.11\.") { Ok "python 3.11 installed ($v)" } else { Err "python 3.11 still not visible" }
    } else {
        Err "py launcher still missing after install"
    }
}

# ----- Git -----
if (Have-Cmd git) {
    Ok "git present ($((git --version)))"
} else {
    Install-Winget "Git.Git" "Git"
}

# ----- Node 20 LTS -----
$nodeOk = $false
if (Have-Cmd node) {
    $nv = (& node --version)
    if ($nv -match "^v(\d+)\.") {
        $maj = [int]$Matches[1]
        if ($maj -ge 20) { Ok "node $nv present"; $nodeOk = $true }
        else { Warn "node $nv found, need v20+" }
    }
}
if (-not $nodeOk) {
    Install-Winget "OpenJS.NodeJS.LTS" "Node 20 LTS"
}

# ----- ffmpeg -----
if (Have-Cmd ffmpeg) {
    Ok "ffmpeg present"
} else {
    Install-Winget "Gyan.FFmpeg" "ffmpeg"
}

# ----- Ollama (optional — for VLM verify + chat agent) -----
if (Have-Cmd ollama) {
    Ok "ollama present"
} else {
    Info "ollama not found (optional — VLM + chat agent only). Installing..."
    try {
        Install-Winget "Ollama.Ollama" "Ollama"
    } catch {
        Warn "ollama install failed; project still works without it (VLM/chat stay off)"
    }
}

Write-Host ""
Write-Host "=== all prerequisites ready ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1) close + reopen PowerShell (some installers only refresh PATH on new sessions)"
Write-Host "  2) cd into the repo folder"
Write-Host "  3) .\setup.bat"
Write-Host "  4) (optional, for VLM/chat) ollama pull qwen2.5vl:3b"
Write-Host ""
