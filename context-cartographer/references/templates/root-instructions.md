# Root Instruction Templates

Thin adapters: one file per selected target. Each names the project documentation system and routes to the map and the local maintenance contract. The contract holds the detail; the adapter does not repeat it.

Rules for this file:

- Create only the adapters for the selected agent targets.
- Do not infer code-rules mode or documentation maintenance mode; resolve both before writing, then state the selected mode concretely and delete the unused variants.
- Keep the routing links real Markdown links. The documentation index resolves routes only from parsed links, so a root that only names `docs/architecture.md` in a code span leaves every owner unreachable.
- Merge with existing project rules instead of replacing the file.

## Codex: AGENTS.md

```markdown
# Project Instructions

- Agent target: Codex. Reply in the project's default language unless asked otherwise.
- Read the [documentation map](docs/architecture.md) to find a topic's owner, and the [documentation rules](docs/documentation-rules.md) before changing documentation. Documentation paths are project-root-relative; resolve the project root once instead of guessing.
- Maintenance mode: `automatic durable maintenance`. After completed work that changes durable behavior (architecture, setup, deployment, staging, test data, the data model, public interfaces, operator or agent workflow, documentation ownership), update the matching owner in the same task.
- Code-rules mode: `do not use code rules file`. Do not route to `docs/code_rules.md`.
- Routine maintenance stays local: the local project instructions and existing owner documents suffice; do not invoke `context-cartographer` for a known owner.
- Invoke `context-cartographer` only for first-time setup, a nontrivial migration or restructuring, genuinely unclear ownership, or an explicit request.
- Treat a question as read-only information; when the user asks to create, save, or update an artifact, including a plan or a document, do that work in the requested scope without re-asking.
- Documentation is local-only: do not commit, publish, or deploy `docs/` unless the user asks.
```

## Claude Code: CLAUDE.md

```markdown
# Project Instructions

- Agent target: Claude Code. Reply in the project's default language unless asked otherwise.
- Read the [documentation map](docs/architecture.md) to find a topic's owner, and the [documentation rules](docs/documentation-rules.md) before changing documentation. Documentation paths are project-root-relative; resolve the project root once instead of guessing.
- Maintenance mode: `automatic durable maintenance`. After completed work that changes durable behavior (architecture, setup, deployment, staging, test data, the data model, public interfaces, operator or agent workflow, documentation ownership), update the matching owner in the same task.
- Code-rules mode: `do not use code rules file`. Do not route to `docs/code_rules.md`.
- Routine maintenance stays local: the local project instructions and existing owner documents suffice; do not invoke `context-cartographer` for a known owner.
- Invoke `context-cartographer` only for first-time setup, a nontrivial migration or restructuring, genuinely unclear ownership, or an explicit request.
- Treat a question as read-only information; when the user asks to create, save, or update an artifact, including a plan or a document, do that work in the requested scope without re-asking.
- Documentation is local-only: do not commit, publish, or deploy `docs/` unless the user asks.
```

## Cursor: .cursor/rules/context-cartographer.mdc

A Cursor rule needs real frontmatter before the body, and `alwaysApply: true` keeps the router active for every request. The file sits in `.cursor/rules/`, so its links are relative to that folder and point at `../../docs/`.

```markdown
---
description: Project documentation routing
alwaysApply: true
---
# Project Instructions

- Agent target: Cursor. Reply in the project's default language unless asked otherwise.
- Read the [documentation map](../../docs/architecture.md) to find a topic's owner, and the [documentation rules](../../docs/documentation-rules.md) before changing documentation. Documentation paths are project-root-relative; resolve the project root once instead of guessing.
- Maintenance mode: `automatic durable maintenance`. After completed work that changes durable behavior (architecture, setup, deployment, staging, test data, the data model, public interfaces, operator or agent workflow, documentation ownership), update the matching owner in the same task.
- Code-rules mode: `do not use code rules file`. Do not route to `docs/code_rules.md`.
- Routine maintenance stays local: the local project instructions and existing owner documents suffice; do not invoke `context-cartographer` for a known owner.
- Invoke `context-cartographer` only for first-time setup, a nontrivial migration or restructuring, genuinely unclear ownership, or an explicit request.
- Treat a question as read-only information; when the user asks to create, save, or update an artifact, including a plan or a document, do that work in the requested scope without re-asking.
- Documentation is local-only: do not commit, publish, or deploy `docs/` unless the user asks.
```

## Mode Variants

Write exactly one maintenance bullet. When the selected mode is `request-only maintenance`, replace the maintenance bullet in every adapter with:

```markdown
- Maintenance mode: `request-only maintenance`. Do not change documentation without an explicit request; if a change likely makes docs stale, report that instead of editing.
```

When code-rules mode is `use code rules file`, replace the code-rules bullet with:

```markdown
- Code-rules mode: `use code rules file`. Read `docs/code_rules.md` before changing code or code-adjacent files.
```

## Merge Rules

- Keep an existing agent-specific rule that still applies; add the missing routing lines instead of overwriting the file.
- For Cursor, generate `.cursor/rules/context-cartographer.mdc`. Keep a legacy `.cursorrules` only when the project already has it, and update that file in place instead of adding a second Cursor rule source.
- A nested instruction file governs its own scope; these root adapters do not override it.
- Register every created owner in the map. The adapter routes to the map, not to an unlisted file.
