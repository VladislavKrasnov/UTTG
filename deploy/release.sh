#!/usr/bin/env bash
set -Eeuo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

host="${UTTG_DEPLOY_HOST:?Set UTTG_DEPLOY_HOST, for example ubuntu@203.0.113.10}"
key="${UTTG_DEPLOY_KEY:-$HOME/.ssh/uttg_deploy_ed25519}"
ssh_command=(ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes)
rsync_shell="ssh -i $key -o IdentitiesOnly=yes -o BatchMode=yes"

release="$(git rev-parse --short=12 HEAD)"
if ! git diff --quiet HEAD -- . || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  release="${release}-$(date -u +%Y%m%d%H%M%S)"
fi

if [[ "${UTTG_SKIP_WEB:-0}" != 1 ]]; then
  npm ci --prefix web --no-audit --no-fund
  npm run build --prefix web
fi

rsync -az --delete -e "$rsync_shell" \
  --exclude '.git/' --exclude '.venv/' --exclude 'node_modules/' --exclude 'web/' \
  --exclude '__pycache__/' --exclude '.mypy_cache/' --exclude '.ruff_cache/' \
  --exclude '.pytest_cache/' --exclude 'deploy/.env' --exclude '.env' \
  ./ "${host}:/opt/uttg/"

if [[ "${UTTG_SKIP_WEB:-0}" != 1 ]]; then
  for site in demo presentation hub; do
    rsync -az -e "$rsync_shell" --exclude index.html "web/${site}/dist/" "${host}:/opt/uttg-sites/${site}/"
    rsync -az -e "$rsync_shell" "web/${site}/dist/index.html" "${host}:/opt/uttg-sites/${site}/index.html"
  done
fi

"${ssh_command[@]}" "$host" "cd /opt/uttg && ./deploy/deploy.sh '${release}'"
