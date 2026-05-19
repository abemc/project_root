#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/local_backup.sh ["docs learning_materials"]
# Creates a timestamped tar.gz under local_backups/ (which is git-ignored)

TS=$(date +%Y%m%d_%H%M%S)
OUT_DIR=local_backups
mkdir -p "$OUT_DIR"
TARGETS=${1:-"docs learning_materials"}
ARCHIVE="$OUT_DIR/backup_${TS}.tar.gz"

echo "Creating local backup: $ARCHIVE"
tar -czf "$ARCHIVE" $TARGETS
echo "Backup created: $ARCHIVE"

# Optionally create a local-only branch (do NOT push)
if [ "${CREATE_BRANCH:-0}" = "1" ]; then
  BRANCH="backup/${TS}"
  git checkout -b "$BRANCH" || git branch "$BRANCH"
  echo "Created local branch $BRANCH (not pushed)."
fi

exit 0
