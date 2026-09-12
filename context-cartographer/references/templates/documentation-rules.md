# Documentation Rules Template

Use this template to create `docs/documentation-rules.md`, the canonical and self-sufficient maintenance contract for the project. Root adapters route here; this file does not depend on the `context-cartographer` skill being installed.

If the project keeps its documentation in another private directory, place this file there and use the real project-root-relative addresses.

```markdown
# Documentation Rules

<!-- context-cartographer: documentation-rules format_version=1 -->

This file is the canonical contract for creating, updating, linking, and checking project documentation. Read it before changing documentation, including ordinary edits, and follow it during ordinary maintenance.

It is self-sufficient: the [architecture map](architecture.md) lists topics and owners, and this file explains how to maintain them. The maintenance work does not require the `context-cartographer` skill.

## 1. Choose The Owner

- Keep durable knowledge in exactly one owner document. A durable fact is one a future task will need again: architecture, setup, deployment, data model, public interfaces, operator workflow, access rules, or agent workflow.
- Do not write routine task notes, transient status, or obvious implementation detail into owner documents.
- Find the owner first. Read the [architecture map](architecture.md), pick the topic by its `Topic ID`, and open the listed owner section. Search the whole repository only when the map has no matching topic.
- If two documents state the same durable fact, keep the clearest and most current statement in one owner and replace the other with a link. Do not leave two competing sources.

## 2. Update Or Create An Owner

- Prefer updating the existing owner over creating a new file.
- Create a new owner only when the topic is durable, will recur, and no existing owner can hold it without mixing responsibilities.
- Under automatic durable maintenance, when no existing owner fits, create the smallest justified owner and update `docs/architecture.md` directly, without asking merely for permission to create a Markdown file and without invoking the skill.
- Register every new owner in the topic table of `docs/architecture.md` as `Topic ID | Purpose | Owner | Read when`. Keep the `Topic ID` stable when a heading or file is renamed.
- Never create a parallel memory file such as `CONTEXT.md` or `CONTEXT-MAP.md`. Resolved knowledge belongs in the existing owner system.

## 3. Addresses And Links

- A Markdown link resolves relative to the file that contains it, not relative to the project root. A path that starts with `/` resolves from the project root.
- Use predictable anchors. Prefer the GitHub-style slug of the heading; add an explicit `<a id="...">` anchor when the heading is unstable or ambiguous, and verify the viewers used by the project support it.
- Add a link only when the reader actually needs to read that section: the owner holds a rule, decision, procedure, prerequisite, or constraint the current document depends on. Choose the narrowest sufficient address.
- Do not link every mention of a term, do not add mandatory back-links, and do not create generic "See also" blocks without a reading condition.
- The map distinguishes four relations: `routes_to` (a root file points to documentation), `owns_topic` (a document owns a topic), `references` (ordinary prose links), and `depends_on` (an explicit prerequisite from the dependency table). Take `depends_on` only from the explicit dependency table, never from a plain link, a similar name, or a repeated term.
- Ordinary link cycles are allowed. Report them as information, not as an error.

## 4. Renames And Inbound Links

- Before renaming a file or heading, find the incoming links from the documentation index or with a repository search.
- Fix the affected addresses in the same authorized change. Do not replace matching text across the whole project.
- When external documents use the old address, keep the previous explicit anchor when possible, or describe the migration.

## 5. Read Sections, Do Not Guess

1. Use the map to find the topic, its owner, and the reading condition.
2. With an exact address, read that section; otherwise list the headings first.
3. Read the section together with its parent headings, the introductory constraints, and any explicit prerequisites needed to understand it.
4. Decide whether that is enough for the task. When the topic is crosscutting, contradicts another owner, or has system-wide consequences, open the related sections and expand the reading.

- An ambiguous or missing anchor is an error with candidate suggestions. Do not silently substitute the first similar section.
- Reading a long document in full is allowed when a broad audit, a migration, or an end-to-end constraint check genuinely needs it. File size alone is not a reason to split a connected topic.
- This selective-reading rule never replaces mandatory instructions. Fully read the applicable `AGENTS.md`, `CLAUDE.md`, skill instructions, and environment rules when the platform requires it.
- If the documentation helper is unavailable, list headings with a repository search and read the matching range with normal file tools, checking code blocks and surrounding context. This is the fallback path, not a second anchor standard.

## 6. Check And Refresh The Graph

The helper is `scripts/documentation_graph.py` inside the installed skill. Run it with `python3` and an explicit project root, for example:

```text
python3 <skill>/scripts/documentation_graph.py --root . --check
python3 <skill>/scripts/documentation_graph.py --root . --write
python3 <skill>/scripts/documentation_graph.py --root . --outline docs/DEPLOYMENT.md
python3 <skill>/scripts/documentation_graph.py --root . --section docs/DEPLOYMENT.md#rollback
```

- `--check` changes nothing. It verifies addresses, owners, and reachable routes; `--require-graph` also requires a present and current local graph.
- `--write` rebuilds the offline graph and returns the same report. It writes the graph only when the inputs changed.
- `--json` changes the representation, not the meaning. `--map PATH` overrides the default `docs/architecture.md`.
- Exit codes: `0` means the check ran without documentation errors, `1` means documentation errors exist, `2` means a bad invocation or an impossible check.
- The graph is a derived local artifact at `.context-cartographer/documentation-graph.html`. Markdown owners remain the source of truth; never edit the graph instead of the document.
- Under automatic durable maintenance, rebuild the graph once after the agreed set of documentation changes, and report any remaining errors without claiming the graph is correct.
- Under request-only maintenance, do not change documents or the graph without a request; when a relevant change happens, say that the graph may be stale.
- If the helper or its index module is missing, report the automatic check as not run and use the fallback. Do not claim a passed check and do not copy the whole skill into the project.

## 7. Privacy And Ignore Policy

- Treat project-memory documentation as local-only unless the user explicitly asks to track or publish it.
- Add precise ignore patterns. Ignore the generated graph directory `.context-cartographer/` and any private documentation directory; do not ignore all of `docs/` when `docs/` is a public site, package documentation, or user-facing content.
- An existing tracked private file is not removed by a new ignore rule. Check tracked files as well as the ignore rule.
- Never write secrets, tokens, private keys, or production credentials into documentation or the graph.

## 8. Durable Change Coverage

Under automatic durable maintenance, update the matching owner in the same task when completed work changes durable behavior, including:

- setup, architecture, or deployment;
- staging, test data, or access rules;
- the data model or storage layout;
- public interfaces or API contracts;
- operator and agent workflow;
- documentation ownership or the documentation set itself.

Update an owner only when a durable fact actually changed; routine task notes belong outside the durable documentation.

## 9. Local Rules Or The Full Skill

For ordinary maintenance with a known owner, the local project instructions and existing owner documents suffice; do not invoke `context-cartographer`.

Invoke `context-cartographer` only for first-time setup, a nontrivial migration or restructuring, genuinely unclear ownership, a real conflict between owners, a mass rename, or an explicit user request. When the structure is unclear, the full skill audits the map instead of guessing.

## 10. Update This Contract

This file declares its format with `<!-- context-cartographer: documentation-rules format_version=1 -->`. When the skill proposes a newer contract, compare versions and migrate only the needed part within the authorized work. Do not overwrite project-specific additions with the template.
```

## Notes For The Skill

- Fill the project language and any project-specific owners before writing the file. Remove this notes section from the generated document.
- Keep the version marker line intact; it lets a future skill version detect an older contract without checking the network.
