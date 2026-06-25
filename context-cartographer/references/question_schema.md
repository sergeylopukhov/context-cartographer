# Questionnaire JSON Schema

This skill uses a stable JSON object saved as `.context-cartographer-questionnaire/questions.json`.

## Top-Level Fields

- `title` string, required: Short questionnaire title.
- `language` string, optional: UI/output language. Supported values: `en`, `ru`. If omitted, the server infers Russian when questionnaire text contains Cyrillic and English otherwise.
- `description` string, optional: One-paragraph explanation shown at the top of the form.
- `project_context` string or object, optional: Brief context the agent used to build the questionnaire.
- `questions` array, required: One or more question objects.
- `metadata` object, optional: Non-user-facing data for the agent.

## Question Fields

- `id` string, required: Stable unique identifier. Use letters, numbers, `_`, or `-`.
- `title` string, required: User-facing question text.
- `help_text` string, optional: Short guidance shown below the title.
- `type` string, required. Supported values:
  - `single_choice`
  - `multiple_choice`
  - `text`
  - `textarea`
  - `scale`
- `options` array, required for `single_choice` and `multiple_choice`.
- `recommended` string, number, or array, optional: Recommended option value. For `multiple_choice`, use an array.
- `allow_other` boolean, optional: Adds a localized "Other / my own option" choice. The UI shows a visible custom-answer field when the user selects it.
- `allow_recommend` boolean, optional: Adds a localized "Not sure / let the agent recommend" choice.
- `required` boolean, optional: Whether the user must answer before saving.
- `default` string, number, or array, optional: Initial value.
- `show_if` object, optional: Simple dependency that controls whether the question is visible.
- `metadata` object, optional: Non-user-facing data for the agent.

## Option Fields

Options may be strings:

```json
"options": ["MVP", "Polished V1", "Prototype"]
```

Or objects:

```json
{
  "value": "mvp",
  "label": "MVP",
  "help_text": "Smallest version that proves the workflow.",
  "metadata": {
    "scope": "small"
  }
}
```

Object option fields:

- `value` string, required: Stable machine value.
- `label` string, optional: User-facing label. Defaults to `value`.
- `help_text` string, optional: Short explanation.
- `recommended` boolean, optional: Marks this option as recommended if the question-level `recommended` field is omitted.
- `metadata` object, optional: Non-user-facing data for the agent.

## allow_other Answer Behavior

When `allow_other: true` is set on a `single_choice` or `multiple_choice` question, the server adds a built-in option with value `__other__` and a localized label:

- English: `Other / my own option`
- Russian: `Другое / свой вариант`

If the user selects that option, the UI shows a custom-answer text field directly under the option. The user must type a custom answer or choose a different answer. If the field is empty, the UI shows:

```text
Enter your own option or choose a different answer.
```

For Russian questionnaires, the message is localized as `Введите свой вариант или выберите другой ответ.`

Saved answers preserve both the selected option marker and the custom text:

- `value`: selected option value, or an array of selected values for `multiple_choice`.
- `selected_options`: selected option objects with `value`, `label`, `is_other`, and `is_recommendation_request`.
- `selected_option_label`: label for a single selected option.
- `selected_option_labels`: labels for all selected options.
- `other_selected`: whether `__other__` was selected.
- `other_text`: the typed custom answer.
- `comment`: optional per-question free-form comment.

For backward compatibility, `other_value` mirrors `other_text`.

## Per-Question Comments

The UI adds an optional comment textarea under every question:

- English label: `Comment`
- English placeholder: `Add a clarification, constraint, or note if useful...`
- Russian label: `Комментарий к ответу`
- Russian placeholder: `Можно добавить уточнение, ограничение или пояснение…`

When present, the comment is saved as `comment` in `answers.json` and included under that question in `answers.md`.

## Saved Answer Examples

Single choice with `other_text`:

```json
{
  "id": "visual_style",
  "title": "Какой визуальный стиль выбрать?",
  "type": "single_choice",
  "value": "__other__",
  "selected_options": [
    {
      "value": "__other__",
      "label": "Другое / свой вариант",
      "is_other": true,
      "is_recommendation_request": false
    }
  ],
  "selected_option_label": "Другое / свой вариант",
  "selected_option_labels": ["Другое / свой вариант"],
  "other_selected": true,
  "other_text": "Строгий интерфейс в стиле банковского кабинета",
  "comment": "Без декоративных градиентов.",
  "display_value": "Другое / свой вариант: Строгий интерфейс в стиле банковского кабинета"
}
```

Multiple choice with `other_text`:

```json
{
  "id": "channels",
  "title": "Какие каналы нужны?",
  "type": "multiple_choice",
  "value": ["email", "__other__"],
  "selected_options": [
    {
      "value": "email",
      "label": "Email",
      "is_other": false,
      "is_recommendation_request": false
    },
    {
      "value": "__other__",
      "label": "Другое / свой вариант",
      "is_other": true,
      "is_recommendation_request": false
    }
  ],
  "selected_option_labels": ["Email", "Другое / свой вариант"],
  "other_selected": true,
  "other_text": "Telegram-уведомления для администраторов",
  "comment": "Email нужен только для итоговых отчетов.",
  "display_value": [
    "Email",
    "Другое / свой вариант: Telegram-уведомления для администраторов"
  ]
}
```

Answer comment without `other_text`:

```json
{
  "id": "deadline",
  "title": "Какой темп работы выбрать?",
  "type": "single_choice",
  "value": "mvp",
  "selected_option_label": "Сначала MVP",
  "selected_option_labels": ["Сначала MVP"],
  "other_selected": false,
  "other_text": "",
  "comment": "Главное - быстро проверить рабочий сценарий.",
  "display_value": "Сначала MVP"
}
```

## Scale Questions

Scale questions support:

- `min`: must be `1`.
- `max`: must be `5` or `10`.
- `default`: optional number within range.
- `recommended`: optional number within range.

If omitted, `min` defaults to `1` and `max` defaults to `5`.

## show_if Dependencies

Use `show_if` for simple conditional follow-up questions.

Supported operators:

```json
{
  "question_id": "project_type",
  "equals": "landing_page"
}
```

```json
{
  "question_id": "channels",
  "includes": "telegram"
}
```

```json
{
  "question_id": "scope",
  "not_equals": "prototype"
}
```

```json
{
  "question_id": "audience",
  "is_answered": true
}
```

Only one operator should be used per `show_if` object.

## Full Valid Example

```json
{
  "language": "en",
  "title": "Landing Page Project Brief",
  "description": "Choose the practical direction for the landing page so the agent can produce a focused implementation plan.",
  "project_context": "The user wants a conversion-focused landing page for a new SaaS product.",
  "metadata": {
    "created_by": "agent",
    "purpose": "requirements"
  },
  "questions": [
    {
      "id": "primary_goal",
      "title": "What should the landing page optimize for first?",
      "help_text": "Pick the outcome that matters most for the first version.",
      "type": "single_choice",
      "required": true,
      "recommended": "waitlist",
      "allow_other": true,
      "allow_recommend": true,
      "options": [
        {
          "value": "waitlist",
          "label": "Waitlist signups",
          "help_text": "Best when validating demand before launch."
        },
        {
          "value": "demo_calls",
          "label": "Booked demo calls"
        },
        {
          "value": "paid_trials",
          "label": "Paid trial starts"
        }
      ]
    },
    {
      "id": "target_audience",
      "title": "Who is the first audience?",
      "type": "text",
      "required": true,
      "default": "B2B SaaS founders"
    },
    {
      "id": "sections",
      "title": "Which sections should be included?",
      "type": "multiple_choice",
      "required": true,
      "default": ["hero", "social_proof", "pricing"],
      "recommended": ["hero", "pain", "social_proof", "cta"],
      "allow_other": true,
      "options": [
        {
          "value": "hero",
          "label": "Hero with primary CTA"
        },
        {
          "value": "pain",
          "label": "Problem and stakes"
        },
        {
          "value": "social_proof",
          "label": "Social proof"
        },
        {
          "value": "pricing",
          "label": "Pricing"
        },
        {
          "value": "cta",
          "label": "Final CTA"
        }
      ]
    },
    {
      "id": "pricing_detail",
      "title": "How much pricing detail should be shown?",
      "type": "single_choice",
      "required": true,
      "show_if": {
        "question_id": "sections",
        "includes": "pricing"
      },
      "options": [
        {
          "value": "simple",
          "label": "One simple starting price"
        },
        {
          "value": "tiers",
          "label": "Three plan tiers"
        },
        {
          "value": "contact",
          "label": "Contact us only"
        }
      ]
    },
    {
      "id": "confidence",
      "title": "How confident are you in this direction?",
      "type": "scale",
      "min": 1,
      "max": 5,
      "default": 3,
      "required": true
    },
    {
      "id": "notes",
      "title": "Anything else the agent should account for?",
      "type": "textarea",
      "required": false
    }
  ]
}
```
