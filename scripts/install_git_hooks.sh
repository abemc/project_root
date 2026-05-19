#!/usr/bin/env bash
set -euo pipefail

# Install client-side git hook to prevent accidental pushing of backup branches
HOOK_DIR=.git/hooks
HOOK_FILE="$HOOK_DIR/pre-push"

mkdir -p "$HOOK_DIR"
cat > "$HOOK_FILE" <<'HOOK'
#!/usr/bin/env bash
# Prevent pushing branches with 'backup' in their name
while read local_ref local_sha remote_ref remote_sha
do
  branch=$(echo "$local_ref" | sed 's|refs/heads/||')
  if [[ "$branch" =~ (^backup/|backup) ]]; then
    echo "Push blocked: branch '$branch' appears to be a backup branch. Manage backups locally."
    exit 1
  fi
done
exit 0
HOOK

chmod +x "$HOOK_FILE"
echo "Installed pre-push hook to block backup branches: $HOOK_FILE"

exit 0
