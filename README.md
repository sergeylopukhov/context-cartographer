# Context Cartographer

`context-cartographer` is an Agent Skill for Codex, Claude Code, and Cursor. It creates and maintains lean project documentation that helps AI coding agents understand a repository without rereading the whole codebase every time.

It builds a small local documentation system for a project: a short `AGENTS.md`, a documentation map, code-editing rules, and only the profile-specific docs the project actually needs.

## What It Does

- Inspects a project before changing documentation.
- Detects the project profile: UI app, website, SaaS, API, bot, library, content/SEO project, ecommerce/payments, data/ML, infra/devops, mobile app, or mixed repo.
- Creates a minimal docs core instead of a large generic documentation dump.
- Asks what to do with existing docs before rewriting, moving, or deleting them.
- Uses existing docs as project context when the user delegates cleanup decisions.
- Keeps agent documentation local-only by default and adds it to `.gitignore`.
- Makes agent instruction files distinguish discussion from actual edit requests, so the agent does not start changing files just because the user is thinking out loud.
- Asks how documentation should be maintained after setup: automatically for durable project changes, or only on explicit request.
- Updates docs later only for durable changes, not routine task notes.

## Why It Exists

AI coding agents waste context when every new task starts with rereading large parts of a project just to understand where things live.

This skill creates a compact map of the project:

- where the main code lives;
- what each docs file owns;
- when to read architecture, product, design, deployment, API, payment, SEO, or security docs;
- what rules apply before code edits;
- which docs should stay private and local.

The result is less repeated exploration, fewer accidental edits, and better continuity between agent sessions.

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
- let the agent decide.

If the user chooses "let the agent decide", the skill uses existing docs as project context, preserves durable facts, marks conflicts as `TODO: clarify`, and migrates the docs into the profile-based structure.

## Questions And Questionnaire

The skill has a bundled local questionnaire server. It does not depend on another installed questionnaire skill.

If the agent needs one or two answers, it can ask directly in chat. If it needs more than two questions, it should create a temporary `.context-cartographer-questionnaire/` folder in the user's project, run the bundled `scripts/questionnaire_server.py`, and give the user a local `http://127.0.0.1:<port>/` form.

The questionnaire output is saved as:

- `.context-cartographer-questionnaire/answers.json`
- `.context-cartographer-questionnaire/answers.md`

The folder is local working data and is ignored by default.

Questionnaire UI language is localized. `questions.json` can set `language: "en"` or `language: "ru"`. If omitted, the server infers Russian from Cyrillic questionnaire text and English otherwise.

## Documentation Maintenance Mode

Initial docs creation and ongoing docs maintenance are separate decisions.

The skill should not silently create or migrate documentation in an empty or unclear project. But when it creates root agent instructions, it must ask how future documentation should be maintained:

- automatic durable maintenance: after completed code, infrastructure, deployment, or operator-workflow work, the agent checks whether durable docs must be updated and does that in the same task;
- request-only maintenance: docs change only when the user explicitly asks, though the agent may mention that docs are probably stale.

`automatic durable maintenance` is explicit opt-in. The skill must not choose it just because the project already has docs or because the user asked for a recommendation.

The selected mode is written into `AGENTS.md`, `docs/architecture.md`, and `docs/code_rules.md`.

## Local-Only By Default

Project-memory docs are private working memory for agents by default.

The generated docs should be added to `.gitignore` or the repo's VCS ignore file unless the user explicitly wants them tracked or published.

If a project already uses `docs/` as public documentation, the skill must not ignore `docs/` broadly. It should ask or use precise ignore patterns.

## Install

The canonical package is the `context-cartographer/` folder. Use the same folder for Codex, Claude Code, and Cursor.

### Codex

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

Then restart Codex so the new skill is loaded.

### Claude Code

Personal install:

```bash
git clone https://github.com/sergeylopukhov/context-cartographer.git /tmp/context-cartographer
mkdir -p ~/.claude/skills
rsync -a /tmp/context-cartographer/context-cartographer/ ~/.claude/skills/context-cartographer/
```

Project install:

```bash
mkdir -p .claude/skills
rsync -a context-cartographer/ .claude/skills/context-cartographer/
```

Optional persistent pointer:

```bash
cp adapters/claude/CLAUDE.md ./CLAUDE.md
```

Use `/context-cartographer` or ask Claude to use the `context-cartographer` skill.

### Cursor

Project skill install:

```bash
mkdir -p .cursor/skills
rsync -a context-cartographer/ .cursor/skills/context-cartographer/
```

Optional Cursor rule adapter:

```bash
mkdir -p .cursor/rules
cp adapters/cursor/context-cartographer.mdc .cursor/rules/context-cartographer.mdc
```

Use `/context-cartographer` or ask Cursor Agent to use the `context-cartographer` skill.

## Usage

Short prompts are enough. The skill should scan the project, ask missing decisions through its bundled questionnaire when needed, propose a docs map, and then update the approved documentation.

Simple prompt:

```text
Use $context-cartographer and bring this project's documentation into shape.
```

Russian prompt:

```text
Используй $context-cartographer и доделай документацию проекта.
```

For a messy existing project:

```text
Use context-cartographer to create proper documentation for this project. Some documentation already exists, but it is incomplete and not useful.
```

If you want the agent to decide the documentation cleanup strategy:

```text
Use context-cartographer. Analyze existing documentation as project context, decide what to keep, move, or delete, and migrate docs to the skill's structure. Show a proposed docs map before editing.
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

adapters/
├── claude/
│   └── CLAUDE.md
└── cursor/
    └── context-cartographer.mdc
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
- Documentation maintenance mode is explicit, not guessed.
- Local project-memory docs should not be committed or deployed by default.
