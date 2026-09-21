#!/usr/bin/env bash
set -Eeuo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

git fetch --quiet origin main
local_revision="$(git rev-parse HEAD)"
remote_revision="$(git rev-parse origin/main)"
if [[ "$local_revision" == "$remote_revision" ]]; then
  exit 0
fi

git reset --hard "$remote_revision"
./deploy/deploy.sh
