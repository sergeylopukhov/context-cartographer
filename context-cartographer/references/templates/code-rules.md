# Code Rules Template

Use this template only when the user selected code-rules mode. When code-rules mode is `do not use code rules file`, do not create `docs/code_rules.md` and do not route agents to it.

The file records the project's own choice. A generated root adapter states `use code rules file` or `do not use code rules file`; it never leaves the mode implicit.

```markdown
# Code Rules

Create this file only when code-rules mode is `use code rules file`. When code-rules mode is `do not use code rules file`, this file does not exist and no agent is routed here.

Behavioral guidelines for agentic coding workflows. Merge with project-specific instructions as needed.

Read this file before changing code or code-adjacent project files such as tests, migrations, scripts, build config, deployment config, or application behavior.

These rules bias toward small, verified, reversible changes. For trivial tasks, use judgment, but do not skip explicit user intent, context checks, or verification.

## 1. Respect Intent And Scope

Discussion is not permission to edit.

- For an informational question, inspect and report without changing files. When the user asks to create, save, or update an artifact, including a plan or a document, that request is the work and not a read-only question.
- For explicit change, build, fix, create, update, or apply requests, complete the authorized in-scope local work and relevant non-destructive checks without asking again.
- Ask only when a missing user decision changes the result, or before a destructive, external, costly, or materially scope-expanding action.
- State meaningful assumptions when they affect implementation.

## 2. Curate Context First

Use just enough context for the next step.

- Read the nearest project instructions and the files directly involved in the change.
- Prefer `rg`, targeted file reads, tests, types, schemas, and existing patterns over broad repository scans.
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
- Do not add tests just to satisfy process when the repository has no test pattern and the change is trivial.
- If a check fails, investigate and fix within the task scope.
- If a check cannot run, report why and give the best available substitute.

## 6. Security And Operations Guardrails

- Never write secrets, tokens, private keys, production credentials, or private user data into code, docs, logs, tests, or chat.
- Add dependencies, change lockfiles, migrations, or deployment configuration only when the requested outcome requires them; ask when the choice materially expands scope or operational risk.
- Require explicit authorization before deleting data or changing a production-like system.
- Preserve permission boundaries and existing access-control checks unless the user explicitly asks to change them.
- Prefer reversible changes and document rollback or recovery steps for risky operations.

## 7. Durable Documentation

- Documentation maintenance mode: TODO: replace with the mode selected in the root agent instructions before writing this file.
- Under `automatic durable maintenance`, after completed work that changes setup, architecture, deployment, staging, test data, the data model, public interfaces, the operator workflow, the agent workflow, or documentation ownership, check whether an owner document must be updated, and update it in the same task before the final response.
- Under `request-only maintenance`, update docs only when the user explicitly asks, but mention when completed work likely made docs stale.
- Follow the [documentation rules](documentation-rules.md) for owner selection, links, and checks. For ordinary maintenance with a known owner, the local project instructions and existing owner documents suffice; do not invoke `context-cartographer`.
- If no existing owner fits under `automatic durable maintenance`, create the smallest justified owner and register it in `docs/architecture.md`, without asking merely for permission to create a Markdown file and without invoking the skill.
- Do not record routine implementation notes, transient task status, or obvious edits.

## 8. Finish With Evidence

At the end of a code or code-adjacent task, report only what matters:

- files changed;
- checks run and results;
- checks not run and why;
- known follow-up risks, if any.

These guidelines are working when diffs are small, intent is clear before edits, verification is explicit, unrelated code stays untouched, and documentation changes only when they preserve durable project knowledge.
```

## Notes For The Skill

- Resolve both branches explicitly when writing a root adapter: `use code rules file` or `do not use code rules file`. Do not recommend one branch over the other.
- Keep this file out of projects that selected `do not use code rules file`, and do not add a routing line to it in that case.
