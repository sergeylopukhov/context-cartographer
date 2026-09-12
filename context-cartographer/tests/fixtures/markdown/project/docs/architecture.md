<!-- context-cartographer: format_version=1 -->

# Architecture Map

Documentation map for the fixture project.

## Scope

| Kind | Path | Notes |
| --- | --- | --- |
| root | `AGENTS.md` | Codex root instruction router |
| include | `docs/` | documentation area |
| exclude | `docs/private/` | local-only notes |
| exclude | `node_modules/` | dependencies |

## Topic Map

| Topic ID | Purpose | Owner | Read when |
| --- | --- | --- | --- |
| deployment.rollback | Restore the previous release | [Rollback](deploy.md#rollback) | Changing release or recovery procedures |
| deployment.rollback | Duplicate row kept on purpose | [Deploy](deploy.md) | Reading deployment docs |
| deployment.backup | Back up the database before a release | [Rollback](deploy.md#rollback) | Preparing a release |
| guide.reading | How to read a section | [Reading](guide.md#reading) | Learning the section reader |
| topic.without-owner | A topic with no owner yet |  | Adding a new owner |

## Dependencies

| Topic ID | Depends on | Reason |
| --- | --- | --- |
| deployment.rollback | deployment.backup, guide.reading | Rollback needs a restore point |
