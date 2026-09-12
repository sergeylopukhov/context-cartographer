# Context Cartographer Adapter For Claude Code

Use this adapter only as a small persistent pointer. The project's own documentation contract lives in the project; the setup workflow lives in the `context-cartographer` skill.

- For project documentation setup, audit, migration, cleanup, restructuring, or unclear ownership, use `/context-cartographer` when the skill is installed.
- In Claude Code projects, prefer `CLAUDE.md` as the root agent instruction file. Do not create `AGENTS.md` unless the user also wants Codex or multi-agent support.
- If the skill is not installed, ask the user to install it into `~/.claude/skills/context-cartographer/` or `.claude/skills/context-cartographer/` before doing broad documentation migration.
- Treat short broad prompts such as "доделай документацию" or "bring docs into shape" as a request to run the full context-cartographer workflow; do not require a long prompt.
- Do not infer documentation maintenance mode; automatic durable maintenance requires explicit user selection.
- Do not infer code-rules mode; using `docs/code_rules.md` for code and code-adjacent edits requires explicit user selection.
- For an informational question, inspect and report without changing files. When the user asks to create, save, or update an artifact, including a plan or a document, that request is the work; complete authorized in-scope local work and checks without asking again, and ask only for a missing consequential decision or before a destructive, external, costly, or scope-expanding action.
- Before changing existing docs, scan read-only and show the proposed docs map: current docs, topic owners, and planned create/update/delete actions.
- If `docs/documentation-rules.md` or `docs/architecture.md` does not exist yet, treat the project as not set up: run the setup workflow instead of inventing the local contract.
- Before changing documentation, read the [documentation rules](docs/documentation-rules.md) and follow it. It is the canonical, self-sufficient maintenance contract.
- Use the [documentation map](docs/architecture.md) to find the owner of a topic. Resolve a Markdown link relative to the file that contains it, choose the narrowest sufficient address, and link the canonical section instead of copying its text.
- Before code or code-adjacent edits, read `docs/code_rules.md` only when root instructions enable code-rules mode.
- When root instructions define automatic durable documentation maintenance, update the relevant owner docs in the same task after durable behavior, architecture, setup, deployment, staging, test-data, access, import/export, public URL, WordPress setup, data model, public interface, operator-workflow, agent workflow, or documentation-ownership changes.
- For ordinary maintenance with a known owner, the local project instructions and existing owner documents suffice; do not invoke `context-cartographer`. Perform routine documentation maintenance directly from root instructions and existing owner docs.
- If no existing owner fits and automatic durable maintenance applies, create the smallest justified owner and update the [documentation map](docs/architecture.md) directly, without asking merely for permission to create a Markdown file and without invoking the skill. Invoke the skill only for genuinely unclear ownership or a nontrivial migration or restructuring.
- After a change that affects the documentation set, check the addresses and refresh the derived graph at `.context-cartographer/documentation-graph.html` once. If the helper or the skill is unavailable, report the automatic check as not run instead of claiming a passed check.
- Keep project-memory docs and the `.context-cartographer/` graph local-only unless the user explicitly asks to track, publish, upload, or deploy them. Use precise ignore patterns instead of ignoring all of `docs/` when `docs/` is public.
- Respect nested instruction files: a closer `CLAUDE.md` or project rule governs its scope, and this adapter does not override project-specific or local rules.
