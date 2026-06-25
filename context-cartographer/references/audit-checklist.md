# Audit Checklist

Use this checklist before changing existing project documentation.

## Repository Scan

- Run `rg --files` from the project root.
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

## Quality Checks

- Is each selected root agent instruction file short enough to act as a router?
- Does the selected target match the file: `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, `.cursor/rules/context-cartographer.mdc` for Cursor, or multiple thin adapters for multi-agent use?
- Does each selected root agent instruction file distinguish conversation-only requests from explicit edit/implementation requests?
- Does each selected root agent instruction file state the selected code-rules mode?
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

## Questions To Ask Before Editing

Ask before acting when:

- existing docs, README files, or project instruction files are present and the prompt did not explicitly delegate cleanup decisions; first ask whether to keep as-is, audit only, migrate after approval, or let the agent decide;
- root agent instructions are being created or replaced and the user has not selected whether to use `docs/code_rules.md` for code and code-adjacent edits;
- the goal is unclear;
- there are multiple plausible owner files;
- no suitable owner file exists;
- an existing root agent instruction file needs heavy rewriting;
- a file might be deleted, merged, or renamed;
- existing docs are present and the user has not chosen what to do with them;
- documentation language policy is unclear;
- project-memory docs are not ignored and `docs/` might be public/user-facing;
- the project profile is ambiguous or mixed;
- a suggested docs file does not match the detected project profile;
- root agent instruction files, `README*`, `docs/architecture.md`, and profile docs conflict; mark `TODO: clarify` or ask instead of choosing a source of truth silently;
- secrets, credentials, production access, or private data might be involved.

## Safe Verification

After approved edits:

- Run `rg` for old filenames.
- Check links from `docs/architecture.md`.
- Check that every newly created docs file is linked from the map.
- If the user delegated docs cleanup to the agent, check that durable facts from existing docs were either migrated, preserved in place, or marked `TODO: clarify` when conflicting.
- Check that project-memory docs are covered by `.gitignore` or the repo's VCS ignore file unless the user explicitly wants them tracked.
- Check that no root Markdown docs remain except selected root agent instruction files such as `AGENTS.md` or `CLAUDE.md`, unless the project intentionally keeps content files elsewhere.
- Report docs-only changes as docs-only; do not run app tests unless code or behavior changed.
