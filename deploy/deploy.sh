#!/usr/bin/env bash
set -Eeuo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

set -a
source deploy/.env
set +a

revision="$(git rev-parse --verify HEAD)"
export UTTG_IMAGE="uttg:${revision}"

docker build --pull --tag "$UTTG_IMAGE" .
# On a first install the data services must exist before Alembic can attach to
# the overlay network. On subsequent releases migrations run before replacing
# API tasks, keeping healthy instances available throughout the rollout.
if ! docker stack ls --format '{{.Name}}' | grep -qx uttg; then
  docker stack deploy --resolve-image never -c deploy/stack.yml uttg
  for _ in $(seq 1 30); do
    if docker service ps uttg_db --filter desired-state=running --format '{{.CurrentState}}' | grep -q Running; then
      break
    fi
    sleep 2
  done
fi

migrated=false
for _ in $(seq 1 30); do
  if docker run --rm --network uttg_internal --env-file deploy/.env \
    --env UTTG_ENVIRONMENT=production \
    --env UTTG_DATABASE_URL="$UTTG_DATABASE_URL" \
    --env UTTG_VALKEY_URL=valkey://valkey:6379/0 \
    --env UTTG_NATS_URL=nats://nats:4222 \
    "$UTTG_IMAGE" alembic upgrade head; then
    migrated=true
    break
  fi
  sleep 2
done
if [[ "$migrated" != true ]]; then
  echo "Database migrations did not complete; rollout cancelled." >&2
  exit 1
fi

docker stack deploy --prune --resolve-image never -c deploy/stack.yml uttg
docker image prune --force --filter "label=io.uttg.release=true" >/dev/null 2>&1 || true
