# Audit Checklist

Use this checklist before changing existing project documentation.

## Repository Scan

- Resolve and record the project root before constructing any project file path.
- Run `rg --files` from the project root.
- Read the scope table in `docs/architecture.md` when it exists. It defines the roots, included areas, and excluded areas that the documentation tools scan.
- Include managed documentation that Git ignores but the map declares as in scope; do not treat `rg --files` as the complete inventory for a project with a declared scope.
- Use paths from that inventory instead of guessing paths from the current directory or another project.
- Reuse files already read during the current task; reread only a changed file, truncated output, or a specific unread range.
- Identify the project profile: UI app/site/SaaS, backend/API, bot/automation, library/package, content/SEO, ecommerce/payments, data/ML, infra/devops, mobile, internal tool, or mixed project.
- Identify the stack from package files, framework files, config files, and folder names.
- Find existing project instructions: `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.cursor/`, `.cursorrules`, README files, or docs indexes.
- Find docs folders and Markdown files outside docs.
- Find VCS ignore files such as `.gitignore`, `.git/info/exclude`, or tool-specific ignore files.
- Ignore vendor, dependency, cache, build, and generated folders unless the user asks about them.

## Documentation Inventory

Classify each durable Markdown file:

- agent router
- architecture map
- architecture topic
- product
- design
- deployment/operations
- security
- API
- integrations
- admin/backoffice
- content/SEO
- advertising
- glossary
- temporary plan/status
- obsolete or generated artifact

Treat `docs/architecture.md` as the map and `docs/documentation-rules.md` as the maintenance contract. Both are durable owners; neither is a temporary plan.

## Quality Checks

- Is each selected root agent instruction file short enough to act as a router?
- Does the selected target match the file: `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, `.cursor/rules/context-cartographer.mdc` for Cursor, or multiple thin adapters for multi-agent use?
- Does each selected root agent instruction file distinguish conversation-only requests from explicit edit/implementation requests?
- Does each selected root agent instruction file require resolving project-root-relative paths before reads and prevent unnecessary full-file rereads during one task?
- Does each selected root agent instruction file state the selected code-rules mode?
- Does each selected root agent instruction file keep routine and automatic durable documentation maintenance independent from `context-cartographer`?
- Does each selected root agent instruction file limit later `context-cartographer` use to setup, audit, migration, cleanup, restructuring, explicit use, or unclear ownership?
- Does each selected root agent instruction file stay thin, routing to `docs/architecture.md` and `docs/documentation-rules.md` instead of copying their content?
- Does each selected root agent instruction file reach the map and the maintenance contract through real Markdown links, not code spans, and state one concrete maintenance mode?
- Does each selected root agent instruction file allow an obvious new owner to be created from the local rules and route genuinely unclear ownership to `context-cartographer`?
- Does `docs/documentation-rules.md` exist for a documentation system, carry its `format_version` marker, and describe owner creation, link rules, section reading, checks, and privacy?
- Does `docs/architecture.md` include the `format_version` marker, a scope table of real roots and areas, a topic table, and an explicit dependency table?
- Are the topic `Owner` cells real Markdown links, and does the scope table list only roots and areas that exist?
- Are Markdown links resolved relative to the file that contains them, and is the narrowest sufficient address used?
- Is `.context-cartographer/` ignored with a precise pattern, and is `docs/` not ignored broadly when `docs/` is a public site or user-facing content folder?
- Can the documentation check run, and are remaining errors reported instead of claimed clean?
- If code-rules mode is enabled, does each selected root agent instruction file require reading `docs/code_rules.md` before code and code-adjacent edits?
- If code-rules mode is disabled, do selected root agent instruction files avoid routing agents to `docs/code_rules.md`?
- Does `docs/code_rules.md` exist only when the user explicitly selected code-rules mode or when the user chose to preserve an existing file?
- Are project-memory docs ignored by VCS and treated as local-only unless the user explicitly wants them tracked?
- Is `docs/architecture.md` a map rather than a large mixed architecture dump?
- Are architecture facts split by topic?
- Are product, design, deployment, and security facts in their owner files?
- Does the docs set match the project profile?
- If docs already exist, has the user chosen whether to keep, audit only, migrate after approval, or let the agent decide?
- Are UI, design, and product docs absent for non-UI/non-product projects unless there is clear evidence they are needed?
- Are there duplicate facts in multiple docs?
- Do root agent instruction files, `README*`, `docs/architecture.md`, and profile docs contradict each other?
- Are there stale links to missing files?
- Are old filenames still referenced after previous moves?
- Are unknown facts marked as `TODO: clarify` rather than invented?
- Are language rules consistent with the project?

## Decision And Authorization Gates

Do not ask merely because several interpretations are imaginable. First inspect the repository and eliminate choices that evidence already resolves. Ask only when the answer changes the resulting documentation system or authorization boundary.

User input is required when:

- existing docs, README files, or project instruction files are present and the prompt did not explicitly delegate cleanup decisions; first ask whether to keep as-is, audit only, migrate after approval, or let the agent decide;
- root agent instructions are being created or replaced and the user has not selected whether to use `docs/code_rules.md` for code and code-adjacent edits;
- root agent instructions are being created or replaced and the user has not selected documentation maintenance mode;
- the goal remains materially unclear after repository discovery;
- several plausible owner maps remain and choosing one would change future routing;
- an existing root agent instruction file needs heavy rewriting;
- a file might be deleted, merged, or renamed;
- documentation language policy is unclear;
- project-memory docs are not ignored and `docs/` might be public/user-facing;
- the project profile remains ambiguous after inspecting code and configuration and the ambiguity changes the owner set;
- root agent instruction files, `README*`, `docs/architecture.md`, and profile docs conflict; mark `TODO: clarify` or ask instead of choosing a source of truth silently;
- secrets, credentials, production access, or private data might be involved.

Do not ask for permission to create a justified missing owner under `automatic durable maintenance`; follow the missing-owner protocol. Do not ask the user for a fact that repository files, tools, or available runtime evidence can establish.
Do not ask again for an exact action the user already authorized. Discussion is not an instruction to implement; an explicit change request is.

## Safe Verification

After approved edits:

- Run `rg` for old filenames.
- Check links from `docs/architecture.md`.
- Check that every newly created docs file is linked from the map.
- Run the documentation check read-only and report the address, owner, and reachability result.
- Refresh the derived graph once after the agreed structure changes, and report remaining errors instead of claiming a clean graph.
- If the user delegated docs cleanup to the agent, check that durable facts from existing docs were either migrated, preserved in place, or marked `TODO: clarify` when conflicting.
- Check that project-memory docs are covered by `.gitignore` or the repo's VCS ignore file unless the user explicitly wants them tracked.
- Check that no root Markdown docs remain except selected root agent instruction files such as `AGENTS.md` or `CLAUDE.md`, unless the project intentionally keeps content files elsewhere.
- Report docs-only changes as docs-only; do not run app tests unless code or behavior changed.
