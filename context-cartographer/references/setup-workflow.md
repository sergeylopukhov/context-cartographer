# New Documentation System Workflow

Use this workflow for first-time documentation setup or a broad request to create a complete agent-facing documentation system.

## Required Inputs

Resolve these decisions before writing root instructions or project-memory docs:

- agent target: Codex, Claude Code, Cursor, or selected multi-agent targets;
- code-rules mode: use `docs/code_rules.md` or do not use it;
- documentation maintenance mode: `automatic durable maintenance` or `request-only maintenance`;
- project profile and primary workflow;
- language policy;
- whether project-memory docs remain local-only or are tracked;
- any profile-specific needs such as deployment, admin, security, API, integrations, content, product, or design.

Do not infer code-rules mode or documentation maintenance mode. Both are blocking decisions without defaults.

Choose the least disruptive question interface that preserves the required decisions. Ask one blocking decision directly, use a suitable native structured-input tool for a small independent set, or use the bundled questionnaire from `question_schema.md` for a broad independent baseline or cross-client fallback. Match the question language to the user or project language.

If answers depend on earlier decisions, conflict with repository evidence, or leave material terminology or ownership ambiguity, read `decision-discovery.md` and run its adaptive workflow. Do not force a fixed questionnaire merely because several fields are missing.

## Before The Questionnaire

Classify the starting folder before asking for decisions, so a documentation questionnaire does not run before the user's idea is heard. Run `scripts/project_probe.py --root PATH --json`. If the folder is `empty` or only a `scaffold`, and the user has not described an idea, read `idea-to-project.md` and make the idea offer first. Two exceptions keep this from overriding the user: do not make the idea offer when the user asked only for documentation, or when they already declined idea work; in those cases do the requested documentation work directly. The required decisions above are needed when root instructions are actually created, which is not the same as starting a conversation about a new project.

The full minimal core belongs to a project that needs a documentation system. When the user only wants to discuss an idea, or wants a single saved brief, follow `idea-to-project.md` and `templates/idea-docs.md` instead of this setup sequence.

## Read-Only Discovery

1. Resolve the project root.
2. Run `rg --files` from that root, and include managed documents that Git ignores but the map declares as in scope.
3. Ignore dependency, cache, generated, vendor, and build directories unless they are directly relevant.
4. Identify the stack, entry points, project profile, public interfaces, deployment or release flow, security-sensitive areas, integrations, and operator workflows. When safe delegation is available, independent read-only areas may be inspected in parallel; give each worker a distinct scope and synthesize the evidence in the primary agent.
5. Inventory existing `AGENTS.md`, `CLAUDE.md`, Cursor rules, README files, docs, ignore rules, and public documentation.
6. Reuse files already read during the task. Reread only changed files, truncated output, or a specific unread range.

If any existing instruction or documentation files are present, do not silently replace them. Resolve whether to keep them, audit only, migrate after approval, or let the agent decide.

## Required References

Read:

- `doc-map.md` to choose the minimal core, project profile, topic owners, and conditional files;
- `documentation-format.md` before writing `docs/architecture.md`, its scope table, or its topic table;
- `file-templates.md` before creating root instructions or any `docs/*.md`, then open only the templates it routes to;
- `documentation-graph.md` before building, checking, or describing the graph helper and precise section reading;
- `question_schema.md` when a questionnaire is required;
- `decision-discovery.md` when decisions are dependent, conflicting, or complex enough to need resumable state.

Read profile-specific source files from the project before documenting them. Mark unknown durable facts as `TODO: clarify`.

## Creation Sequence

1. Create or surgically update only the root instruction files selected for the target agents. Keep them thin: they route to the map and the maintenance contract with real Markdown links instead of repeating them, and each states one concrete maintenance mode and one concrete code-rules mode.
2. Create `docs/architecture.md` as a concise documentation map with the format marker, a scope table listing only roots and areas that exist, a topic table whose `Owner` cells are real Markdown links, and an explicit dependency table that may be empty.
3. Create `docs/documentation-rules.md` with the self-sufficient maintenance contract from `templates/documentation-rules.md`. It carries the owner rules, link rules, section-reading order, check commands, and privacy policy, so ordinary maintenance does not need the skill.
4. Create the minimal core from `doc-map.md` and `templates/core-docs.md`.
5. Create `docs/code_rules.md` only when code-rules mode is enabled.
6. Add only profile and conditional files supported by repository evidence or explicit user intent.
7. Register every created owner in the topic table of `docs/architecture.md`. Keep the `Topic ID` stable when a heading or file is renamed.
8. Encode the selected agent target, code-rules mode, and documentation maintenance mode in every root instruction file and in the map.
9. Under `automatic durable maintenance`, require later tasks to update the existing owner document directly in the same task when durable project knowledge changes, and to create the smallest justified owner when no owner fits, without invoking the skill merely to create a Markdown file.
10. Require later agents to invoke `context-cartographer` only when ownership is genuinely unclear, a migration or restructuring is nontrivial, or the user asks.
11. Add local project-memory files and the derived `.context-cartographer/` graph directory to the repository ignore rules with precise patterns unless the user explicitly wants them tracked.
12. Build the graph once with `documentation-graph.md` and `--write`, and report its result.

## Link And Routing Rules

Apply these while creating owners so the map and the documents agree:

- A Markdown link resolves relative to the file that contains it, not relative to the project root. Choose the narrowest sufficient address.
- Link to another owner only when the reader actually needs that section: a rule, decision, procedure, prerequisite, or constraint. Do not link every term mention and do not add generic "See also" blocks.
- Keep one canonical owner for a topic. Replace repeated durable text with a link to the canonical section.
- Take `depends_on` only from the explicit dependency table, never from a plain link or a similar name.

## Quality Gates

Before finishing:

- confirm every durable topic has exactly one owner, and every created owner is registered in `docs/architecture.md`;
- confirm root instructions are short routers that link to the map and the maintenance contract with parsed Markdown links, state one concrete mode each, and do not copy the contract;
- confirm `docs/documentation-rules.md` exists and is routed from each root adapter, together with the map;
- confirm no profile file was created without evidence;
- confirm automatic maintenance works from the local rules without loading the skill;
- confirm an obvious new owner can be created from the local rules, and genuinely unclear ownership routes to `context-cartographer`;
- confirm unknowns are marked rather than invented;
- confirm project-memory files and `.context-cartographer/` are ignored with precise patterns;
- check stale filenames and broken links with `rg`, and check the addresses with the documentation helper;
- report files created, decisions applied, verification performed, and unresolved TODOs.
