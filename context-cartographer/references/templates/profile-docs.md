# Profile Document Templates

Use these templates only when the project profile or repository evidence supports the file. Read `references/doc-map.md` for the profile rules. After creating an owner, register it in the topic table of `docs/architecture.md` and follow `docs/documentation-rules.md` for links and checks.

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
