# Documentation Map Template

Create or update `docs/architecture.md` from the block below. The format contract is `references/documentation-format.md`; this template follows it and never overrides it.

The block is a complete, runnable minimal map for the core documentation set. Replace the `TODO` values with project facts, keep only the root rows whose file exists, and delete a section only when it has no owner. An empty dependency table is valid.

Every owner must be a real Markdown link, because the index resolves the graph from parsed links. A path written only as a code span creates an unreachable owner.

```markdown
# Architecture Map

<!-- context-cartographer: format_version=1 -->

This file is the map, not the full architecture record. Read it when a task affects structure, behavior, routes, models, services, tests, deployment, durable rules, or documentation organization.

## Project Profile

- Profile: TODO: clarify
- Stack: TODO: clarify

## Scope

The scope table is the only editable definition of the roots and areas the documentation tools scan. Keep a root row only when that file exists.

| Kind | Path | Notes |
| --- | --- | --- |
| root | `AGENTS.md` | Codex root instruction router |
| root | `CLAUDE.md` | Claude Code root instruction router |
| root | `.cursor/rules/context-cartographer.mdc` | Cursor root rule |
| include | `docs/` | documentation area |
| exclude | `.context-cartographer/` | derived local graph |

## Core Docs

- [Documentation Rules](documentation-rules.md): the maintenance contract for this documentation set.
- [Architecture Overview](architecture-overview.md): stack, repository layout, system boundaries.
- [Quality And Risks](architecture-quality-risks.md): verification commands, known risks, technical debt.

## Profile Docs

Add a link and a topic row only for a profile or conditional owner that exists.

## Topic Map

| Topic ID | Purpose | Owner | Read when |
| --- | --- | --- | --- |
| docs.maintenance | Create, update, link, and check documentation | [Documentation Rules](documentation-rules.md) | Creating, changing, moving, or checking documentation |
| architecture.overview | Stack, layout, and system boundaries | [Architecture Overview](architecture-overview.md) | Changing structure, layout, or boundaries |
| quality.risks | Verification commands and known risks | [Quality And Risks](architecture-quality-risks.md) | Changing tests, verification, or risky areas |

Owner links resolve relative to this file, so `documentation-rules.md` means `docs/documentation-rules.md`. Use an explicit stable anchor when a heading is unstable or ambiguous.

## Explicit Dependencies

Add a row only for a real prerequisite between declared topics. An empty table is valid; do not invent a dependency target.

| Topic ID | Depends on | Reason |
| --- | --- | --- |

## Local-Only Policy

- Treat project-memory documentation as local-only by default.
- Keep the root instruction files, `docs/`, `.project-questionnaire/`, and the graph directory `.context-cartographer/` in the repository ignore file unless the user explicitly wants the docs tracked.
- If `docs/` is a public site, package documentation, or user-facing content folder, do not ignore all of `docs/`; use precise patterns for the private files.

## Update Rules

- Write a durable fact only to the most specific owner.
- Agent target: TODO: replace with the selected targets.
- Code-rules mode: TODO: replace with `use code rules file` or `do not use code rules file`.
- Documentation maintenance mode: TODO: replace with `automatic durable maintenance` or `request-only maintenance`.
- For ordinary maintenance with a known owner, the local rules and existing owner documents suffice; do not invoke `context-cartographer`.
```

## Optional Rows

Add these only when the project truly has them. They are examples of shape, not rows to ship.

### When Code-Rules Mode Is Enabled

Create `docs/code_rules.md` and add both of these to the generated map, so the parser has a real owner link for it:

```markdown
- [Code Rules](code_rules.md): code-editing rules for this project.
```

```markdown
| code.rules | Code-editing rules | [Code Rules](code_rules.md) | Changing code or code-adjacent files |
```

When code-rules mode is declined, do not add the file, the link, or the row.

```markdown
| Topic ID | Purpose | Owner | Read when |
| --- | --- | --- | --- |
| deployment.release | Build, deploy, and roll back a release | [Deployment](DEPLOYMENT.md#release) | Changing the release flow |
```

```markdown
| Topic ID | Depends on | Reason |
| --- | --- | --- |
| deployment.release | deployment.backup | A rollback needs a restore point |
```

Before adding an optional dependency, confirm that both `Topic ID` values are declared in the topic table and that the owner file exists.

## Notes For The Skill

- Keep the `format_version` marker line at the top of the generated map.
- Keep the map short: it routes to owners instead of containing their detail.
- Fill every `TODO` before writing; a generated map that keeps a mode placeholder is not finished.
