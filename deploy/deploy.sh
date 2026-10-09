#!/usr/bin/env bash
set -Eeuo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

set -a
source deploy/.env
set +a

release="${1:?Usage: deploy.sh <release-id>}"
[[ "$release" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo "Invalid release id" >&2; exit 1; }
export UTTG_IMAGE="uttg:${release}"
export UTTG_CADDYFILE_DIGEST="$(sha256sum deploy/Caddyfile | cut -c1-12)"

docker build --pull --label io.uttg.release=true --tag "$UTTG_IMAGE" .

if ! docker stack ls --format '{{.Name}}' | grep -qx uttg; then
  docker stack deploy --detach=true --resolve-image never -c deploy/stack.yml uttg
fi

for _ in $(seq 1 60); do
  if docker service ps uttg_db --filter desired-state=running --format '{{.CurrentState}}' | grep -q '^Running'; then
    break
  fi
  sleep 2
done

migrated=false
for _ in $(seq 1 30); do
  if docker run --rm --network uttg_internal \
    --env UTTG_ENVIRONMENT=production \
    --env UTTG_DATABASE_URL \
    --env UTTG_IP_FINGERPRINT_SECRET \
    --env UTTG_WEBHOOK_ENCRYPTION_KEY \
    --env UTTG_VALKEY_URL=valkey://valkey:6379/0 \
    --env UTTG_NATS_URL=nats://nats:4222 \
    "$UTTG_IMAGE" alembic upgrade head; then
    migrated=true
    break
  fi
  sleep 3
done
if [[ "$migrated" != true ]]; then
  echo "Database migrations did not complete; rollout cancelled." >&2
  exit 1
fi

docker stack deploy --detach=false --prune --resolve-image never -c deploy/stack.yml uttg

for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 https://uttg.oxis.cc/v1/ready >/dev/null; then
    echo "Release ${release} is serving traffic."
    docker image ls --filter label=io.uttg.release=true --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' \
      | sort -k2 -r | tail -n +4 | cut -d' ' -f1 | xargs -r docker image rm >/dev/null 2>&1 || true
    docker config ls --format '{{.Name}}' | grep '^uttg-caddyfile-' \
      | grep -v "${UTTG_CADDYFILE_DIGEST}" | xargs -r docker config rm >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 4
done
echo "Release ${release} did not become ready; Swarm rollback policy applies." >&2
exit 1
