param(
  [ValidateSet("docker", "local")]
  [string]$Mode = "docker"
)

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".run"

function Stop-TrackedProcess {
  param([string]$Name)

  $pidFile = Join-Path $RunDir "$Name.pid"
  if (-not (Test-Path $pidFile)) {
    Write-Host "$Name is not running (no pid file)."
    return
  }

  $pidValue = Get-Content $pidFile -Raw
  try {
    Stop-Process -Id $pidValue -ErrorAction Stop
    Write-Host "Stopped $Name (pid $pidValue)"
  } catch {
    Write-Host "$Name pid $pidValue was not active."
  }

  Remove-Item $pidFile -Force
}

if ($Mode -eq "docker") {
  Push-Location $Root
  docker compose down
  Pop-Location
  Write-Host "Docker app stopped."
  exit 0
}

Stop-TrackedProcess -Name "frontend"
Stop-TrackedProcess -Name "backend"
