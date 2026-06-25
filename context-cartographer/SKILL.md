---
name: context-cartographer
description: AGENTS.md, CLAUDE.md, Cursor rules, architecture.md, project docs, docs/, and documentation map setup, audit, cleanup, and maintenance for new and existing repositories. Use when an AI coding agent needs to create or update agent instructions, classify project type before choosing docs, split oversized architecture docs, route documentation ownership, or decide which project docs to read or update for UI apps, websites, SaaS, APIs, bots, automations, libraries, content projects, ecommerce, payments, data/ML, infra/devops, mobile apps, and internal tools. Also use for short documentation requests such as "доделай документацию", "создай нормальную доку", "приведи docs в порядок", "почини AGENTS.md", or "настрой документацию проекта".
---

# Context Cartographer

Use this skill to build a small, durable documentation system that helps future agents load the right context at the right time.

Keep `AGENTS.md` short. Put project documentation in `docs/`. Prefer a documentation map over one large all-purpose architecture file.

## Core Rules

- Short broad prompts are enough. If the user asks to create, finish, fix, improve, clean up, or set up project documentation without details, run the full documentation workflow from a read-only scan; do not ask the user to provide a long prompt.
- Inspect the repository read-only before proposing documentation changes.
- Ask when the project goal, documentation ownership, or target file is unclear.
- In generated `AGENTS.md`, make conversation-only the default for questions, analysis, brainstorming, and project discussion; require explicit user intent before edits.
- Never overwrite an existing `AGENTS.md` or docs file without explicit user approval.
- Preserve project-specific rules and edit existing files surgically.
- Classify the project profile before choosing which docs to create.
- Create only documentation files that the project needs now.
- When creating a project documentation system, always include `docs/code_rules.md` and route `AGENTS.md` to it for code and code-adjacent edits.
- Distinguish initial documentation creation from ongoing documentation maintenance: create or migrate docs only with user intent, but once a docs system exists, encode the selected maintenance mode in `AGENTS.md` and `docs/code_rules.md`.
- Never leave documentation maintenance mode as a placeholder in generated files; write the selected mode explicitly.
- Treat project-memory docs as local-only by default: add them to `.gitignore` or the repo's VCS ignore file, and do not commit, push, upload, publish, or deploy them unless the user explicitly asks.
- If existing docs are present, ask what to do with them before rewriting, deleting, or moving them; when the user delegates the decision, use those docs as project context and migrate durable facts into the skill's documentation structure.
- For existing docs, show a short proposed docs map before editing: current docs, topic owners, and planned changes.
- Update docs in later tasks only when durable project behavior, architecture, setup, deployment, staging, test data, SSH access, import/export flow, public URLs, WordPress setup, operator workflow, data model, public interfaces, agent workflow, or documentation ownership changes; do not add routine notes or restate obvious edits.
- Put unknown facts as `TODO: clarify`; do not invent project facts.
- Use the bundled questionnaire for broad unclear decisions or many options.
- Verify links and stale references after changing documentation.

## Mandatory Decision Gates

- For a broad short prompt, include all missing decisions in the normal workflow instead of asking the user to rewrite the request. Use the bundled questionnaire when there are more than two decisions.
- After the initial read-only scan, if any existing docs, README files, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.cursor/`, `.cursorrules`, or other project instruction files exist and the user's prompt did not explicitly delegate cleanup decisions, stop and ask which strategy to use before proposing edits or changing files.
- The strategy question must offer these choices: keep as-is, audit only, migrate after approval, or let the agent decide.
- Continue without this question only when the user already clearly said to decide autonomously, migrate everything, or skip questions.
- Before creating a new documentation system or replacing root agent instructions, ask for a documentation maintenance mode unless the user already specified it:
  - automatic durable maintenance: after completed code or code-adjacent work, update the relevant durable docs in the same task when the work changes durable project knowledge;
  - request-only maintenance: update docs only when the user explicitly asks, but mention when docs may now be stale.
- If the user asks for a recommendation, choose automatic durable maintenance for repositories with an established docs system, and request-only maintenance for throwaway prototypes or repos where docs are intentionally not tracked.
- If more than two questions are needed, use the bundled questionnaire instead of asking a numbered list in chat; otherwise ask the one or two questions directly.

## Reference Files

- Read `references/doc-map.md` before deciding which docs should exist or where information belongs.
- Read `references/file-templates.md` before creating new `AGENTS.md` or `docs/*.md` files.
- Read `references/audit-checklist.md` before auditing an existing repository.
- Read `references/cleanup-rules.md` before splitting, merging, deleting, or renaming documentation.
- Read `references/question_schema.md` before creating a questionnaire JSON.

## Bundled Questionnaire

Use the bundled questionnaire instead of long numbered chat questions when profile, scope, language, ownership, or overwrite decisions require more than two answers.

For broad short prompts, the questionnaire should normally include:

- documentation cleanup strategy for existing docs;
- documentation maintenance mode;
- project profile and primary workflow;
- whether project-memory docs should stay local-only or be tracked/published;
- any unclear profile-specific docs such as deployment, admin, security, API, integrations, content, product, or design.

1. Create `.context-cartographer-questionnaire/questions.json` in the target project using `references/question_schema.md`.
2. Back up existing `.context-cartographer-questionnaire/answers.json` or `answers.md` before overwriting questionnaire files.
3. Run `python3 <this-skill>/scripts/questionnaire_server.py --input .context-cartographer-questionnaire/questions.json --out-dir .context-cartographer-questionnaire --port 0`.
4. Give the user the printed `http://127.0.0.1:<port>/` URL and ask them to save the form and say `готово` or equivalent.
5. After completion, read `.context-cartographer-questionnaire/answers.json` and `.context-cartographer-questionnaire/answers.md`, summarize decisions, then continue.
6. If local Python or browser access is unavailable, ask up to three concise chat questions instead.

Questionnaires must bind only to `127.0.0.1`, avoid external dependencies, include "Other/custom" and "Not sure/recommend" options when useful, and never ask for secrets or private keys.

## New Project Workflow

1. Inspect the initial project structure and existing files.
2. Identify project profile, stack, audience, language policy, whether the user requested automatic setup, and the documentation maintenance mode.
3. Ask concise questions if core facts are missing; use the bundled questionnaire for multi-question decisions.
4. Create a short root `AGENTS.md` router only when absent or explicitly approved.
5. Create `docs/architecture.md` as the documentation map.
6. Create the full minimal core docs, including `docs/code_rules.md`, plus only the profile docs that match the project; do not create every possible file.
7. Add created project-memory docs to `.gitignore` or the repo's VCS ignore file unless the user explicitly wants them tracked.
8. Link all created docs from `docs/architecture.md`.
9. Report what was created and what still needs clarification.

## Existing Project Workflow

1. List files with `rg --files` and targeted reads.
2. Detect existing `AGENTS.md`, `docs/`, README files, architecture docs, product/design/deployment docs, and content docs.
3. Identify stale references, duplicated facts, oversized docs, missing owners, and files outside the expected documentation structure.
4. If existing docs or instruction files are present and the prompt did not explicitly delegate cleanup decisions, stop and ask how to handle them: keep as-is, audit only, migrate after approval, or let the agent decide.
5. If the user chooses "let the agent decide", read existing docs as project context, preserve durable facts, resolve conflicts with `TODO: clarify` or questions, and migrate docs into this skill's minimal-core/profile-based structure.
6. If the project has or is getting a docs system, ensure `docs/code_rules.md` exists or propose adding it.
7. If root agent instructions do not state a documentation maintenance mode, ask for one before updating them unless the user delegated the decision.
8. Show a proposed docs map before changing existing docs: list current docs, topic owners, and the exact planned create/update/delete actions.
9. Ensure project-memory docs are ignored by VCS; if `docs/` is public/user-facing, ask before adding broad ignore patterns.
10. Ask before deleting, merging, renaming, or heavily rewriting docs unless the user already delegated docs cleanup decisions to the agent.
11. Apply approved edits narrowly.
12. Check changed links and old filenames with `rg`.

## Cleanup Workflow

Use cleanup mode when docs are too large, duplicated, stale, or mixed by topic.

1. Classify each Markdown file by project profile and owner: agent router, architecture, product, design, deployment, security, API, integrations, admin, content/SEO, advertising, glossary, temporary, public repo docs, or obsolete.
2. Move only durable, non-duplicated facts into the correct owner file.
3. Keep `docs/architecture.md` as a concise map with links and summaries.
4. Ask before creating a new owner file when no suitable destination exists.
5. Delete obsolete files only after explicit user approval.
6. Verify that removed filenames are no longer referenced.

## Documentation Defaults

- Store Markdown documentation in `docs/`, except root `AGENTS.md`.
- Do not move public repo docs such as `README.md`, `LICENSE`, `CONTRIBUTING.md`, changelogs, or user-facing content into `docs/` automatically.
- Keep project-memory docs local-only by default; do not commit, push, upload, publish, or deploy them without explicit user approval.
- Keep project docs in English by default.
- Keep another language only for UI copy, brand terms, legal/user-facing text, campaign keywords, content examples, or domain terms.
- Treat `docs/architecture-frontend.md`, `docs/PRODUCT.md`, `docs/DESIGN.md`, and `docs/DEPLOYMENT.md` as profile-based docs, not universal core docs.
- Treat `docs/SECURITY.md` as conditional: create it only for auth, payments, PII, production access, external tokens, or secret-handling needs.
- Allow automatic docs creation for empty projects only when the user explicitly asks for it.
- Do not treat the "explicit request before edits" rule as blocking automatic durable documentation maintenance after the user has already asked for code, infrastructure, deployment, or operator-workflow changes and selected automatic durable maintenance.

## Exit Criteria

After documentation changes, report:

- files created or changed;
- links or stale references checked;
- ignore rules checked or updated for local-only docs;
- verification commands run;
- checks not run and why.
