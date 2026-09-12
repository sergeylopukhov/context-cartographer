# Adaptive Decision Discovery

Use this workflow only when documentation setup, restructuring, or ownership resolution contains several dependent user decisions, ambiguous terminology, or conflicting evidence. Skip it when repository evidence and the user's request already determine the documentation map.

This is an interview layer inside `context-cartographer`, not a separate skill and not a second documentation system.

## Principles

- Separate facts from decisions. Inspect the repository, existing docs, configuration, and available runtime evidence for facts; do not ask the user what the project can answer.
- When safe delegation is available, independent fact-finding may run in parallel. Give each worker a distinct read-only scope, require source paths or commands, and synthesize the result in the primary agent. Never delegate user decisions or final ownership selection.
- Treat user intent, trade-offs, priorities, and authorization boundaries as decisions. Do not infer them from code.
- Resolve prerequisites before dependent decisions. Recompute the open frontier after every meaningful answer or new fact.
- Challenge vague terms, contradictions, and hidden assumptions with a concrete example or edge case.
- Recommend a practical answer when evidence supports one. Do not recommend an answer for the required `code-rules mode` or `documentation maintenance mode` choices; those remain neutral user decisions.
- Never create `CONTEXT.md`, `CONTEXT-MAP.md`, or another parallel source of truth. Resolved knowledge goes to the existing owner system selected through `doc-map.md`.
- Do not implement project code or mutate project documentation merely because the interview is complete. Continue only within the user's authorized documentation task.

## Entry Criteria

Use adaptive discovery when at least one is true:

- unresolved decisions have dependencies that make a flat questionnaire misleading;
- questionnaire answers expose contradictions or important custom answers;
- existing docs and repository evidence disagree about a durable fact;
- terminology changes the owner map, project boundaries, or user-facing behavior;
- a high-cost or difficult-to-reverse documentation or architecture choice remains open.

Do not use it merely because a setup questionnaire has more than two independent fields. A single validated questionnaire is sufficient when its answers are complete and consistent.

## Workflow

1. Complete read-only discovery before asking for facts.
2. Classify every unresolved item as a verified fact, uncertain fact, user decision, conflict, or out-of-scope item.
3. Collect independent baseline choices through the best available structured interface. Prefer a native question UI when it can preserve the needed options and custom answers; otherwise use the bundled questionnaire.
4. Use the answers from their real source. When the bundled questionnaire was used, read `answers.json` and `answers.md`. When the answers came from a native structured-input tool or the conversation, use them directly and do not require `answers.json` or `answers.md` to exist. Build `.project-questionnaire/decision-state.json` only if dependent decisions or conflicts remain.
5. Validate the state before using it:

   ```bash
   python3 <this-skill>/scripts/decision_state.py \
     --input .project-questionnaire/decision-state.json \
     --validate-only
   ```

6. Inspect the current frontier:

   ```bash
   python3 <this-skill>/scripts/decision_state.py \
     --input .project-questionnaire/decision-state.json \
     --json
   ```

7. Ask one frontier decision at a time when its answer can reshape downstream choices. Batch genuinely independent frontier decisions through a suitable structured interface. Include the recommendation and its reason unless the decision is one of the two neutral modes above.
8. After each meaningful answer, update the state, record newly discovered dependencies or conflicts, and validate it again.
9. When an answer conflicts with evidence, show both claims and their sources. Ask which intended behavior should become authoritative; do not silently choose.
10. Before finishing, test important decisions with a concrete scenario. Add only scenarios that could change the documentation map or durable rule.
11. Set state to `ready_for_confirmation` only when every decision is resolved and every conflict is closed and a separate confirmation is still genuinely needed. Present a compact decision summary and the proposed documentation map.
12. Continue to documentation edits when the original request already authorizes the exact resulting changes. That authorization is the confirmation; do not ask again. Ask only when the interview materially changed the proposed scope, multiple valid maps remain, or a destructive action still needs authorization.
13. Set state to `confirmed` once the planned changes are authorized, whether by the original request or by a later explicit confirmation. Do not add a confirmation ceremony when the authorization already exists. Treat the state file as temporary local workflow state, never as a durable owner or publication artifact.

## State File

Store resumable state at `.project-questionnaire/decision-state.json`. The directory is local-only and ignored by default.

Minimal valid example:

```json
{
  "version": 1,
  "topic": "Project documentation setup",
  "status": "active",
  "facts": [
    {
      "id": "fact_stack",
      "statement": "The project is a Laravel application.",
      "source": "composer.json and artisan",
      "status": "verified"
    }
  ],
  "conflicts": [],
  "decisions": [
    {
      "id": "agent_target",
      "question": "Which coding agents should receive root instructions?",
      "status": "resolved",
      "depends_on": [],
      "conflicts": [],
      "recommendation": "Codex only, because no other agent configuration exists.",
      "answer": "Codex"
    },
    {
      "id": "code_rules_mode",
      "question": "Should this project use docs/code_rules.md?",
      "status": "pending",
      "depends_on": ["agent_target"],
      "conflicts": [],
      "recommendation": null,
      "answer": null
    }
  ],
  "out_of_scope": []
}
```

Allowed session statuses are `active`, `ready_for_confirmation`, and `confirmed`. Every *blocking* decision and every *blocking* conflict must be resolved before `ready_for_confirmation` or `confirmed`; a decision marked `blocking: false`, including one postponed with status `deferred`, does not gate that step, and neither does a conflict explicitly marked `blocking: false`. Decision statuses are `pending`, `resolved`, `blocked`, `stale`, and `deferred`. A blocked decision must include a non-empty `blocker`. A deferred decision must set `blocking: false` and carry no answer. A stale decision records that a dependency changed: its earlier answer moves to `previous_answers` and `answer` stays `null`, so a stale answer is never read as active. Facts are `verified`, `uncertain`, or `conflicting`; conflicts are `open` or `resolved` and resolved conflicts require a `resolution`. An open conflict is blocking unless it is explicitly marked `blocking: false`, so an unassigned disagreement is never silently downgraded.

The validator rejects duplicate IDs, missing dependency targets, dependency cycles, resolved items without answers, unresolved dependencies or open conflicts behind a resolved decision, a stale decision with an active answer, a deferred decision that is still blocking, malformed versions (including `true` in place of `1`), non-boolean `blocking` values, unknown source kinds, stages, or authority modes, and premature ready/confirmed status.

### Version 2 fields

Version `1` is the original schema and keeps its exact meaning, so existing state files stay readable; the validator accepts both versions. Version `2` adds:

- `source_kind`: `conversation`, `native`, `questionnaire`, `saved_document`, or `unknown` — where the answers actually came from. A migrated legacy file records `unknown` instead of guessing.
- `stage`: `idea`, `planned`, `implemented`, or `unknown` — so resuming a saved plan is not confused with delivered work.
- `authority`: `{mode, scope, evidence}`. `mode` is `discussion`, `design`, `implementation`, or `unknown`; `scope` lists the areas the authorization covers; `evidence` records the user's own words and must be non-empty whenever the mode is known. This is the authorization basis for the current work type and is deliberately separate from readiness. The check fails closed: an absent or empty scope never authorizes a requested item, and a substantive mode (`design` or `implementation`) needs a bounded recorded scope even when no particular item is named.
- `desired_state`: `[{id, statement, source?}]` — the intended outcome, kept apart from the observed `facts`.
- `blocking` (default `true`) and `previous_answers` on each decision, `blocking` (default `true`) on each conflict, plus an optional state-level `next_step` and its `previous_next_steps` archive.

`next_step` is either a non-empty string or an object `{step, revision?}` that pins the idea revision it was written for. A step pinned to an older revision is ignored, and `revise_decision` archives and clears the stored step whenever a decision meaning changes, so a superseded plan is never recommended over an open blocker.

Migrate in memory with `upgrade_state()` or `--upgrade-to-v2`; both print a version 2 state and never rewrite the file. Legacy files stay valid, and nothing on disk changes until the caller writes the printed result.

Version 2 example:

```json
{
  "version": 2,
  "topic": "Small field-notes tool",
  "status": "active",
  "source_kind": "conversation",
  "stage": "idea",
  "authority": {
    "mode": "discussion",
    "scope": ["documentation"],
    "evidence": "The user asked to discuss the idea before anything is created."
  },
  "facts": [
    {
      "id": "fact_folder",
      "statement": "The chosen folder holds only a README draft.",
      "source": "folder listing",
      "status": "verified"
    }
  ],
  "desired_state": [
    {
      "id": "want_offline",
      "statement": "Notes stay readable without network access.",
      "source": "user statement"
    }
  ],
  "conflicts": [],
  "decisions": [
    {
      "id": "audience",
      "question": "Who is the first user of the tool?",
      "status": "resolved",
      "depends_on": [],
      "conflicts": [],
      "recommendation": "Start with the author alone.",
      "answer": "The author alone",
      "blocking": true,
      "previous_answers": []
    },
    {
      "id": "first_scope",
      "question": "What belongs in the first version?",
      "status": "pending",
      "depends_on": ["audience"],
      "conflicts": [],
      "recommendation": "Capture and search only.",
      "answer": null,
      "blocking": true,
      "previous_answers": []
    },
    {
      "id": "sync_later",
      "question": "Should multi-device sync be built now?",
      "status": "deferred",
      "depends_on": ["first_scope"],
      "conflicts": [],
      "recommendation": null,
      "answer": null,
      "blocking": false,
      "previous_answers": []
    }
  ],
  "out_of_scope": ["Publishing the tool"]
}
```

### Revision, invalidation, and readiness

- `idea_revision(state)` returns a 16-character token over the topic, project stage, desired state, facts, decisions, and conflicts. `is_result_current(state, revision)` reports whether a tool result computed at that token is still current, so a result produced before a change is rejected instead of reused.
- `revise_decision(state, decision_id, answer, ...)` re-answers one decision and marks every transitively dependent decision `stale`, archiving their earlier answers in `previous_answers`. A repeated identical answer is treated as no change and never invalidates dependents. Facts, conflicts, and unaffected decisions are preserved, and a `ready_for_confirmation` or `confirmed` session drops back to `active` when readiness breaks. The revision quoted in `stale_reason` is the revision that actually results from the invalidation.
- `authorized_for(state, mode, scope_item=None)` reads the recorded authorization: `implementation` covers `design` and `discussion`, while `discussion` never covers design or implementation. A requested scope item must be present in the recorded `scope`. This reports the user's authorization; it never grants one.
- `compute_readiness(state)` reports readiness for the *next authorized stage* only, not for every possible future question. A substantive stage also requires recorded authorization; `deferred`, `blocking: false` decisions, and explicitly non-blocking conflicts never gate it.
- `next_useful_step(state)` returns the single most useful resume action and always reports open blocking work — an unresolved conflict, a blocker, a stale dependent, or an answerable question — before any stored or generic hint. When nothing blocking is left it recommends a still-current stored step, then the next authorized stage, then the missing authorization basis.
- The summary keeps two separate signals. `ready` is informational: no blocking decision or conflict is open, which is all `ready_for_confirmation` and `confirmed` need, so resolved decisions with no recorded authorization can still be confirmed. The nested `readiness` mapping is authorization-gated and reports the next stage's `mode`, `stage`, `authorized`, `ready`, `blocking_decisions`, `blocking_conflicts`, and `deferred_decisions`. The command line prints both as clearly labelled lines.

The structural validator never certifies that a recorded fact is true, and an authorization record is not permission granted by the script.

### Commands

```bash
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --validate-only
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --json
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --idea-revision
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --next-step
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --readiness
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --check-authorization implementation
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --upgrade-to-v2
python3 <this-skill>/scripts/decision_state.py --input .project-questionnaire/decision-state.json --revise-decision code_rules_mode --answer "Use code rules"
```

Every mode prints to stdout and none of them writes the state file, so nothing is rewritten implicitly. `--check-authorization` exits `0` when the recorded authorization covers the mode and `3` when it does not. `--answer`, `--reason`, and `--source-kind` are only meaningful with `--revise-decision`; using one without it is a usage error (exit `2`) instead of being silently ignored. A state file that is not valid UTF-8, or that is a directory, fails with a clear error and exit `2` rather than a traceback.

Writing state to disk stays optional and caller-authorized; a discussion-only session still needs no state file, and no file is rewritten after every answer. Never store secrets, full transcripts, or the model's hidden reasoning in the state or in these examples.

## Completion Criteria

Discovery is complete only when:

- every required (blocking) decision is resolved and any deferred non-blocking item is named explicitly;
- all dependencies were visited in order;
- no relevant repository fact was delegated back to the user;
- every material contradiction has an explicit resolution or a visible `TODO: clarify` destination;
- important boundary decisions survived a concrete scenario check;
- the proposed owner map has one owner per durable topic;
- the user has confirmed the shared understanding when confirmation is required.

Do not use a fixed question count as progress. Report the resolved, pending, blocked, and open-conflict counts from the state instead.
