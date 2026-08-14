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
$mediaDestination = Join-Path $BackupDir "brewing-$stamp-media.tar"
$dbId = (docker compose ps -q db).Trim()
$apiId = (docker compose ps -q api).Trim()
if (-not $dbId) { throw 'The PostgreSQL container is not running.' }
if (-not $apiId) { throw 'The API container is not running.' }

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/brewing-backup.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }
docker cp "${dbId}:/tmp/brewing-backup.dump" $destination
if ($LASTEXITCODE -ne 0) { throw 'docker cp failed.' }
docker compose exec -T db rm -f /tmp/brewing-backup.dump

docker compose exec -T api sh -c 'mkdir -p /var/lib/brewing/media && tar -C /var/lib/brewing/media -cf /tmp/brewing-media.tar .'
if ($LASTEXITCODE -ne 0) { throw 'media archive failed.' }
docker cp "${apiId}:/tmp/brewing-media.tar" $mediaDestination
if ($LASTEXITCODE -ne 0) { throw 'media docker cp failed.' }
docker compose exec -T api rm -f /tmp/brewing-media.tar

Write-Output "Backup created: $destination"
Write-Output "Media archive: $mediaDestination"
