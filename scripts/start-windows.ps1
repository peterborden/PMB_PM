param(
  [ValidateSet("docker", "local")]
  [string]$Mode = "docker"
)

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RunDir = Join-Path $Root ".run"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

function Start-TrackedProcess {
  param(
    [string]$Name,
    [string]$FilePath,
    [string]$Arguments,
    [string]$WorkingDirectory
  )

  $pidFile = Join-Path $RunDir "$Name.pid"
  $logFile = Join-Path $RunDir "$Name.log"

  if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -Raw
    try {
      Get-Process -Id $existingPid -ErrorAction Stop | Out-Null
      Write-Host "$Name is already running (pid $existingPid)."
      return
    } catch {
      Remove-Item $pidFile -Force
    }
  }

  $proc = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $Arguments `
    -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $logFile `
    -PassThru

  Set-Content -Path $pidFile -Value $proc.Id
  Write-Host "Started $Name (pid $($proc.Id))"
}

if ($Mode -eq "docker") {
  Push-Location $Root
  docker compose up --build -d
  Pop-Location
  Write-Host "Docker app started at http://127.0.0.1:8000"
  exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is required for local backend start."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm is required for local frontend start."
}

Start-TrackedProcess `
  -Name "backend" `
  -FilePath "uv" `
  -Arguments "run --project backend uvicorn backend.app.main:app --host 127.0.0.1 --port 8000" `
  -WorkingDirectory $Root

Start-TrackedProcess `
  -Name "frontend" `
  -FilePath "npm" `
  -Arguments "run dev -- --hostname 127.0.0.1 --port 3000" `
  -WorkingDirectory (Join-Path $Root "frontend")

Write-Host "Local services started:"
Write-Host "  Backend:  http://127.0.0.1:8000"
Write-Host "  Frontend: http://127.0.0.1:3000"
