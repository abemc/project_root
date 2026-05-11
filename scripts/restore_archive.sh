#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/restore_archive.sh <archive.tar.gz> [destination]
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <archive.tar.gz> [destination]"
  exit 2
fi
ARCH="$1"
DEST=${2:-.}
if [ ! -f "$ARCH" ]; then
  echo "Archive not found: $ARCH" >&2
  exit 3
fi
echo "Restoring $ARCH -> $DEST"
tar -xzf "$ARCH" -C "$DEST"
echo "Restore complete"
