# lossyrob-skills

Reusable [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli) skills.

## Install

```bash
copilot plugin install lossyrob/skills
```

## Skills

### session-branch

Branch the current Copilot CLI session, creating a new session that inherits conversation history up to the current point while preserving the original session intact. Useful for experimentation or parallel development without losing your place.

**Trigger phrases:** "branch", "branch session", "fork session", "create a branch from here"

**Features:**
- Copies full session state (events, workspace config)
- Tracks lineage via `branch_of` / `branch_note` in `workspace.yaml`
- Resets checkpoints and rewind snapshots for a clean slate
- Optional truncation ("branch from N turns ago")
- Optional git worktree integration

## License

MIT
