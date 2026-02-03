param(
  [switch]$SkipSoundfont
)

$ErrorActionPreference = "Stop"

function Test-Command {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Write-Info {
  param([string]$Msg)
  Write-Host "[claw-daw] $Msg"
}

$RepoUrl = "https://github.com/sdiaoune/claw-daw.git"
$SoundfontUrl = "https://github.com/pianobooster/fluid-soundfont/releases/latest/download/FluidR3_GM.sf2"

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator
)

function Ensure-Choco {
  if (Test-Command "choco") { return $true }
  if (-not $IsAdmin) {
    Write-Host "[claw-daw] Chocolatey is required to install fluidsynth/ffmpeg." -ForegroundColor Yellow
    Write-Host "[claw-daw] Re-run this script in an Administrator PowerShell." -ForegroundColor Yellow
    return $false
  }
  Write-Info "Installing Chocolatey..."
  Set-ExecutionPolicy Bypass -Scope Process -Force
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
  iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
  return (Test-Command "choco")
}

function Invoke-Python {
  param([string[]]$Args)
  if (Test-Command "python") {
    & python @Args
    return $LASTEXITCODE
  }
  if (Test-Command "py") {
    & py -3 @Args
    return $LASTEXITCODE
  }
  throw "Python not found on PATH."
}

if (-not (Test-Command "python") -and -not (Test-Command "py")) {
  if (Test-Command "winget") {
    Write-Info "Installing Python via winget..."
    & winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  } elseif (Ensure-Choco) {
    Write-Info "Installing Python via Chocolatey..."
    choco install -y python
  } else {
    throw "Python 3.10+ is required. Install Python and re-run."
  }
}

if (-not (Test-Command "fluidsynth")) {
  if (-not (Ensure-Choco)) {
    throw "Chocolatey is required to install fluidsynth. Re-run as Administrator."
  }
  Write-Info "Installing fluidsynth..."
  choco install -y fluidsynth
}

if (-not (Test-Command "ffmpeg")) {
  if (-not (Ensure-Choco)) {
    throw "Chocolatey is required to install ffmpeg. Re-run as Administrator."
  }
  Write-Info "Installing ffmpeg..."
  choco install -y ffmpeg
}

Write-Info "Installing pipx..."
Invoke-Python -Args @("-m", "pip", "install", "--user", "--upgrade", "pip", "pipx") | Out-Null
Invoke-Python -Args @("-m", "pipx", "ensurepath") | Out-Null

Write-Info "Installing claw-daw via pipx..."
$rc = Invoke-Python -Args @("-m", "pipx", "install", "--force", "claw-daw")
if ($rc -ne 0) {
  Write-Host "[claw-daw] PyPI install failed; falling back to GitHub..." -ForegroundColor Yellow
  Invoke-Python -Args @("-m", "pipx", "install", "--force", "git+$RepoUrl") | Out-Null
}

if (-not $SkipSoundfont) {
  $LocalApp = $env:LOCALAPPDATA
  if (-not $LocalApp) { $LocalApp = Join-Path $env:USERPROFILE "AppData\Local" }
  $Sf2Dir = Join-Path $LocalApp "claw-daw\soundfonts"
  $Sf2Path = Join-Path $Sf2Dir "FluidR3_GM.sf2"

  $HasSf2 = $false
  $Candidates = @(
    $Sf2Path,
    (Join-Path $LocalApp "Sounds\Banks\default.sf2"),
    "C:\Program Files\Common Files\Sounds\Banks\default.sf2"
  )
  foreach ($p in $Candidates) {
    if (Test-Path $p) { $HasSf2 = $true; break }
  }

  if (-not $HasSf2) {
    Write-Info "No GM SoundFont found; downloading FluidR3_GM..."
    New-Item -ItemType Directory -Force -Path $Sf2Dir | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-WebRequest -Uri $SoundfontUrl -OutFile $Sf2Path -UseBasicParsing
  }
}

Write-Host ""
Write-Info "Done. If 'claw-daw' is not found, restart PowerShell."
Write-Host "Try:"
Write-Host "  claw-daw --help"
