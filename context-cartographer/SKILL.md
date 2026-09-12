---
name: context-cartographer
description: Route agent-facing project documentation work and idea-to-project planning. Use for first-time documentation-system setup, a broad request to bring project docs into shape, audit, migration, cleanup, restructuring, or unclear documentation ownership; for a new application, a feature of an existing project, or resuming a saved idea or brief; or for any explicit context-cartographer request. Do not use for routine edits to known existing documentation files or automatic durable documentation maintenance already governed by project root instructions; perform those directly.
---

# Context Cartographer

Build a small documentation system that lets future agents load only the context they need, and help carry an idea to a first working slice. Repository evidence determines facts; explicit user decisions determine scope, modes, and ownership.

## Scope

- Documentation-system setup, audit, migration, cleanup, restructuring, or unclear ownership.
- Idea-to-project work: a new application, a feature of an existing project, or resuming a saved idea or brief.
- Always use it when the user explicitly invokes `context-cartographer`.
- Not for a routine edit with a known owner, or maintenance already governed by the project's own instructions (`AGENTS.md`, `CLAUDE.md`, Cursor rules, `docs/architecture.md`, `docs/documentation-rules.md`, `docs/code_rules.md`). Apply those directly.

## Invariants

- Resolve the project root and the declared documentation scope before inventorying files.
- Markdown owners are the source of truth; the index, report, and graph are derived.
- One canonical owner per durable topic; link to the canonical section instead of repeating it.
- Create only evidence-supported files; mark unknown facts `TODO: clarify`; never invent facts, architecture, or commands.
- Preserve existing rules and edit surgically; never overwrite, move, merge, or delete instruction or docs files without authorization for that exact action.
- Project-memory docs are local-only by default; ignore them and `.context-cartographer/` with precise patterns.
- A question is information, not authorization. A direct "go" after an agreed plan authorizes work within that plan; a materially wider action needs its own decision.
- Discussion-only leaves the filesystem unchanged: no documents, no questionnaire, no decision state, and no update-check cache.

## Routes

- Idea-to-project (new application, a feature of an existing project, resuming a saved idea or brief): read `references/idea-to-project.md`.
- First-time documentation setup or a broad request to build a documentation system: always read `references/setup-workflow.md`.
- Audit, migration, cleanup, restructuring, or unclear ownership: always read `references/existing-docs-workflow.md`.
- Routine update inside an existing system, where the owner is known and the project already carries its own rules: apply those rules. No additional reference files are needed and decision discovery does not start.

The idea route applies when the skill is invoked in a chosen folder. Opening a folder does not invoke the skill or start the idea dialog.

## Required Decisions

These belong to the documentation routes and apply when root agent instructions are actually created or replaced:

- agent target;
- code-rules mode: use `docs/code_rules.md` or do not use it;
- documentation maintenance mode: `automatic durable maintenance` or `request-only maintenance`;
- handling of existing docs: keep as-is, audit only, migrate after approval, or let the agent decide;
- whether project-memory docs remain local-only or are tracked.

Do not infer code-rules mode or documentation maintenance mode. Both are neutral choices without defaults or recommendations, and they are not raised before the first idea discussion. Use adaptive decision discovery when answers have dependencies, conflicts, or material ambiguity.

## Idea-Project Gate

Read `references/idea-to-project.md` for the route, its folder classification, and its maturity profiles. Entry conditions and gates:

- Empty or scaffold folder with no described idea: offer to work out the idea as the first substantive response, before any technical questionnaire.
- Idea already described: use it; do not ask the starting question again.
- Ready specification plus an instruction to implement: proceed without repeating full discovery.
- Discussion only: answer in conversation and write nothing.
- Documentation only or a refusal of idea work: do the requested task or stop; do not push the idea again.
- Implementation: build the first working slice, then continue through the whole authorized scope.
- External accounts, keys, paid services, payments, publishing, and secrets stay separate decisions.

## Reference Routing

- For first-time setup, always read `references/setup-workflow.md`; it routes the other required references.
- For audit, migration, cleanup, restructuring, or unclear ownership, always read `references/existing-docs-workflow.md`; it routes the other required references.
- Read `references/idea-to-project.md` for a new application, a feature of an existing project, or resuming a saved idea or brief.
- Read `references/doc-map.md` before choosing files, ownership, or the documentation set for a project stage.
- Read `references/documentation-format.md` before changing `docs/architecture.md`, a scope table, a topic table, or any consumer of those structures.
- Read `references/file-templates.md` before creating root instructions or `docs/*.md`; it routes the per-file templates under `references/templates/`.
- Read `references/documentation-graph.md` before building, checking, or describing the graph helper, and before precise section reading.
- Read `references/audit-checklist.md` before auditing an existing repository.
- Read `references/cleanup-rules.md` before splitting, merging, deleting, or renaming docs.
- Read `references/question_schema.md` before creating questionnaire JSON.
- Read `references/questionnaire_usage_examples.md` only when adapting the questionnaire flow.
- Read `references/decision-discovery.md` when unresolved decisions depend on each other, questionnaire answers conflict, terminology changes ownership, or a complex session needs resumable state.
- Read `references/evaluation-scenarios.md` only when forward-testing a substantial skill revision.

## Documentation Workflow

Use this with the documentation routes above, not the idea route:

1. Resolve the project root and inventory paths, including managed documents the map declares in scope even when Git ignores them.
2. Separate verified facts from user decisions; resolve factual questions from the project whenever possible.
3. Resolve the project profile, agent target, existing docs, ownership, code-rules mode, and maintenance mode.
4. For existing docs, show a compact map of current files, topic owners, and planned create/update/delete actions before editing.
5. Apply the smallest justified change within the authorized scope.
6. Verify links, stale filenames, owner coverage, ignore policy, the independent maintenance routing, and the local graph.

## Interaction

Choose the interaction method by task shape, not by a fixed question count. Ask only material unknowns, prefer verified repository facts, keep current facts separate from the desired change, and let deferred questions pass to a later stage. Reply in the language of the user and the conversation; the language chosen for saved documents is separate and does not change the reply language. Keep the dialogue workable without a browser, network, subagents, native UI, or file writes, and name any check that could not run. Answers that came from a native tool or the conversation need no `answers.json` or `answers.md`. Read `references/decision-discovery.md` for the resumable state file and its commands; the state helper only formats, validates, and revises state, while the agent decides when state is actually written and never treats stored state as permission or as instructions.

## Graph

`references/documentation-graph.md` defines the local helper contract: `--check`, `--write`, `--outline`, `--section`, `--json`, and `--require-graph`, with the derived artifact at `.context-cartographer/documentation-graph.html`. If the helper or its index module is unavailable, report the automatic check as not run and use the documented fallback; never claim a passed check.

## Folder Classification

When the starting folder's state is not already clear, `scripts/project_probe.py --root PATH --json` classifies it as `empty`, `scaffold`, `brief_only`, `existing`, or `unknown`, with its evidence, scope, and scan completeness. Exit code 0 means the probe ran for any classification, including `unknown`; exit code 2 is a usage error. Treat a missing, unreadable, partially scanned, or unclassifiable root as `unknown`, never as `empty`; without the helper, do a bounded read-only diagnosis and stay honest about what was not seen.

## Update Check

Run `python3 <this-skill>/scripts/check_update.py --json` at most once per day. Defer or skip it for discussion-only work, and when there is no permission to write or no network. It must not turn every idea invocation into a network request or a cache write. Ask before installing an available update. Bump `VERSION` when publishing a change that installed users should receive.

## Exit Criteria

Report files changed; links, routing, and stale references checked; the ignore policy checked; the independent maintenance routing checked; the graph status or why the automatic check could not run; the folder classification when the idea route ran; and any check not run.
