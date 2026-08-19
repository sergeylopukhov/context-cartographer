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
4. Read `answers.json` and `answers.md`, then build `.project-questionnaire/decision-state.json` only if dependent decisions or conflicts remain.
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
11. Set state to `ready_for_confirmation` only when every decision is resolved and every conflict is closed. Present a compact decision summary and proposed documentation map.
12. Continue to documentation edits when the original request already authorizes the exact resulting changes. Ask for confirmation only when the interview materially changed the proposed scope, multiple valid maps remain, or a destructive action still needs authorization.
13. Set state to `confirmed` after confirmation. Treat the state file as temporary local workflow state, never as a durable owner or publication artifact.

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

Allowed session statuses are `active`, `ready_for_confirmation`, and `confirmed`. Decision statuses are `pending`, `resolved`, and `blocked`. A blocked decision must include a non-empty `blocker`. Facts are `verified`, `uncertain`, or `conflicting`; conflicts are `open` or `resolved` and resolved conflicts require a `resolution`.

The validator rejects duplicate IDs, missing dependency targets, dependency cycles, resolved items without answers, and premature ready/confirmed status.

## Completion Criteria

Discovery is complete only when:

- every required decision is resolved;
- all dependencies were visited in order;
- no relevant repository fact was delegated back to the user;
- every material contradiction has an explicit resolution or a visible `TODO: clarify` destination;
- important boundary decisions survived a concrete scenario check;
- the proposed owner map has one owner per durable topic;
- the user has confirmed the shared understanding when confirmation is required.

Do not use a fixed question count as progress. Report the resolved, pending, blocked, and open-conflict counts from the state instead.
