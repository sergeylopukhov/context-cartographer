---
name: context-cartographer
description: Create or rebuild agent-facing project documentation systems and root instruction routers such as AGENTS.md, CLAUDE.md, Cursor rules, and docs/architecture.md; audit or migrate an existing docs set; resolve duplicated, stale, or unclear documentation ownership; or redesign a documentation map. Use for first-time setup, broad requests to bring project docs into shape, structural cleanup or migration, and explicit context-cartographer requests. Do not use for routine edits to known existing documentation files or automatic durable documentation maintenance already governed by project root instructions; perform those directly.
---

# Context Cartographer

Build a small documentation system that lets future agents load only the context they need.

## Scope Boundary

- Use this skill for documentation-system setup, audit, migration, cleanup, restructuring, or unclear ownership.
- Do not use it for a routine edit when the target owner file is already known.
- Do not use it for automatic durable maintenance already required by `AGENTS.md`, `CLAUDE.md`, Cursor rules, `docs/architecture.md`, or `docs/code_rules.md`. Apply those local instructions directly.
- Always use it when the user explicitly invokes `context-cartographer`.

## Core Rules

- Resolve the project root and inventory real paths before reading project files. Do not guess paths from the current directory or another project.
- Reuse files already read during the task. Reread only a changed file, truncated output, or a specific unread range.
- Keep root agent instruction files short. Put durable topic detail in owner files under `docs/`.
- Use `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, `.cursor/rules/context-cartographer.mdc` for Cursor, or thin adapters for selected multi-agent targets.
- Inspect read-only before proposing changes.
- Preserve existing project-specific rules and edit surgically.
- Never overwrite, move, merge, or delete existing instruction or docs files without approval.
- Create only files supported by project evidence and current needs.
- Mark unknown facts as `TODO: clarify`; never invent project facts.
- Keep project-memory docs local-only by default and add them to the repository ignore file unless the user explicitly asks to track or publish them.
- Verify links, owner routing, ignore rules, and stale references after edits.

## Required Decisions

Before creating or replacing root agent instructions, resolve:

- agent target;
- code-rules mode: use `docs/code_rules.md` or do not use it;
- documentation maintenance mode: `automatic durable maintenance` or `request-only maintenance`;
- handling of existing docs: keep as-is, audit only, migrate after approval, or let the agent decide;
- whether project-memory docs remain local-only or are tracked.

Do not infer code-rules mode or documentation maintenance mode. When more than two decisions are missing, use the bundled questionnaire.

Generated root instructions must keep routine maintenance independent from this skill:

- Under `automatic durable maintenance`, update the matching owner doc in the same task whenever completed work changes durable behavior, architecture, setup, deployment, staging, test data, access, import/export, public URLs, operator workflow, data model, public interfaces, agent workflow, or documentation ownership.
- Under `request-only maintenance`, update docs only when explicitly asked and flag likely stale docs.
- State that routine maintenance uses root instructions and existing owner docs directly without invoking `context-cartographer`.
- If no existing owner file fits, do not create a new Markdown file during routine maintenance. Invoke this skill and follow the missing-owner protocol.
- Invoke this skill later only for setup, audit, migration, cleanup, restructuring, explicit use, or genuinely unclear ownership.

## Reference Routing

- For first-time setup, always read `references/setup-workflow.md`; it routes the other required references.
- For audit, migration, cleanup, restructuring, or unclear ownership, always read `references/existing-docs-workflow.md`; it routes the other required references.
- Read `references/doc-map.md` before choosing files or ownership.
- Read `references/file-templates.md` before creating root instructions or `docs/*.md`.
- Read `references/audit-checklist.md` before auditing an existing repository.
- Read `references/cleanup-rules.md` before splitting, merging, deleting, or renaming docs.
- Read `references/question_schema.md` before creating questionnaire JSON.
- Read `references/questionnaire_usage_examples.md` only when adapting the questionnaire flow.

## Workflow

1. Resolve the project root and inventory paths with `rg --files`.
2. Classify the project profile, selected agent target, existing docs, ownership, code-rules mode, and maintenance mode.
3. For existing docs, show a compact map of current files, topic owners, and planned create/update/delete actions before editing.
4. Apply the smallest approved documentation-system change.
5. Verify links, stale filenames, owner coverage, local-only ignore rules, and the independent routine-maintenance instructions.

For a new system, follow `references/setup-workflow.md`.

For audit, cleanup, migration, restructuring, or unclear ownership, follow `references/existing-docs-workflow.md`.

## Questionnaire

For broad setup work with more than two missing decisions:

1. Create `.project-questionnaire/questions.json` from `references/question_schema.md`.
2. Set `language` to the user or project language.
3. Validate with `python3 <this-skill>/scripts/questionnaire_server.py --input .project-questionnaire/questions.json --validate-only`.
4. Run the server on `127.0.0.1` with an automatic port.
5. After the user saves and says they are done, read both answer files before continuing.

Code-rules mode and documentation maintenance mode must be required choices without defaults or recommendation options.

## Update Check

Run `python3 <this-skill>/scripts/check_update.py --json` at most once per day. Ask before installing an available update. Bump `VERSION` when publishing a change that installed users should receive.

## Exit Criteria

Report:

- files created or changed;
- links, routing, and stale references checked;
- local-only ignore policy checked;
- independent automatic-maintenance routing checked;
- validation performed and any checks not run.
