# Context Cartographer

`context-cartographer` is a Codex skill for creating and maintaining lean project documentation that helps AI agents understand a repository without rereading the whole codebase every time.

It builds a small local documentation system for a project: a short `AGENTS.md`, a documentation map, code-editing rules, and only the profile-specific docs the project actually needs.

## What It Does

- Inspects a project before changing documentation.
- Detects the project profile: UI app, website, SaaS, API, bot, library, content/SEO project, ecommerce/payments, data/ML, infra/devops, mobile app, or mixed repo.
- Creates a minimal docs core instead of a large generic documentation dump.
- Asks what to do with existing docs before rewriting, moving, or deleting them.
- Uses existing docs as project context when the user delegates cleanup decisions.
- Keeps agent documentation local-only by default and adds it to `.gitignore`.
- Makes `AGENTS.md` distinguish discussion from actual edit requests, so Codex does not start changing files just because the user is thinking out loud.
- Updates docs later only for durable changes, not routine task notes.

## Why It Exists

AI coding agents waste context when every new task starts with rereading large parts of a project just to understand where things live.

This skill creates a compact map of the project:

- where the main code lives;
- what each docs file owns;
- when to read architecture, product, design, deployment, API, payment, SEO, or security docs;
- what rules apply before code edits;
- which docs should stay private and local.

The result is less repeated exploration, fewer accidental edits, and better continuity between Codex sessions.

## Token Savings

The exact savings depend on project size, but the pattern is usually:

- Small project: about 10-30% fewer context tokens on navigation-heavy tasks.
- Medium project: about 30-60% fewer context tokens after the first documentation pass.
- Large or messy project: often 50-80% fewer tokens for onboarding, architecture, and "where is this?" tasks.

Example: instead of reading 50k-200k tokens of scattered code, README files, old notes, and configs, the agent can often read 5k-20k tokens of focused project docs, then open only the relevant source files.

This does not make implementation free. It reduces repeated context discovery.

## What Gets Created

Minimal core:

- `AGENTS.md` - short agent router and behavior rules.
- `docs/architecture.md` - documentation map and reading rules.
- `docs/architecture-overview.md` - stack, repository layout, important entry points.
- `docs/architecture-quality-risks.md` - tests, verification, known risks.
- `docs/code_rules.md` - code-editing rules for agentic coding.

Profile-based docs are created only when needed:

- `docs/architecture-frontend.md`
- `docs/architecture-backend-data.md`
- `docs/API.md`
- `docs/INTEGRATIONS.md`
- `docs/CONTENT-SEO.md`
- `docs/architecture-payments.md`
- `docs/PRODUCT.md`
- `docs/DESIGN.md`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY.md`
- `docs/ADMIN.md`
- `docs/GLOSSARY.md`

## Existing Documentation

If a project already has documentation, the skill should stop after the initial scan and ask what to do:

- keep as-is;
- audit only;
- migrate after approval;
- let Codex decide.

If the user chooses "let Codex decide", the skill uses existing docs as project context, preserves durable facts, marks conflicts as `TODO: clarify`, and migrates the docs into the profile-based structure.

## Local-Only By Default

Project-memory docs are private working memory for agents by default.

The generated docs should be added to `.gitignore` or the repo's VCS ignore file unless the user explicitly wants them tracked or published.

If a project already uses `docs/` as public documentation, the skill must not ignore `docs/` broadly. It should ask or use precise ignore patterns.

## Install

Use the Codex skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

Then restart Codex so the new skill is loaded.

## Usage

Simple prompt:

```text
Используй $context-cartographer и приведи документацию проекта в порядок.
```

For a messy existing project:

```text
Используй $context-cartographer, сделай мне нормальную документацию по этому проекту. Сейчас какая-то документация уже есть, но она плохая и неполная.
```

If you want Codex to decide the documentation cleanup strategy:

```text
Используй $context-cartographer. Проанализируй существующую документацию как контекст, сам реши что сохранить, перенести или удалить, и приведи docs к структуре skill. Перед правками покажи proposed docs map.
```

## Repository Layout

```text
context-cartographer/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── audit-checklist.md
│   ├── cleanup-rules.md
│   ├── doc-map.md
│   ├── file-templates.md
│   └── question_schema.md
└── scripts/
    ├── questionnaire_server.py
    └── smoke_test.py
```

## Validation

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py context-cartographer
python3 context-cartographer/scripts/smoke_test.py
```

## Design Principles

- Small required context.
- Profile-based docs instead of universal docs.
- Existing docs are treated as evidence, not discarded blindly.
- Discussion is not permission to edit.
- Durable docs are updated only when durable project behavior changes.
- Local project-memory docs should not be committed or deployed by default.
