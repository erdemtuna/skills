# skills

Reusable [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli) skills. Forked from [lossyrob/skills](https://github.com/lossyrob/skills).

## Install

```bash
copilot plugin install erdemtuna/skills
```

## Skills

| Skill | Description | Triggers | Requirements |
|-------|-------------|----------|--------------|
| [**code-review**](skills/code-review/SKILL.md) | Reviews code against 7 quality dimensions: type safety, DRY, clean code, SOLID, error handling, injection vulnerabilities, and performance. Outputs structured findings with severity levels (🔴 Must Fix · 🟡 Should Fix · 🔵 Consider). | `review code`, `check my PR`, `code quality`, `is this code good?` | — |
| [**session-branch**](skills/session-branch/SKILL.md) | Branch the current session, creating a new one that inherits conversation history while preserving the original. Supports optional truncation and git worktree integration. | `branch`, `branch session`, `fork session` | — |
| [**odt-convert**](skills/odt-convert/SKILL.md) | Convert ODT files to Markdown with comment extraction, inline images, and Visio diagram support. | `convert odt`, `odt to markdown`, working with `.odt` files | `pandoc`, Python 3 |

## License

MIT
