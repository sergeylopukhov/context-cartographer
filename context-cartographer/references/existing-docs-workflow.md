# Existing Documentation Workflow

Use this workflow for documentation audit, migration, cleanup, restructuring, conflicting ownership, or a durable topic that has no existing owner file.

Do not use it for a routine update when `AGENTS.md` and `docs/architecture.md` already identify the owner. Update that owner directly.

## Required Decisions

Before changing existing documentation, resolve:

- for a broad audit, migration, cleanup, or restructuring: handling strategy — keep as-is, audit only, migrate after approval, or let the agent decide;
- agent target when root instructions are being created or replaced;
- code-rules mode when root instructions do not already state it;
- documentation maintenance mode when root instructions do not already state it;
- whether local project-memory docs remain ignored or are intentionally tracked.

Generic permission to decide cleanup does not authorize choosing code-rules mode or documentation maintenance mode.

For a targeted missing-owner case, keep unrelated existing docs as-is. Do not require a general cleanup strategy; request approval only for the proposed owner file and its routing-map update.

## Required References

Read:

- `audit-checklist.md` for every audit or migration;
- `doc-map.md` to classify the project and assign topic ownership;
- `file-templates.md` before creating a root instruction file or owner document;
- `cleanup-rules.md` before splitting, merging, deleting, or renaming docs.

## Audit And Proposal

1. Resolve the project root and inventory real paths with `rg --files`.
2. Inventory root instructions, README files, docs indexes, architecture, product, design, deployment, security, API, integration, admin, content, advertising, glossary, temporary, and obsolete files.
3. Identify duplicate facts, conflicts, missing owners, stale links, oversized mixed documents, and profile-inappropriate files.
4. Show a compact proposed documentation map before edits:
   - current file;
   - topic owner;
   - planned keep, update, create, move, merge, rename, or delete action.
5. Ask before destructive or ownership-changing actions unless the user explicitly approved those exact actions or delegated the cleanup decision.

## Missing Owner Protocol

When a durable fact does not fit any existing owner:

1. Do not create a new Markdown file during routine maintenance.
2. Invoke `context-cartographer`.
3. Read `doc-map.md` and the current `docs/architecture.md`.
4. Check whether an existing owner can accept the fact without mixing responsibilities.
5. Propose a new owner only when the topic is durable, will recur, and would create noise or duplication elsewhere.
6. Ask for approval before creating the new owner; this approval is scoped to that owner and its routing entry.
7. Add the new owner to `docs/architecture.md` and update routing rules in the same task.

## Migration And Cleanup

- Preserve project-specific rules and durable unique facts.
- Move each durable fact to exactly one owner file.
- Replace repeated broad text with a link when a reminder is useful.
- Keep `docs/architecture.md` as a map.
- Keep public README, license, changelog, examples, and docs-site content in their conventional locations.
- Mark conflicting facts as `TODO: clarify` or ask; do not choose silently.
- Delete or rename only after approval and after preserving unique durable facts.
- Keep temporary plans and status outside durable owner docs.

## Maintenance Preservation

After restructuring:

- preserve the selected `automatic durable maintenance` or `request-only maintenance` mode;
- ensure routine updates use root instructions and existing owners directly;
- ensure absent or ambiguous ownership routes back to `context-cartographer`;
- ensure Codex, Claude Code, and Cursor adapters preserve the same durable-change coverage.

## Verification

- Check every newly created owner is linked from `docs/architecture.md`.
- Check old filenames and inbound references with `rg`.
- Check there are no duplicate owners for one topic.
- Check local-only files remain ignored unless tracking was explicitly requested.
- Check root instructions remain short and contain the missing-owner fallback.
- Report preserved, moved, created, renamed, and deleted files separately.
