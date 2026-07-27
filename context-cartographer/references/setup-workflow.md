# New Documentation System Workflow

Use this workflow for first-time documentation setup or a broad request to create a complete agent-facing documentation system.

## Required Inputs

Resolve these decisions before writing root instructions or project-memory docs:

- agent target: Codex, Claude Code, Cursor, or selected multi-agent targets;
- code-rules mode: use `docs/code_rules.md` or do not use it;
- documentation maintenance mode: `automatic durable maintenance` or `request-only maintenance`;
- project profile and primary workflow;
- language policy;
- whether project-memory docs remain local-only or are tracked;
- any profile-specific needs such as deployment, admin, security, API, integrations, content, product, or design.

Do not infer code-rules mode or documentation maintenance mode. Both are blocking decisions without defaults.

If more than two decisions are missing, use the bundled questionnaire from `question_schema.md`. Match the questionnaire language to the user or project language.

## Read-Only Discovery

1. Resolve the project root.
2. Run `rg --files` from that root.
3. Ignore dependency, cache, generated, vendor, and build directories unless they are directly relevant.
4. Identify the stack, entry points, project profile, public interfaces, deployment or release flow, security-sensitive areas, integrations, and operator workflows.
5. Inventory existing `AGENTS.md`, `CLAUDE.md`, Cursor rules, README files, docs, ignore rules, and public documentation.
6. Reuse files already read during the task. Reread only changed files, truncated output, or a specific unread range.

If any existing instruction or documentation files are present, do not silently replace them. Resolve whether to keep them, audit only, migrate after approval, or let the agent decide.

## Required References

Read:

- `doc-map.md` to choose the minimal core, project profile, topic owners, and conditional files;
- `file-templates.md` before creating root instructions or any `docs/*.md`;
- `question_schema.md` when a questionnaire is required.

Read profile-specific source files from the project before documenting them. Mark unknown durable facts as `TODO: clarify`.

## Creation Sequence

1. Create or surgically update only the root instruction files selected for the target agents.
2. Create `docs/architecture.md` as a concise documentation map, not a full handbook.
3. Create the minimal core from `doc-map.md`.
4. Create `docs/code_rules.md` only when code-rules mode is enabled.
5. Add only profile and conditional files supported by repository evidence or explicit user intent.
6. Link every created owner document from `docs/architecture.md`.
7. Encode the selected agent target, code-rules mode, and documentation maintenance mode in the root instructions and architecture map.
8. Under `automatic durable maintenance`, require later tasks to update the existing owner document directly in the same task when durable project knowledge changes.
9. Require later agents to invoke `context-cartographer` before creating a new owner document when no existing owner fits.
10. Add local project-memory files to the repository ignore rules unless the user explicitly wants them tracked.

## Quality Gates

Before finishing:

- confirm every durable topic has exactly one owner;
- confirm root instructions are short routers;
- confirm `docs/architecture.md` links every created owner;
- confirm no profile file was created without evidence;
- confirm automatic maintenance works from root instructions without loading the skill;
- confirm missing ownership routes back to `context-cartographer`;
- confirm unknowns are marked rather than invented;
- confirm local-only files are ignored;
- check stale filenames and broken links with `rg`;
- report files created, decisions applied, verification performed, and unresolved TODOs.
