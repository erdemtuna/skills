---
name: session-branch
description: Branch the current session, creating a new session that inherits conversation history up to the current point while preserving the original session intact. This skill should be used when the user wants to create a new session branch for experimentation or parallel development without affecting the original session.
---
# Session Branch Skill

Branch the current session, creating a new session that inherits conversation history up to the current point while preserving the original session intact.

## Trigger

Use this skill when the user says:
- "branch", "branch session", "fork session"
- "create a branch from here"
- "save this point and branch"

## Instructions

When invoked, perform the following steps. Execute steps 1-6 in a single bash script for reliability.

### 1. Identify Current Session

The current session ID is in `<session_context>` → session folder path.

### 2. Run Branch Script

Run the following as a single bash script, substituting `CURRENT_SESSION_ID` with the actual value:

```bash
set -e

CURRENT_SESSION_ID="<current-session-id>"
STATE_DIR="$HOME/.copilot/session-state"
CURRENT_SESSION="$STATE_DIR/$CURRENT_SESSION_ID"
NEW_SESSION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
NEW_SESSION="$STATE_DIR/$NEW_SESSION_ID"

# Get current summary for branch note
CURRENT_SUMMARY=$(grep '^summary:' "$CURRENT_SESSION/workspace.yaml" | head -1 | sed 's/^summary: //')

# Copy entire session
cp -r "$CURRENT_SESSION" "$NEW_SESSION"

# Update workspace.yaml: new ID + branch metadata
sed -i "s/^id: .*/id: $NEW_SESSION_ID/" "$NEW_SESSION/workspace.yaml"
# Add branch tracking fields (copilot overwrites summary, but preserves unknown fields)
cat >> "$NEW_SESSION/workspace.yaml" << EOF
branch_of: $CURRENT_SESSION_ID
branch_note: "Branched from: $CURRENT_SUMMARY"
EOF

# Fix session.start event to reference new session ID
python3 -c "
import json
lines = open('$NEW_SESSION/events.jsonl').readlines()
new_lines = []
for line in lines:
    evt = json.loads(line.strip())
    if evt['type'] == 'session.start':
        evt['data']['sessionId'] = '$NEW_SESSION_ID'
    new_lines.append(json.dumps(evt, separators=(',', ':')))
with open('$NEW_SESSION/events.jsonl', 'w') as f:
    f.write('\n'.join(new_lines) + '\n')
"

# Reset rewind snapshots (they reference old event state)
echo '{"version":1,"snapshots":[],"filePathMap":{}}' > "$NEW_SESSION/rewind-snapshots/index.json"
rm -rf "$NEW_SESSION/rewind-snapshots/backups"/* 2>/dev/null || true

# Reset session database (contains old session references)
rm -f "$NEW_SESSION/session.db" 2>/dev/null || true

# Reset checkpoints
cat > "$NEW_SESSION/checkpoints/index.md" << 'CKPT'
# Checkpoint History

Checkpoints are listed in chronological order. Checkpoint 1 is the oldest, higher numbers are more recent.

| # | Title | File |
|---|-------|------|
CKPT

echo "NEW_SESSION_ID=$NEW_SESSION_ID"
```

### 3. Report Success

Tell the user the **exact commands** to drop into the new session. Include the `cd` to the working directory.

**Detect CLI flags**: Before reporting, detect what flags the current session was launched with:
```bash
COPILOT_FLAGS=$(cat /proc/$PPID/cmdline 2>/dev/null | tr '\0' ' ' | grep -oP '(--yolo|--alt-screen|--model \S+)' | tr '\n' ' ' || echo "")
```

Include those flags in the resume command:

```
✅ Session branched successfully!

To start working in the new session:

    cd <cwd> && copilot --resume=<new-session-id> <detected-flags>

To return to this session later:

    cd <original-cwd> && copilot --resume=<current-session-id> <detected-flags>
```

If a worktree was created, the `cd` should point to the worktree directory instead:

```
    cd <worktree-dir> && copilot --resume=<new-session-id> <detected-flags>
```

**Important:** The session picker (`copilot --resume`) does NOT visually distinguish branches.
To identify branches later, the user can run:

```bash
grep -l 'branch_of' ~/.copilot/session-state/*/workspace.yaml | while read f; do
  echo "---"
  cat "$f"
done
```

### 4. Truncation (Only If Requested)

If user says "branch from N turns ago", truncate events.jsonl to remove the last N turns:

```bash
python3 -c "
import json, sys

turns_back = int(sys.argv[1])
lines = open('$NEW_SESSION/events.jsonl').readlines()
events = [json.loads(l.strip()) for l in lines]

# Find user.message events (each = 1 turn)
user_msgs = [(i, e) for i, e in enumerate(events) if e['type'] == 'user.message']
if turns_back >= len(user_msgs):
    print('Error: only', len(user_msgs), 'turns exist')
    sys.exit(1)

# Cut at the Nth-from-last user message
cut_idx = user_msgs[-turns_back][0]
events = events[:cut_idx]

with open('$NEW_SESSION/events.jsonl', 'w') as f:
    for e in events:
        f.write(json.dumps(e, separators=(',', ':')) + '\n')
print(f'Truncated to {len(events)} events (removed last {turns_back} turns)')
" N
```

## Notes

- Both sessions are fully independent after branching
- The original session is never modified
- Rewind/checkpoint history starts fresh in the branch
- Session database (session.db) is removed in the branch to avoid stale references
- `branch_of` and `branch_note` fields in workspace.yaml track lineage (copilot preserves these custom fields)
- The `summary` field in workspace.yaml is auto-generated by copilot and CANNOT be used for branch identification — it gets overwritten on next interaction

## Worktree Branching (Optional)

If the user says "branch into a worktree" or "branch with worktree for X", also create a git worktree so the new session works in an isolated directory:

```bash
BRANCH_NAME="donna/$FEATURE_SLUG"
WORKTREE_DIR="$HOME/proj/pal-trees/$FEATURE_SLUG"

# Create branch and worktree
git worktree add "$WORKTREE_DIR" -b "$BRANCH_NAME"

# Install dependencies in the worktree
cd "$WORKTREE_DIR/donna" && npm install

# Update the new session's cwd to point at the worktree
sed -i "s|^cwd: .*|cwd: $WORKTREE_DIR|" "$NEW_SESSION/workspace.yaml"
```

Then tell the user:
```
✅ Session branched with worktree!

Worktree: ~/proj/pal-trees/<feature>
Branch: donna/<feature>

To start working:
    cd ~/proj/pal-trees/<feature> && copilot --resume=<new-session-id>
```
