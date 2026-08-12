param(
    [string]$BackupDir = $(if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { 'B:\brewing-platform-backups' })
)

$ErrorActionPreference = 'Stop'
$resolvedRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $resolvedRepo

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$filename = "brewing-$stamp.dump"
$destination = Join-Path $BackupDir $filename
$containerId = (docker compose ps -q db).Trim()
if (-not $containerId) { throw 'The PostgreSQL container is not running.' }

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/brewing-backup.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }
docker cp "${containerId}:/tmp/brewing-backup.dump" $destination
if ($LASTEXITCODE -ne 0) { throw 'docker cp failed.' }
docker compose exec -T db rm -f /tmp/brewing-backup.dump

Write-Output "Backup created: $destination"

