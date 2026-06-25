# Context Cartographer Adapter For Claude Code

Use this adapter only as a small persistent pointer. Keep the full workflow in the `context-cartographer` skill.

- For project documentation setup, audit, cleanup, `AGENTS.md`, `architecture.md`, docs maps, or local agent-memory docs, use `/context-cartographer` when the skill is installed.
- If the skill is not installed, ask the user to install it into `~/.claude/skills/context-cartographer/` or `.claude/skills/context-cartographer/` before doing broad documentation migration.
- Treat questions, analysis, brainstorming, and project discussion as conversation-only unless the user explicitly asks to implement, change, create, update, delete, move, fix, run, or apply something.
- Before changing existing docs, scan read-only and show the proposed docs map: current docs, topic owners, and planned create/update/delete actions.
- Before code or code-adjacent edits, read `docs/code_rules.md` when it exists.
- When root instructions define automatic durable documentation maintenance, update the relevant owner docs in the same task after deployment, staging, test-data, SSH, import/export, public URL, WordPress setup, operator-workflow, architecture, or public-interface changes. If automatic mode applies and no docs update is needed, say so in the final response.
- Keep project-memory docs local-only unless the user explicitly asks to track, publish, upload, or deploy them.
