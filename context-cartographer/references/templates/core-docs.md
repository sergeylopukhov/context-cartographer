# Core Document Templates

Use these templates for the minimal core owners. Read `references/doc-map.md` for the profile decision and `references/templates/documentation-rules.md` for the maintenance contract.

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

## Notes For The Skill

- Fill `TODO: clarify` with repository evidence, not with invented facts. Leave the marker when a durable fact is genuinely unknown and no one can confirm it yet.
- Keep the core concise; split a topic out only when it becomes substantial enough for its own owner.
