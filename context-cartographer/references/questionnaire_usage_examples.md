# Usage Examples

Use these prompts when an agent should collect project decisions through a clickable local questionnaire.

These examples should trigger the skill even without naming it:

```text
Ask me questions before implementation.
```

```text
Collect requirements before you build.
```

```text
Сначала задай мне вопросы по проекту.
```

```text
Собери требования перед реализацией.
```

Explicit skill-name examples:

```text
Use interactive-project-questionnaire when you need to ask me project questions.
```

```text
Используй interactive-project-questionnaire, чтобы задать мне вопросы по проекту.
```

```text
Use $interactive-project-questionnaire to collect requirements for this landing page project.
```

```text
Use the interactive questionnaire skill before implementing this feature.
```

```text
Ask me project questions through a clickable local form, not through a numbered chat list.
```

```text
Use $interactive-project-questionnaire and write the questionnaire in Russian.
```

```text
Перед реализацией собери требования через кликабельную анкету. Я хочу выбирать готовые варианты, но иногда выбирать "Другое / свой вариант" и вписывать свой ответ.
```

## Typical Agent Flow

1. The agent creates `.project-questionnaire/questions.json`.
2. The agent validates it:

   ```bash
   python3 <skill-dir>/scripts/questionnaire_server.py --input .project-questionnaire/questions.json --validate-only
   ```

3. The agent starts the local server:

   ```bash
   python3 <skill-dir>/scripts/questionnaire_server.py --input .project-questionnaire/questions.json --out-dir .project-questionnaire --port 0
   ```

4. The agent gives the user a URL like `http://127.0.0.1:8765/`.
5. The user opens the URL, selects predefined answers, optionally chooses the localized "Other" option, optionally adds comments, saves the form, and tells the agent they are done.
6. The agent reads `.project-questionnaire/answers.md` and `.project-questionnaire/answers.json`.
7. The agent summarizes the decisions and continues the task.

## Russian Questionnaire Example

Set top-level `language` to `ru`:

```json
{
  "title": "Бриф проекта",
  "description": "Выберите практическое направление, чтобы агент продолжил работу без длинного списка вопросов в чате.",
  "language": "ru",
  "questions": [
    {
      "id": "goal",
      "title": "Какой результат важнее всего?",
      "type": "single_choice",
      "required": true,
      "allow_other": true,
      "allow_recommend": true,
      "options": [
        {
          "value": "mvp",
          "label": "Быстрый MVP"
        },
        {
          "value": "polished_v1",
          "label": "Аккуратная первая версия"
        }
      ]
    }
  ]
}
```

## Optional Cleanup

Do not clean up automatically after saving the form. The agent still needs to read the answer files.

After the task is finished, cleanup can be requested explicitly or run manually:

```bash
python3 <skill-dir>/scripts/questionnaire_server.py --out-dir .project-questionnaire --cleanup
```

Cleanup deletes generated questionnaire files such as `questions.json`, `answers.json`, `answers.md`, and backups from `.project-questionnaire/`, while keeping `.project-questionnaire/.gitignore`.
