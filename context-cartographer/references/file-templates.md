# File Templates

Use these compact templates when creating new project documentation. Remove sections that do not apply. Mark unknown durable facts as `TODO: clarify`.

Resolve both code-rules mode and documentation maintenance mode before writing generated files. Do not leave mode TODOs in output.

## Contents

- Minimal core: selected root agent instruction file(s), `docs/architecture.md`, `docs/architecture-overview.md`, `docs/architecture-quality-risks.md`
- Selected core: `docs/code_rules.md` only when the user chooses to use a dedicated code-writing rules file.
- Profile docs: `docs/architecture-frontend.md`, `docs/architecture-backend-data.md`, `docs/PRODUCT.md`, `docs/DESIGN.md`, `docs/DEPLOYMENT.md`
- Conditional docs: `docs/SECURITY.md`, `docs/architecture-payments.md`, `docs/API.md`, `docs/INTEGRATIONS.md`, `docs/CONTENT-SEO.md`, `docs/advertising.md`, `docs/ADMIN.md`, `docs/GLOSSARY.md`

## Root Agent Instruction File

Create the file that matches the selected target:

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`
- Cursor: `.cursor/rules/context-cartographer.mdc`
- Legacy Cursor only when already present: `.cursorrules`
- Multi-agent: one thin adapter per selected target.

Use the same body shape for each target, adjusted only for the agent name and file format. For Cursor `.mdc`, include the required frontmatter before the Markdown body.

```markdown
# Project Instructions

- Agent target: TODO: replace with `Codex`, `Claude Code`, `Cursor`, or `multi-agent adapter`.
- Reply in the project/user's default language unless asked otherwise.
- Treat questions, analysis, brainstorming, and project discussion as conversation-only by default. Do not edit files, run mutating commands, or make code changes unless the user explicitly asks to implement, change, create, update, delete, move, fix, run, or apply something.
- If the user's intent is ambiguous, ask whether they want discussion only or actual file changes before editing.
- If the goal is unclear and cannot be safely inferred, ask before acting.
- Treat project-memory docs as local-only: do not commit, push, upload, publish, or deploy them unless explicitly requested.
- Code-rules mode: TODO: replace with `use code rules file` or `do not use code rules file` before writing this file.
- If code-rules mode is `use code rules file`, read `docs/code_rules.md` before changing code or code-adjacent project files such as tests, migrations, scripts, build config, deployment config, or application behavior.
- If code-rules mode is `do not use code rules file`, do not require or route to `docs/code_rules.md`; follow root instructions, direct user requests, and local project patterns.
- Read `docs/architecture.md` only when the task affects structure, behavior, routes, models, services, tests, deployment, durable rules, or documentation organization.
- Documentation maintenance mode: TODO: replace with `automatic durable maintenance` or `request-only maintenance` before writing this file.
- If maintenance mode is `automatic durable maintenance`, after any completed work that changes durable project behavior, architecture, setup, deployment, staging, test data, SSH access, import/export flow, public URLs, WordPress setup, operator workflow, data model, public interfaces, agent workflow, or documentation ownership, check whether the matching docs file must be updated. If yes, update it in the same task before the final response; if not, explicitly say that no durable docs update was needed.
- If maintenance mode is `request-only maintenance`, update docs only when the user explicitly asks, but mention when completed work may have made existing docs stale.
- For product, design, deployment, security, API, integration, content, admin, or advertising questions, read the matching `docs/*.md` owner file first.
- If documentation ownership is unclear or no suitable file exists, ask before creating a new documentation file.
```

## docs/architecture.md

```markdown
# Architecture Map

This file is a map, not the full architecture record. Read it when a task affects project structure, behavior, routes, models, services, tests, deployment, durable rules, or documentation organization.

## Project Profile

- Profile: TODO: clarify
- Stack: TODO: clarify

## Core Architecture Docs

- `docs/architecture-overview.md`: stack, repository layout, system boundaries.
- `docs/architecture-quality-risks.md`: tests, verification, known risks.

## Profile Docs

- TODO: link only docs that exist.

## Companion Docs

- Code-rules mode: TODO: replace with `use code rules file` or `do not use code rules file` before writing this file.
- `docs/code_rules.md`: code-editing rules, only when code-rules mode is `use code rules file`.

## Local-Only Policy

- Project-memory docs are local-only by default.
- Keep selected root agent instruction files, `docs/`, and `.project-questionnaire/` in `.gitignore` or the repo's VCS ignore file unless the user explicitly wants docs tracked.
- If `docs/` is public/user-facing, ask before ignoring it broadly.

## Update Rules

- Write new facts only to the most specific owner file.
- Do not duplicate durable facts across files.
- Agent target: TODO: replace with the selected target before writing this file.
- Root agent instruction files: TODO: list selected files such as `AGENTS.md`, `CLAUDE.md`, or `.cursor/rules/context-cartographer.mdc`.
- Code-rules mode: TODO: replace with the mode selected in root agent instructions before writing this file.
- Documentation maintenance mode: TODO: replace with the mode selected in root agent instructions before writing this file.
- Under `automatic durable maintenance`, update docs only for durable project changes and do it in the same task; do not record routine implementation notes, transient task status, or obvious edits.
- Under `request-only maintenance`, do not edit docs unless explicitly asked, but flag likely stale docs in the final response.
- If no owner file fits, ask before creating one.
- After renaming or deleting docs, check stale references with `rg`.
```

## .gitignore snippet

Use this snippet only when `docs/` is the private project-memory documentation folder. If `docs/` is public/user-facing, ask before choosing precise ignore patterns.

```gitignore
# Local agent/project documentation
AGENTS.md
CLAUDE.md
.cursor/rules/context-cartographer.mdc
.cursorrules
docs/
.project-questionnaire/
```

## docs/architecture-overview.md

```markdown
# Architecture Overview

## Stack

- Runtime: TODO: clarify
- Frameworks/tools: TODO: clarify
- Storage/data: TODO: clarify

## Repository Layout

- `path/`: purpose

## System Boundaries

- In scope: TODO: clarify
- Out of scope: TODO: clarify

## Important Entry Points

- `path/file`: purpose
```

## docs/architecture-quality-risks.md

```markdown
# Quality And Risks

## Verification Commands

- `command`: what it verifies

## Known Risks

- Risk: mitigation or owner

## Technical Debt

- Item: why it matters
```

## docs/code_rules.md

```markdown
# Code Rules

Create this file only when the user selected `use code rules file` during first setup.

Behavioral guidelines for agentic coding workflows. Merge with project-specific instructions as needed.

Read this file before changing code or code-adjacent project files such as tests, migrations, scripts, build config, deployment config, or application behavior.

These rules bias toward small, verified, reversible changes. For trivial tasks, use judgment, but do not skip explicit user intent, context checks, or verification.

## 1. Confirm Intent And Scope

Discussion is not permission to edit.

- Treat questions, analysis, brainstorming, and project discussion as conversation-only unless the user explicitly asks to implement, change, create, update, delete, move, fix, run, or apply something.
- If the goal, target behavior, or permission to edit is unclear, ask before changing files or running mutating commands.
- State meaningful assumptions when they affect implementation.
- If multiple valid interpretations exist, present the options instead of choosing silently.

## 2. Curate Context First

Use just enough context for the next step.

- Read the nearest project instructions and the files directly involved in the change.
- Prefer `rg`, targeted file reads, tests, types, schemas, and existing patterns over broad repo scans.
- Do not load unrelated docs, generated folders, dependencies, build output, or large files unless they are needed.
- If existing facts conflict, do not invent a resolution. Ask or mark `TODO: clarify` in the right docs file.

## 3. Plan Small Changes

For non-trivial edits, make a short plan before implementation.

- Define the user-visible outcome.
- Identify the smallest set of files that must change.
- Name the verification command or manual check before editing.
- Prefer one narrow change over a broad refactor.
- Do not add speculative features, abstractions, configuration, dependencies, or error handling.

## 4. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

- Do not improve adjacent code, comments, or formatting.
- Do not refactor things that are not broken.
- Match existing style, even if you would do it differently.
- If you notice unrelated dead code, mention it; do not delete it.

When your changes create orphans:

- Remove imports, variables, and functions that your changes made unused.
- Do not remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

## 5. Verify, Then Iterate

Treat agent-written code like code from a new contributor: useful, but not trusted until checked.

- Run the most focused relevant checks first, then broader checks when the blast radius justifies them.
- Add or update tests when fixing bugs, changing shared behavior, or touching risky logic.
- Do not add tests just to satisfy process when the repo has no test pattern and the change is trivial.
- If a check fails, investigate and fix within the task scope.
- If a check cannot run, report why and give the best available substitute.

## 6. Security And Operations Guardrails

- Never write secrets, tokens, private keys, production credentials, or private user data into code, docs, logs, tests, or chat.
- Ask before adding dependencies, changing lockfiles, running migrations, changing deployment config, deleting data, or touching production-like systems.
- Preserve permission boundaries and existing access-control checks unless the user explicitly asks to change them.
- Prefer reversible changes and document rollback or recovery steps for risky operations.

## 7. Durable Documentation

- Documentation maintenance mode: TODO: replace with the mode selected in root agent instructions before writing this file.
- Under `automatic durable maintenance`, after any completed work that changes deployment, staging, test data, SSH access, import/export flow, public URLs, WordPress setup, operator workflow, setup, architecture, data model, public interfaces, agent workflow, or documentation ownership, check whether `docs/DEPLOYMENT.md`, `docs/ADMIN.md`, `docs/architecture.md`, `docs/SECURITY.md`, or another owner doc must be updated. If yes, update it in the same task before the final response; if not, explicitly say that no durable docs update was needed.
- Under `request-only maintenance`, update docs only when the user explicitly asks, but mention if completed work likely made docs stale.
- Do not record routine implementation notes, transient task status, or obvious edits.
- If documentation ownership is unclear, ask before creating a new docs file.

## 8. Finish With Evidence

At the end of a code or code-adjacent task, report only what matters:

- files changed;
- checks run and results;
- checks not run and why;
- known follow-up risks, if any.

These guidelines are working when diffs are small, intent is clear before edits, verification is explicit, unrelated code stays untouched, and documentation changes only when they preserve durable project knowledge.
```

## docs/architecture-frontend.md

```markdown
# Frontend Architecture

Create this file only for UI, website, mobile, dashboard, admin, or other user-facing interface surfaces.

## UI Stack

- Framework/platform: TODO: clarify
- Styling: TODO: clarify

## Screens, Layouts, And Components

- `path/`: purpose

## State And Data Flow

- TODO: clarify

## Responsive And Accessibility Rules

- TODO: clarify
```

## docs/architecture-backend-data.md

```markdown
# Backend, Runtime, And Data Architecture

Create this file for backend services, APIs, bots, automations, jobs, data pipelines, storage, or runtime logic.

## Runtime Structure

- `path/`: purpose

## Data Model Or State

- Entity/state: purpose and key relationships

## Services, Jobs, Automations, And Queues

- Service/job/automation: purpose

## Access And Business Rules

- TODO: clarify
```

## docs/PRODUCT.md

```markdown
# Product

Create this file only when the project has durable product, audience, business, or user-workflow decisions.

## Audience

- TODO: clarify

## Core Value

- TODO: clarify

## Main Workflows

- Workflow: user outcome

## Scope Boundaries

- In scope: TODO: clarify
- Out of scope: TODO: clarify
```

## docs/DESIGN.md

```markdown
# Design

Create this file only when visual, UX, interaction, brand, or user-facing copy rules matter.

## UX Principles

- TODO: clarify

## Visual Direction

- TODO: clarify

## Components And Interaction Rules

- Component: behavior

## Copy Rules

- TODO: clarify
```

## docs/DEPLOYMENT.md

```markdown
# Deployment, Release, And Operations

Create this file only when local run, deploy, release, publishing, scheduling, hosting, or operations matter.

## Environments

- Local: TODO: clarify
- Production/release: TODO: clarify

## Run Commands

- `command`: purpose

## Deploy Or Release Flow

1. TODO: clarify

## Logs, Queues, Scheduler, Or Monitoring

- TODO: clarify

## Rollback Or Recovery

- TODO: clarify
```

## docs/SECURITY.md

```markdown
# Security

Create this file only when the project handles auth, payments, PII, production access, external tokens, secrets, or permission-sensitive workflows.

## Secret Policy

- Never write secrets into docs, chat, logs, tests, or committed files.

## Access Rules

- TODO: clarify

## Sensitive Data

- TODO: clarify

## Operational Checks

- TODO: clarify
```

## docs/architecture-payments.md

```markdown
# Payment Architecture

Create this file only when payments, subscriptions, billing, invoices, refunds, fiscalization, or provider webhooks exist.

## Providers And Flows

- Provider/flow: purpose

## Domain Model

- Payment/subscription/invoice entity: purpose

## Webhooks And Reconciliation

- TODO: clarify

## Risks And Verification

- TODO: clarify
```

## docs/API.md

```markdown
# API And Public Interface

Create this file for public APIs, internal API contracts, webhooks, SDKs, CLI commands, or library public surface.

## Interfaces

- Endpoint/command/module: purpose

## Contracts

- Request/input: TODO: clarify
- Response/output: TODO: clarify

## Compatibility Rules

- TODO: clarify
```

## docs/INTEGRATIONS.md

```markdown
# Integrations

Create this file when the project depends on third-party services, provider APIs, sync jobs, external storage, messaging, analytics, or credentials.

## Providers

- Provider: purpose

## Data Flow

- TODO: clarify

## Credential And Environment Policy

- TODO: clarify
```

## docs/CONTENT-SEO.md

```markdown
# Content And SEO

Create this file for content projects, SEO pages, editorial rules, metadata, schema, internal linking, or publishing workflows.

## Content Types

- Type: purpose

## SEO Rules

- Metadata: TODO: clarify
- Internal linking: TODO: clarify
- Schema: TODO: clarify

## Editorial Workflow

- TODO: clarify
```

## docs/advertising.md

```markdown
# Advertising

Create this file when paid acquisition, campaigns, UTM rules, ad copy, targeting, or conversion tracking need durable documentation.

## Channels And Campaigns

- Channel/campaign: purpose

## Tracking Rules

- UTM: TODO: clarify
- Conversion events: TODO: clarify

## Copy And Targeting Notes

- TODO: clarify
```

## docs/ADMIN.md

```markdown
# Admin And Operations

Create this file when administrators, moderators, support staff, or operators need durable workflow rules.

## Roles

- Role: permissions and responsibilities

## Workflows

- Workflow: purpose

## Risky Actions

- Action: required checks
```

## docs/GLOSSARY.md

```markdown
# Glossary

Create this file when project terms, acronyms, names, or domain vocabulary must be preserved consistently.

## Terms

- Term: definition
```
