# .claude/

Per-project configuration for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview), Anthropic's CLI coding agent. Tracked in git so collaborators (and future maintainers) inherit the same automation hooks, MCP server declarations, and slash-command permissions when working inside this repo.

## Contents

- `settings.json` — project-scoped Claude Code settings: lifecycle hooks (`SessionStart`, `PreCompact`, etc.), MCP server configs, permission defaults. Currently empty; populate only with hooks that should run for every contributor.

User-specific Claude preferences (model choice, theme, keybindings) live in `~/.claude/` and are never committed here.