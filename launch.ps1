# vamos launcher (Windows PowerShell) — feature parity with launch.sh.
#
#   .\launch.ps1                 # ensure venv, install deps, launch UI
#   .\launch.ps1 -InstallCrons   # also install Task Scheduler entries from crons.yml
#   .\launch.ps1 -Prep           # run morning prep (sod + inbox + standup) before UI
#   .\launch.ps1 -NoUi           # setup only, don't launch UI
#   .\launch.ps1 -Update         # re-run pip install (force-update deps)
#   .\launch.ps1 -Port 9000      # override UI port (default 8501)
#
# Reads VAMOS_AUTO_PREP from .env: when "true", auto-prep runs even without -Prep.
# First-time setup tip: if you get "running scripts is disabled" errors, run:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

param(
  [switch]$InstallCrons,
  [switch]$Prep,
  [switch]$NoUi,
  [switch]$Update,
  [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$RootDir = (Get-Location).Path

# --- venv ---
if (-not (Test-Path ".venv")) {
  Write-Host "[launch] creating virtualenv .venv"
  python -m venv .venv
  $Update = $true
}

. .\.venv\Scripts\Activate.ps1

# --- deps ---
if ($Update -or -not (Get-Command vamos -ErrorAction SilentlyContinue)) {
  Write-Host "[launch] installing vamos + Streamlit (this may take a minute on first run)"
  # --no-cache-dir avoids "Cache entry deserialization failed" warnings from a
  # mismatched pip cache (different Python version).
  pip install -q --no-cache-dir --upgrade pip
  pip install -q --no-cache-dir -e ".[ui]"
}

# --- .env sanity ---
if (-not (Test-Path ".env")) {
  Write-Warning "[launch] .env not found. Copy .env.example to .env and fill in your ADO_PAT."
  Write-Warning "[launch]   Copy-Item .env.example .env"
}

# --- auto-prep (read VAMOS_AUTO_PREP from .env if -Prep wasn't passed) ---
if (-not $Prep -and (Test-Path ".env")) {
  $envText = Get-Content ".env" -Raw -ErrorAction SilentlyContinue
  if ($envText -match "(?m)^VAMOS_AUTO_PREP\s*=\s*true\s*$") {
    $Prep = $true
  }
}

if ($Prep) {
  Write-Host "[launch] running morning prep (sod + inbox + standup)"
  try {
    vamos prep
  } catch {
    Write-Warning "[launch] prep failed: $_  (continuing to UI launch)"
  }
}

# --- crons / Task Scheduler ---
if ($InstallCrons) {
  if (-not (Test-Path "crons.yml")) {
    Write-Host "[launch] crons.yml not found; copying from crons.yml.example"
    Copy-Item "crons.yml.example" "crons.yml"
  }
  Write-Host "[launch] installing Task Scheduler entries from crons.yml:"
  vamos cron-list
  vamos cron-install
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "[launch] cron-install reported errors; check output above."
  }
}

# --- UI ---
if ($NoUi) {
  Write-Host "[launch] setup complete (UI launch skipped via -NoUi)"
  exit 0
}

$Url = "http://localhost:$Port"
Write-Host ""
Write-Host "================================================================"
Write-Host "  vamos UI starting at:  $Url"
Write-Host "================================================================"
Write-Host ""

# Open the browser a couple seconds in, in case Streamlit's auto-open misses.
Start-Job -ScriptBlock { Start-Sleep -Seconds 3; Start-Process $using:Url } | Out-Null

vamos ui --port $Port
