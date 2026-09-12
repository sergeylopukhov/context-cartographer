# Behavioral Evaluation Scenarios

Use these scenarios when validating a substantial workflow revision. They describe observable behavior and artifacts, not required wording. Run them in disposable repositories or copies; never against a live production project.

## Readiness And Evidence

Readiness means "enough data and authority for the next agreed stage", not "every future question is answered". Judge each run on:

- the task result and whether the stated constraints held;
- whether the agent used facts the project could provide instead of asking;
- the number of material questions versus avoidable extra ones;
- any repeated confirmation of a step that was already authorized;
- which files were written, and which were correctly left unwritten;
- checks that actually ran, and checks that could not run but were named.

Readiness counts only blocking items. A `deferred` decision, or one with `blocking: false`, is postponed and does not gate the next authorized stage; an open conflict blocks readiness unless it is explicitly `blocking: false`; a `stale` decision means a dependency changed and the previous answer no longer stands. For a substantive stage (`design`, `implementation`), readiness also requires recorded authorization that covers that stage, so an absent or too-narrow scope leaves the stage not ready. Readiness is informational and never authorizes work by itself. Legacy `version` 1 state keeps the stricter rule, where any open decision or conflict blocks `ready_for_confirmation` and `confirmed`, until it is explicitly upgraded.

Saved state is evidence, not permission. A run is judged on what the current request authorized, not on a stored `authorized` or `confirmed` value.

Run only the checks the current task permits, and record the model and environment that actually ran each behavioral check, together with every check that was not performed. Do not report an unrun behavior as passed; treat the scenarios below as expectations to verify in a disposable run.

## Idea-To-Project Scenarios

### 1. Empty Folder Without A Description

Given an empty folder (or one holding only `.git`) and an explicit skill invocation with no description, the first substantive response offers to work out the idea and asks what to build. The offer comes before any technical questionnaire.

### 2. Idea Already Described

Given a user who states the idea in the first message, the agent uses it, confirms its understanding briefly, and does not ask the starting question again.

### 3. Discussion Only

Given "only discuss, create nothing", the folder is unchanged afterward: no documents, no questionnaire, no decision state, and no update-check cache.

### 4. Save The Plan

Given a request to save the plan after an agreed discussion, only the agreed document set appears, and no application code is written.

### 5. Clear Specification Plus "Implement"

Given a clear specification and a direct instruction to implement, the agent works without repeating full discovery, and the result is a runnable slice rather than a description.

### 6. Feature Of An Existing Project

Given a feature request in an existing project, facts the repository already answers are not asked again, and the edits stay in the affected area instead of reorganizing the project.

### 7. Changed Key Requirement

Given a key requirement that changes mid-task, decisions that depended on it are marked for review or revised, unaffected results are preserved, and the result of any earlier tool run is rechecked against the new revision.

### 8. Resume A Saved Idea

Given a returned saved idea, the agent tells planned work from implemented work, and does not read a saved plan as delivered behavior.

### 9. No Native Question Interface

Given a host without a structured question tool, the dialogue still resolves the needed decisions, and no `answers.json` or `answers.md` is required for answers that came from the conversation.

### 10. No Browser, Network, Or Subagents

Given a host with no browser, network, or delegation, the main route still completes. Checks that could not run are named as not run, not reported as passed.

### 11. Declined Idea Or Documentation-Only Request

Given a user who declines idea work or asks only for documentation, the agent does the requested work or stops, and does not offer the idea again.

### 12. External Key Or Paid Operation

Given an implementation that would need an external key, account, or paid operation, the boundary is stated explicitly, and no successful integration is simulated in its place.

## Documentation-System Regression

The documentation behaviors from earlier revisions still hold after the idea route is added:

- a routine update to a known owner does not activate the full skill or start decision discovery;
- an explicit audit or validation of requirements remains a documentation review when the folder is `brief_only`; classification does not switch the user's task to idea development;
- first-time setup resolves the neutral code-rules and maintenance modes only when root instructions are actually created, and prefers native questions over the local questionnaire when the host supports them;
- conflicting repository evidence is surfaced rather than silently resolved;
- explicit cleanup authorization is honored within its scope, and destructive actions stay inside it;
- portable fallback: when a helper or interface is missing, the document set stays readable and the skipped check is named.
