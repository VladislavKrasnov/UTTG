#!/usr/bin/env bash
set -Eeuo pipefail

backup_dir="/var/backups/uttg"
retention_days=7
container="$(docker ps --filter label=com.docker.swarm.service.name=uttg_db --format '{{.ID}}' | head -n1)"
[[ -n "$container" ]] || { echo "Database task is not running" >&2; exit 1; }

target="${backup_dir}/uttg-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker exec "$container" pg_dump -U uttg -d uttg --format=custom --compress=6 >"${target}.partial"
docker exec -i "$container" pg_restore --list >/dev/null <"${target}.partial"
mv "${target}.partial" "$target"
chmod 600 "$target"
find "$backup_dir" -name 'uttg-*.dump' -mtime +"$retention_days" -delete
echo "Backup written to ${target}"
