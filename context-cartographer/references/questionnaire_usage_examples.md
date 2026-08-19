# Bundled Questionnaire Usage

Use the bundled questionnaire only inside a `context-cartographer` setup, audit, migration, cleanup, or restructuring task. Generic product discovery or "ask me questions before implementation" requests do not belong to this skill unless the user is specifically designing the project's agent-facing documentation system.

## Appropriate Requests

```text
Use $context-cartographer to set up this project's agent documentation. Collect the unresolved setup choices through a clickable form if the native question interface is not sufficient.
```

```text
Приведи документацию проекта в порядок. Если для карты owner-файлов нужно несколько независимых решений, собери их через локальную анкету.
```

```text
Audit the existing project docs and ask me through a portable questionnaire whether they should remain local, be migrated, or be tracked.
```

Do not activate this workflow for:

```text
Ask me questions before building a landing page.
```

```text
Interview me about a new product feature.
```

Those are general requirements-discovery requests unless they explicitly include documentation-system ownership or restructuring.

## Interface Selection

1. Resolve repository facts before asking questions.
2. Ask one blocking decision directly.
3. Use a host-native structured question interface for a small independent set when it supports the required answer detail.
4. Use the bundled questionnaire for a broad independent baseline, richer comments/custom answers, or cross-client portability.
5. After reading the saved answers, switch to `decision-discovery.md` only when dependencies, conflicts, or material ambiguity remain.

## Local Questionnaire Flow

1. Create `.project-questionnaire/questions.json`.
2. Validate it:

   ```bash
   python3 <skill-dir>/scripts/questionnaire_server.py \
     --input .project-questionnaire/questions.json \
     --validate-only
   ```

3. Start the local server:

   ```bash
   python3 <skill-dir>/scripts/questionnaire_server.py \
     --input .project-questionnaire/questions.json \
     --out-dir .project-questionnaire \
     --port 0
   ```

4. Give the user the printed `http://127.0.0.1:<port>/` URL.
5. After the user saves and says they are done, read both `.project-questionnaire/answers.json` and `.project-questionnaire/answers.md`.
6. Reuse complete answers. Do not repeat the entire questionnaire in chat.

## Documentation Setup Example

The two mode decisions are required and deliberately have no defaults or recommendations:

```json
{
  "title": "Project documentation setup",
  "description": "Choose how agents should route and maintain durable project knowledge.",
  "language": "en",
  "questions": [
    {
      "id": "agent_target",
      "title": "Which coding agents should receive project instructions?",
      "type": "multiple_choice",
      "required": true,
      "allow_other": true,
      "options": [
        {"value": "codex", "label": "Codex"},
        {"value": "claude", "label": "Claude Code"},
        {"value": "cursor", "label": "Cursor"}
      ]
    },
    {
      "id": "code_rules_mode",
      "title": "Should the project use docs/code_rules.md?",
      "type": "single_choice",
      "required": true,
      "options": [
        {"value": "use", "label": "Use a dedicated code-rules file"},
        {"value": "skip", "label": "Do not use a dedicated code-rules file"}
      ]
    },
    {
      "id": "maintenance_mode",
      "title": "How should durable project documentation be maintained?",
      "type": "single_choice",
      "required": true,
      "options": [
        {"value": "automatic", "label": "Automatic durable maintenance"},
        {"value": "request_only", "label": "Update only when requested"}
      ]
    }
  ]
}
```

## Explicit Cleanup

Do not clean generated files before the agent has read the saved answers and any decision state. Cleanup remains explicit:

```bash
python3 <skill-dir>/scripts/questionnaire_server.py \
  --out-dir .project-questionnaire \
  --cleanup
```

Cleanup removes generated questionnaire files, answer backups, and `decision-state.json`, while preserving `.project-questionnaire/.gitignore` and unrelated files.
