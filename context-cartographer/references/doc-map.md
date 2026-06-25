# Documentation Map

Use this file to choose a minimal, profile-based documentation set and decide where each durable fact belongs.

## Contents

- Minimal Core
- Profile-Based Files
- Project Profiles
- Monorepo Rule
- Conditional Files
- Ownership Rules
- Creation Rules
- Local-Only Policy
- Language Policy

## Minimal Core

Create or maintain these files when the project has durable documentation needs. When setting up a documentation system, do not skip any minimal core file except `docs/code_rules.md` when the user declines code-rules mode.

- Root agent instruction file: short router for agent behavior and documentation routing. Use `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, `.cursor/rules/context-cartographer.mdc` for Cursor, or multiple thin adapters for multi-agent projects.
- `docs/architecture.md`: map of documentation files, reading rules, and architecture ownership.
- `docs/architecture-overview.md`: stack, repository layout, runtime shape, important folders, and system boundaries.
- `docs/architecture-quality-risks.md`: test commands, verification rules, known risks, fragile areas, and technical debt.
- `docs/code_rules.md`: selected-core rules for code edits and code-adjacent changes; create only when the user explicitly chooses code-rules mode.

Do not create a larger set until the project profile makes those files useful.

## Profile-Based Files

Create these only when the profile needs them:

- `docs/architecture-frontend.md`: UI architecture, layouts, components, styling, client state, mobile screens, or user-facing frontend implementation.
- `docs/architecture-backend-data.md`: backend, API runtime, data model, services, jobs, automations, pipelines, storage, queues, access rules, and business logic.
- `docs/PRODUCT.md`: audience, value proposition, product scope, workflows, pricing or access boundaries, and product tone.
- `docs/DESIGN.md`: visual direction, UX rules, component behavior, copy rules, and design constraints.
- `docs/DEPLOYMENT.md`: local runbook, release/deploy/publish flow, environments, logs, rollback, scheduler, queues, and operations.
- `docs/ADMIN.md`: operator roles, admin workflows, moderation, support flows, and risky backoffice actions.

## Project Profiles

- UI app, website, SaaS, dashboard, or mobile app: use `architecture-frontend.md`, `PRODUCT.md`, `DESIGN.md`, and `DEPLOYMENT.md` when there is a deploy or release flow.
- Backend API or service: use `architecture-backend-data.md`, `API.md`, `DEPLOYMENT.md`, and `INTEGRATIONS.md` when providers exist. Do not create frontend/design docs unless there is a UI surface.
- Bot or automation: use `architecture-backend-data.md`, `INTEGRATIONS.md`, and `DEPLOYMENT.md` when scheduling, hosting, or credentials matter. Add `ADMIN.md` only for operator workflows.
- Library or package: use `architecture-overview.md`, `architecture-quality-risks.md`, and `API.md` for public surface or usage contracts. Use `DEPLOYMENT.md` only for release/publishing workflows.
- Content or SEO project: use `CONTENT-SEO.md`; add `PRODUCT.md` for business goals and `DESIGN.md` only when UI/brand guidance exists.
- Ecommerce or payments: use `architecture-payments.md`, `SECURITY.md`, `DEPLOYMENT.md`, and relevant `INTEGRATIONS.md`; add UI/product/design docs only when storefront, admin, or product strategy exists.
- Data, ML, ETL, or analytics pipeline: use `architecture-backend-data.md`, `INTEGRATIONS.md`, `DEPLOYMENT.md`, and `SECURITY.md` when data sensitivity matters.
- Infra, DevOps, or platform repo: use `DEPLOYMENT.md`, `SECURITY.md`, and `INTEGRATIONS.md`; avoid product/design/frontend docs unless the repo also has a product UI.
- Mixed project: create the minimal core first, then add only the profile files supported by repo evidence or user intent.

## Monorepo Rule

For monorepo repositories with multiple independent apps, packages, or workspaces, identify owners and workspace boundaries before creating or moving docs. Then choose one shared docs map, per-workspace docs maps, or both, based on how much architecture and ownership the workspaces actually share.

## Conditional Files

Suggest these only when the project actually needs them:

- `docs/SECURITY.md`: auth, payments, PII, production access, external tokens, secrets, or permission-sensitive workflows.
- `docs/architecture-payments.md`: payment providers, subscriptions, invoices, webhooks, refunds, reconciliation, fiscalization.
- `docs/API.md`: public API, internal API contracts, webhooks, SDK behavior, request/response examples, CLI commands, or library public surface.
- `docs/INTEGRATIONS.md`: third-party services, credentials location policy, sync jobs, provider-specific constraints.
- `docs/CONTENT-SEO.md`: content strategy, SEO pages, metadata rules, internal linking, schema, editorial workflows.
- `docs/advertising.md`: campaign structure, UTM rules, ad copy, paid channels, conversion tracking.
- `docs/ADMIN.md`: admin panel, roles, operational workflows, backoffice actions, moderation, support flows.
- `docs/GLOSSARY.md`: domain terms, project-specific vocabulary, acronyms, names that agents must preserve.

## Ownership Rules

- Put architecture facts in the most specific `docs/architecture-*.md` file.
- Put the routing map and reading rules in `docs/architecture.md`.
- Put product decisions in `docs/PRODUCT.md`, not architecture files.
- Put visual and UX rules in `docs/DESIGN.md`, not product or frontend architecture unless they affect implementation.
- Put deployment, release, publishing, and operational runbooks in `docs/DEPLOYMENT.md`.
- Put staging, test-data setup, SSH access notes, import/export flow, public URLs, WordPress setup, logs, rollback, queues, scheduler, and monitoring in `docs/DEPLOYMENT.md`.
- Put operator workflows, support actions, admin panel usage, moderation, backoffice checks, and risky manual actions in `docs/ADMIN.md`.
- Put code-editing behavior in `docs/code_rules.md` only when the user selects code-rules mode.
- Ensure each selected root agent instruction file states the target agent, selected code-rules mode, and selected documentation maintenance mode.
- If code-rules mode is enabled, tell agents to read `docs/code_rules.md` before every code or code-adjacent edit. If declined, state that no dedicated code-rules file is used.
- Do not infer code-rules mode from project type, existing docs, or "let the agent decide"; using `docs/code_rules.md` requires explicit user selection.
- Do not infer documentation maintenance mode from project type, existing docs, or "let the agent decide"; automatic durable maintenance requires explicit user selection.
- Put local-only documentation privacy rules in each selected root agent instruction file, `docs/architecture.md`, and the repo's VCS ignore file.
- Put secret-handling and access-control policy in `docs/SECURITY.md` when that file exists.
- Put temporary task plans outside durable docs unless the user explicitly wants them preserved.
- Do not write routine task notes, transient status, or obvious implementation details into durable docs.

## Creation Rules

- Create the smallest useful set first.
- Choose the root agent instruction target before creating or replacing root instructions: `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, `.cursor/rules/context-cartographer.mdc` for Cursor, or thin adapters for multiple selected agents. Ask when the target is ambiguous.
- Ask for code-rules mode before creating root agent instructions unless the user already specified it. This is a blocking gate.
- Include `docs/code_rules.md` in the minimal documentation core only when the user selects code-rules mode.
- Ask for the documentation maintenance mode before creating root agent instructions unless the user already specified it. This is a blocking gate, not a recommendation.
- Always add project-memory docs to `.gitignore` or the repo's VCS ignore file unless the user explicitly wants docs tracked.
- Under automatic durable maintenance, update docs after later tasks only when durable behavior, architecture, setup, deployment, staging, test data, SSH access, import/export flow, public URLs, WordPress setup, operator workflow, data model, public interfaces, agent workflow, or documentation ownership changes.
- Under request-only maintenance, do not update docs after later tasks unless the user explicitly asks, but mention likely stale docs when relevant.
- Do not create UI, design, product, deployment, or security files unless repo evidence or user intent supports them.
- Do not create conditional files merely because they might be useful later.
- If no existing owner file fits, ask before creating a new documentation file.
- If a file already exists, merge surgically instead of replacing it.
- Do not move public repo docs or user-facing content into `docs/` automatically.

## Local-Only Policy

Project-memory docs created or maintained by this skill are local-only by default. Do not commit, push, upload, publish, or deploy them unless the user explicitly asks.

Default ignore patterns when `docs/` is owned by project-memory docs:

```gitignore
# Local agent/project documentation
AGENTS.md
CLAUDE.md
.cursor/rules/context-cartographer.mdc
.cursorrules
docs/
.project-questionnaire/
```

If `docs/` is already a public docs site, package documentation, or user-facing content folder, do not ignore `docs/` broadly. Ask before choosing a private documentation path or add precise ignore patterns only for project-memory files.

## Language Policy

- Use English for project documentation by default.
- Preserve non-English text only when it is real UI copy, brand text, content examples, legal/user-facing copy, campaign keywords, or required domain terminology.
- If the project language is unclear, ask before normalizing documentation language.
