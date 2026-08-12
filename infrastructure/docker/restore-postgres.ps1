param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

$ErrorActionPreference = 'Stop'
$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
$resolvedRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $resolvedRepo

$confirmation = Read-Host 'Restore replaces objects in the development database. Type RESTORE to continue'
if ($confirmation -cne 'RESTORE') { throw 'Restore cancelled.' }

$containerId = (docker compose ps -q db).Trim()
if (-not $containerId) { throw 'The PostgreSQL container is not running.' }
docker cp $resolvedBackup "${containerId}:/tmp/brewing-restore.dump"
if ($LASTEXITCODE -ne 0) { throw 'docker cp failed.' }
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/brewing-restore.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed.' }
docker compose exec -T db rm -f /tmp/brewing-restore.dump

Write-Output 'Restore completed. Restart the API and verify /health/ready.'

