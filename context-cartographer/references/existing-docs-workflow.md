# Existing Documentation Workflow

Use this workflow for documentation audit, migration, cleanup, restructuring, conflicting ownership, or a genuinely unclear owner.

Do not use it for a routine update when `AGENTS.md`, `docs/architecture.md`, and `docs/documentation-rules.md` already identify the owner. Update that owner directly.

Folder classification does not replace the user's requested operation. If the user explicitly asks to audit, review, validate, migrate, clean up, or restructure requirements or documentation, stay on this workflow even when the folder is `brief_only`. Route a `brief_only` folder to `idea-to-project.md` only when the request is to develop or implement the idea, or when no explicit documentation-review intent controls the task. A feature of an existing project updates the existing owners and creates a new owner only for a new durable topic.

## Required Decisions

Before changing existing documentation, resolve:

- for a broad audit, migration, cleanup, or restructuring: handling strategy - keep as-is, audit only, migrate after approval, or let the agent decide;
- agent target when root instructions are being created or replaced;
- code-rules mode when root instructions do not already state it;
- documentation maintenance mode when root instructions do not already state it;
- whether local project-memory docs remain ignored or are intentionally tracked.

Generic permission to decide cleanup does not authorize choosing code-rules mode or documentation maintenance mode.

Resolve a single blocking decision directly. For several independent decisions, use an available native structured-input tool or the bundled questionnaire. Read `decision-discovery.md` when choices depend on one another, evidence conflicts, terminology is ambiguous, or the session needs resumable state.

For a targeted missing-owner case, keep unrelated existing docs as-is. Do not require a general cleanup strategy or ask for approval to create the owner file and its routing-map entry.

## Required References

Read:

- `audit-checklist.md` for every audit or migration;
- `doc-map.md` to classify the project and assign topic ownership;
- `documentation-format.md` before changing the map, its scope table, or its topic table;
- `file-templates.md` before creating a root instruction file or owner document, then open only the templates it routes to;
- `documentation-graph.md` before checking addresses, reading a precise section, or refreshing the graph;
- `cleanup-rules.md` before splitting, merging, deleting, or renaming docs;
- `decision-discovery.md` when the audit exposes dependent decisions, material contradictions, or unresolved terminology.

## Audit And Proposal

1. Resolve the project root and inventory real paths with `rg --files` or an equivalent repository inventory, including managed documents that Git ignores but the map declares as in scope. If safe delegation is available, parallelize only clearly independent read-only inventories and keep final ownership decisions in the primary agent.
2. Inventory root instructions, README files, docs indexes, architecture, product, design, deployment, security, API, integration, admin, content, advertising, glossary, temporary, and obsolete files.
3. Identify duplicate facts, conflicts, missing owners, stale links, oversized mixed documents, and profile-inappropriate files.
4. Run the documentation check read-only to collect address, owner, and reachability problems before proposing edits.
5. Show a compact proposed documentation map before edits:
   - current file;
   - topic owner;
   - planned keep, update, create, move, merge, rename, or delete action.
6. Ask before destructive actions unless the user explicitly approved those exact actions or delegated the cleanup decision. Creating a justified missing owner and adding its routing entry is not a destructive action and requires no question.

## Missing Owner Protocol

When a durable fact does not fit any existing owner:

1. Create a new owner file during routine maintenance only for a durable topic that no existing owner can hold.
2. If the topic is temporary, one-off, or belongs in an existing owner, place it there instead of creating a file.
3. Invoke `context-cartographer` when ownership is genuinely unclear, not for an obvious new owner, and also when the map itself needs a broader restructuring or migration.
4. Read `doc-map.md` and the current `docs/architecture.md` before choosing the owner.
5. Check whether an existing owner can accept the fact without mixing responsibilities.
6. Propose a new owner only when the topic is durable, will recur, and would create noise or duplication elsewhere.
7. Under automatic durable maintenance, create the smallest justified owner automatically without asking for approval.
8. Add the new owner to `docs/architecture.md` and update routing rules in the same task.
9. Do not ask a question merely because a new Markdown file is needed. If some facts remain uncertain, use `TODO: clarify` without blocking automatic maintenance.

## Link And Rename Rules

- Resolve a Markdown link relative to the file that contains it, and replace repeated durable text with a link to the canonical section when a reminder is useful.
- Keep root routes and topic `Owner` cells as real Markdown links. The index resolves the graph only from parsed links; a path in a code span does not create a route.
- Before renaming a file or heading, find the incoming links from the documentation index or with a repository search, and fix the affected addresses in the same authorized change.
- Do not replace matching text across the whole project. When external documents use the old address, keep the previous explicit anchor when possible, or describe the migration.
- Take `depends_on` only from the explicit dependency table. Ordinary link cycles are allowed and reported as information.

## Migration And Cleanup

- Preserve project-specific rules and durable unique facts.
- Move each durable fact to exactly one owner file.
- Keep `docs/architecture.md` as a map and keep the maintenance contract in `docs/documentation-rules.md`.
- Keep public README, license, changelog, examples, and docs-site content in their conventional locations.
- Mark conflicting facts as `TODO: clarify` or ask; do not choose silently.
- Delete or rename only after approval and after preserving unique durable facts.
- Keep temporary plans and status outside durable owner docs.
- Preserve the selected language, privacy policy, and existing agent adapters, or migrate them explicitly.

## Maintenance Preservation

After restructuring:

- preserve the selected `automatic durable maintenance` or `request-only maintenance` mode;
- ensure routine updates use the local rules and existing owners directly, without invoking `context-cartographer`;
- ensure an obvious new owner is created from the local rules, and only genuinely unclear or conflicting ownership routes back to `context-cartographer`;
- ensure Codex, Claude Code, and Cursor adapters preserve the same durable-change coverage;
- refresh the graph once after the agreed set of structure changes.

## Verification

- Check every newly created owner is linked from `docs/architecture.md`.
- Check each root adapter links to the map and the maintenance contract with parsed links and states one concrete mode.
- Check old filenames and inbound references with `rg`.
- Check there are no duplicate owners for one topic.
- Check local-only files and `.context-cartographer/` remain ignored unless tracking was explicitly requested.
- Check root instructions remain short and contain the missing-owner fallback.
- Report preserved, moved, created, renamed, and deleted files separately.
