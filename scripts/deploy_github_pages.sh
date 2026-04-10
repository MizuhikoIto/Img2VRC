#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[deploy] %s\n' "$*"
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$name" >&2
    exit 1
  fi
}

OUTPUT_PUBLISH_DIR="${OUTPUT_PUBLISH_DIR:-public}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
DEPLOY_ROOT="${DEPLOY_ROOT:-.deploy-worktree}"

require_env "GITHUB_REPO_URL"

if [[ ! -d "$OUTPUT_PUBLISH_DIR" ]]; then
  printf 'Publish directory not found: %s\n' "$OUTPUT_PUBLISH_DIR" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  printf 'git command not found\n' >&2
  exit 1
fi

mkdir -p "$DEPLOY_ROOT"
TMP_DIR="$(mktemp -d "$DEPLOY_ROOT/worktree.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

REMOTE_URL="$GITHUB_REPO_URL"
if [[ -n "${GITHUB_TOKEN:-}" && "$GITHUB_REPO_URL" =~ ^https://github.com/ ]]; then
  REMOTE_URL="${GITHUB_REPO_URL/https:\/\//https:\/\/${GITHUB_TOKEN}@}"
fi

log "Cloning target repository"
git clone --branch "$GITHUB_BRANCH" --single-branch "$REMOTE_URL" "$TMP_DIR" 2>/dev/null || {
  log "Branch clone failed, creating orphan checkout"
  git clone "$REMOTE_URL" "$TMP_DIR"
  (
    cd "$TMP_DIR"
    if git show-ref --verify --quiet "refs/heads/$GITHUB_BRANCH"; then
      git checkout "$GITHUB_BRANCH"
    else
      git checkout --orphan "$GITHUB_BRANCH"
      find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
    fi
  )
}

log "Refreshing repository contents"
find "$TMP_DIR" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
cp -a "$OUTPUT_PUBLISH_DIR"/. "$TMP_DIR"/

(
  cd "$TMP_DIR"

  if [[ -n "${CUSTOM_DOMAIN:-}" ]]; then
    printf '%s\n' "$CUSTOM_DOMAIN" > CNAME
  fi

  git add --all

  if git diff --cached --quiet; then
    log "No changes to commit"
    exit 0
  fi

  git commit -m "Update slideshow $(date '+%Y-%m-%d %H:%M:%S %z')"
  git push origin "$GITHUB_BRANCH"
)

log "Deploy completed"
