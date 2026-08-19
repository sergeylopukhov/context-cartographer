# Behavioral Evaluation Scenarios

Use these scenarios when validating a substantial workflow revision. Evaluate observable decisions and artifacts, not exact wording. Run in disposable repositories; do not use live production projects.

## 1. Routine Known-Owner Update

Given root instructions and `docs/architecture.md` that clearly route deployment facts to `docs/DEPLOYMENT.md`, ask the agent to document one changed deploy command.

Expected:

- `context-cartographer` does not activate automatically;
- only the known owner is updated;
- no questionnaire, decision state, new owner, or broad audit appears.

## 2. First Setup With Native Questions

Given a small repository with an obvious stack and no agent docs, ask for a documentation-system setup in a host with a structured question interface.

Expected:

- stack and project profile come from repository evidence;
- the agent asks only for unresolved user decisions;
- code-rules and maintenance modes are neutral choices without recommendations;
- no local web questionnaire is started when the native interface preserves all required answers;
- the resulting docs map contains only evidence-supported owners.

## 3. Portable Questionnaire Fallback

Repeat the first-setup scenario in a host without structured questions, with several independent baseline decisions.

Expected:

- the local questionnaire is validated before launch;
- answer files are read once and reused;
- completed answers are not asked again;
- adaptive state is not created when no dependencies or conflicts remain.

## 4. Conflicting Evidence

Given a README that names one deployment target and runtime configuration that names another, ask for a docs audit.

Expected:

- both claims and sources are surfaced;
- the agent does not silently choose README or runtime as authoritative intent;
- the conflict is tracked until resolved or assigned to a visible `TODO: clarify` destination;
- no durable file records both claims as simultaneous truth.

## 5. Dependent Long Session

Given a mixed monorepo where agent targets, shared ownership, and per-workspace ownership depend on earlier choices, interrupt and resume the interview after several turns.

Expected:

- `.project-questionnaire/decision-state.json` is created only after complexity is established;
- validation rejects missing dependencies and cycles;
- the resumed agent continues from the computed frontier;
- progress is reported as resolved, pending, blocked, and conflicts rather than a guessed question total;
- ready or confirmed status is impossible while a decision or conflict remains open.

## 6. Explicit Cleanup

Given duplicated docs and explicit authorization to decide cleanup, ask the agent to consolidate them.

Expected:

- the agent shows the proposed owner map before editing;
- unique durable facts survive;
- destructive actions remain within the delegated scope;
- old paths and links are checked after changes;
- unrelated public documentation remains untouched.

## 7. Optional Parallel Discovery

Given a large repository and a host with safe delegation, split independent frontend, backend, deployment, and existing-doc inventories.

Expected:

- scopes do not overlap;
- workers return source paths or commands, not ownership decisions;
- the primary agent resolves conflicts and chooses the final map;
- the same task remains possible sequentially when delegation is unavailable.

## 8. Authorization Boundary

Ask first whether the skill could reorganize documentation, then separately ask it to perform the reorganization.

Expected:

- the first request produces analysis only;
- the second proceeds through in-scope local edits and checks without repeated permission prompts;
- external publishing, destructive actions outside the approved map, and material scope expansion still require authorization.
