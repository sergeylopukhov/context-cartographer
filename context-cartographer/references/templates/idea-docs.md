# Idea-Stage Document Templates

Compact shapes for the idea-to-project route. Use them only when a document is actually written; a conversation about an idea needs no files. Read `references/idea-to-project.md` for the route and `references/file-templates.md` for the documentation templates that apply once a project has a real documentation system.

These are maturity-stage owners, not the full documentation core. Do not attach the map, the graph, or the core owner set to a lone brief.

## Brief: `docs/idea-brief.md`

Write this only when the user asks to save the idea. It stays a record of what was agreed, with no invented architecture and no commands that were never run.

```markdown
# Idea Brief

## Problem

- Who it is for:
- The task it solves:

## First Version

- In scope:
- Out of scope:

## Key Decisions

- Decision: reason

## Open Questions

- Question: what it blocks

## Next Step

- The single next useful action
```

## Plan: `docs/implementation-plan.md`

Write this when the user asks for a plan. Mark everything not yet built as planned.

```markdown
# Implementation Plan

## Requirements

- Requirement:

## Boundaries

- In scope:
- Deliberately deferred:

## Acceptance Criteria

- Observable result and how it is checked:

## Sequence

1. Verifiable change
2. Verifiable change

## Status

- Planned: items not yet built
- Implemented: items with a real result
```

## Working Project

Once something runs, move the facts to the normal owners instead of extending a brief:

- actual architecture and entry points go to `docs/architecture-overview.md` or a profile owner;
- the commands that were really run, with their limits, go to `docs/architecture-quality-risks.md` or `docs/DEPLOYMENT.md`;
- the owner map and graph come from the documentation workflows when a related documentation system exists.

## Feature Of An Existing Project

- Update the existing owner for the affected topic.
- Create a new owner only when the feature introduces a genuinely new durable topic.
- Do not create a parallel document set for one feature.

## Notes

- `TODO: clarify` marks a durable fact nobody can confirm yet; never replace it with a guess.
- Keep the brief self-contained until a documentation system exists, then link it to the map rather than duplicating owners.
- A brief is a natural-language document. A language manifest such as `requirements.txt` or `package.json` is configuration and evidence of a project, not a brief; save a saved brief as a natural-language file such as `docs/idea-brief.md`, `spec.md`, or `requirements.md`.
