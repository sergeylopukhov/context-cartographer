# File Templates

Router for the compact project-documentation templates. Read this file before creating or updating root instructions or any `docs/*.md`, then open only the template files the task needs.

Resolve both code-rules mode and documentation maintenance mode before writing generated files. Do not infer either mode.

Generate project facts and project-root-relative addresses, not a copy of this skill's text. Mark unknown durable facts as `TODO: clarify`, and do not leave a mode placeholder in written output.

## Template Files

| Read this template | When | It produces |
| --- | --- | --- |
| [templates/root-instructions.md](templates/root-instructions.md) | Creating or updating a root agent instruction file | Thin `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/context-cartographer.mdc` routers |
| [templates/documentation-map.md](templates/documentation-map.md) | Creating or updating the documentation map | `docs/architecture.md` with its scope table, topic table, and dependency table |
| [templates/documentation-rules.md](templates/documentation-rules.md) | Installing the self-sufficient maintenance contract | `docs/documentation-rules.md` |
| [templates/core-docs.md](templates/core-docs.md) | Creating the minimal core owners | `docs/architecture-overview.md`, `docs/architecture-quality-risks.md` |
| [templates/profile-docs.md](templates/profile-docs.md) | The project profile needs extra owners | `docs/architecture-frontend.md`, `docs/DEPLOYMENT.md`, and other profile or conditional owners |
| [templates/code-rules.md](templates/code-rules.md) | Code-rules mode is enabled | `docs/code_rules.md` |
| [templates/idea-docs.md](templates/idea-docs.md) | An idea, brief, or plan is being written before a full documentation system exists | A stage-appropriate brief or `docs/implementation-plan.md` |

Read `references/documentation-format.md` before writing the map. It is the format contract for the scope table, the topic table, and addresses; this router never overrides it.

Read `references/doc-map.md` to choose the profile and the owner set, and `references/documentation-graph.md` before running or describing the documentation helper.

The minimal core belongs to a project that actually needs a documentation system. For an idea or a lone brief, use [templates/idea-docs.md](templates/idea-docs.md) instead of the core templates, and do not attach the map or the graph.

## Local-Only Files

Project-memory documentation is local-only by default. Ignore the private documentation directory and the derived graph directory `.context-cartographer/` with precise patterns; do not ignore all of `docs/` when `docs/` is a public site or user-facing content folder. The exact policy lives in the generated `docs/documentation-rules.md`.

## Routing Rules

- Create a root adapter only for a selected agent target.
- Every created owner must be registered in `docs/architecture.md` with a real Markdown link in its `Owner` cell.
- Every generated root adapter routes to `docs/architecture.md` and `docs/documentation-rules.md` with real Markdown links, states one concrete mode, and does not repeat the contract.
- A profile file is created only when repository evidence or explicit user intent supports it.
