# Cleanup Rules

Use this file when documentation is too large, duplicated, stale, or mixed by topic.

## Profile-Aware Cleanup

Before moving or creating docs, identify the project profile. Do not force every project into a UI/SaaS documentation shape.

- When existing documentation is present and the prompt did not explicitly delegate cleanup decisions, stop after the read-only scan and ask whether to keep it as-is, audit only, migrate after approval, or let the agent decide.
- If the user delegates the decision to the agent, use existing docs as project context and migrate durable facts into the minimal-core/profile-based structure from this skill.
- For non-UI projects, do not create `docs/architecture-frontend.md` or `docs/DESIGN.md` unless a real UI/admin/mobile surface exists.
- For libraries, CLIs, bots, automations, APIs, data/ML, and infra repos, keep docs focused on runtime, interfaces, operations, integrations, and risks.
- Keep public repo docs such as `README.md`, `LICENSE`, `CONTRIBUTING.md`, changelogs, examples, and user-facing content in their conventional locations unless the user explicitly asks to move them.
- Do not move user-facing content, blog posts, docs-site pages, or SEO pages into project-memory `docs/` merely because they are Markdown.
- Keep project-memory docs local-only and ignored by VCS unless the user explicitly asks to track, publish, upload, or deploy them.
- Do not add a broad `docs/` ignore rule when `docs/` is a public docs site, package docs, or user-facing content folder; ask or use precise patterns.

## Split Oversized Docs

Split a large documentation file when it mixes stable topics such as architecture, product, design, deployment, security, API, advertising, and content.

Process:

1. Read headings and link references first.
2. Confirm the user-approved strategy for existing docs, or proceed only if the user delegated docs cleanup decisions to the agent.
3. Create a topic map before moving content.
4. Move each fact to one owner file only.
5. Replace the old large file with a concise index if it remains useful.
6. Preserve important wording when it carries project-specific meaning.
7. Check links and old filenames after the split.

Prefer these architecture owners:

- `docs/architecture.md`: index, reading rules, ownership rules.
- `docs/architecture-overview.md`: stack, folders, boundaries.
- `docs/architecture-frontend.md`: UI implementation, only when a UI surface exists.
- `docs/architecture-backend-data.md`: backend, runtime, automation, pipeline, service, and data model.
- `docs/architecture-quality-risks.md`: tests, risks, fragile areas.
- Domain-specific architecture files only when the topic is substantial, such as payments or integrations.

## Merge Duplicate Docs

Merge documentation when several files repeat the same durable facts.

Rules:

- Keep the clearest and most current fact.
- Move facts into the most specific owner file.
- Replace broad repeated text with a link when a reminder is still useful.
- Do not merge temporary notes into durable docs unless they contain still-valid decisions.
- If two facts conflict, preserve neither as truth; mark the conflict as `TODO: clarify` or ask the user.

## Delete Or Rename Docs

Ask for explicit approval before deleting or renaming docs unless the user directly requested that exact deletion or rename.

Before deletion:

- verify the file is obsolete, generated, duplicated, or temporary;
- move durable unique facts to the correct owner file;
- check inbound references with `rg`;
- update any docs map or index.

After deletion:

- run `rg` for the removed filename;
- verify links from `docs/architecture.md`;
- report what was removed and where important facts moved.

## New Owner Files

Ask before creating a new documentation owner file when:

- no existing owner file fits;
- the topic is temporary or one-off;
- the new file would overlap with an existing owner;
- the project does not yet have a docs structure.

Create a new owner file when:

- the topic is durable;
- several future tasks will need it;
- putting it elsewhere would create noise or duplication;
- the user approves the new owner.

## What Not To Do

- Do not create `README.md`, `CHANGELOG.md`, or extra guide files inside a skill unless explicitly required.
- Do not turn root agent instruction files such as `AGENTS.md`, `CLAUDE.md`, or Cursor rules into full project manuals.
- Do not keep long checklists in `docs/architecture.md`.
- Do not move public repo docs or user-facing content files into `docs/` merely because they are Markdown.
- Do not document secrets, private keys, tokens, or production credentials.
- Do not commit, push, upload, publish, or deploy project-memory docs unless explicitly requested.
