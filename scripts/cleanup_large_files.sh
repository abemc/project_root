#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/cleanup_large_files.sh [targets...]
# If no targets provided, defaults to: .venv myenv checkpoints models hf_cache

TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=backups
mkdir -p "$BACKUP_DIR"

DEFAULTS=(.venv myenv checkpoints models hf_cache)
if [ "$#" -eq 0 ]; then
  TARGETS=("${DEFAULTS[@]}")
else
  TARGETS=("$@")
fi

for t in "${TARGETS[@]}"; do
  if [ ! -e "$t" ]; then
    echo "Skip: $t (not found)"
    continue
  fi
  SAFE_NAME=$(echo "$t" | tr '/ ' '__')
  ARCH="$BACKUP_DIR/${SAFE_NAME}_${TS}.tar.gz"
  echo "Archiving: $t -> $ARCH"
  tar -C . -czf "$ARCH" "$t"
  if tar -tzf "$ARCH" >/dev/null 2>&1; then
    echo "Archive verified: $ARCH"
    rm -rf "$t"
    mkdir -p "$t"
    cat > "$t/ARCHIVED.md" <<EOF
This directory was archived to: $ARCH
Archived at: $TS

To restore, run:
  scripts/restore_archive.sh "$ARCH" [destination]

Note: This directory is a placeholder to keep repository paths intact for imports.
EOF
    echo "Replaced $t with placeholder containing ARCHIVED.md"
  else
    echo "Archive verification failed for $ARCH; leaving original $t in place" >&2
  fi
done

echo "Done. Archives saved under $BACKUP_DIR"
