# Questionnaire JSON Schema

Save questionnaire definitions as a UTF-8 JSON object, usually:

```text
.project-questionnaire/questions.json
```

## Top-Level Fields

- `title` string, required: Short questionnaire title.
- `description` string, optional: One-paragraph explanation shown at the top of the form.
- `language` string, optional: Built-in UI language. Supported values: `en`, `ru`. Defaults to `en`.
- `ui` object, optional: Overrides for built-in UI labels. Keys must match the supported UI keys listed below.
- `project_context` string, object, or array, optional: Internal context the agent used to build the questionnaire. It is saved in answer files for the agent, but is not shown in the browser form.
- `questions` array, required: One or more question objects.
- `metadata` object, optional: Non-user-facing data for the agent.

## Language And UI Labels

Use:

```json
"language": "en"
```

or:

```json
"language": "ru"
```

The server adds built-in labels for "Other", "Not sure", comments, buttons, progress, errors, and generated Markdown headings.

Use `ui` only for project-specific overrides:

```json
{
  "language": "en",
  "ui": {
    "other_label": "Something else",
    "save_answers": "Save brief"
  }
}
```

Common UI keys:

- `not_sure_label`
- `other_label`
- `other_placeholder`
- `other_required`
- `required_missing`
- `comment_label`
- `comment_placeholder`
- `save_answers`
- `clear_draft`
- `summary_title`
- `saved_message`
- `markdown_title`
- `markdown_answers`

If an unknown `ui` key is supplied, validation fails.

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
- `allow_other` boolean, optional: Adds the localized "Other / custom answer" option. The UI shows a visible custom-answer field when the user selects it.
- `allow_recommend` boolean, optional: Adds the localized "Not sure / recommend for me" option.
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

When `allow_other: true` is set on a `single_choice` or `multiple_choice` question, the server adds a built-in option with value `__other__` and a localized label.

If the user selects that option, the UI shows a custom-answer text field directly under the option. The user must type a custom answer or choose a different answer.

Saved answers preserve both the selected option marker and the custom text:

- `value`: selected option value, or an array of selected values for `multiple_choice`.
- `selected_options`: selected option objects with `value`, `label`, `is_other`, and `is_recommendation_request`.
- `selected_option_label`: label for a single selected option.
- `selected_option_labels`: labels for all selected options.
- `other_selected`: whether `__other__` was selected.
- `other_text`: the typed custom answer.
- `comment`: optional per-question free-form comment.
- `display_value`: localized display value for summaries.

For backward compatibility, `other_value` mirrors `other_text`.

## Per-Question Comments

The UI adds an optional comment textarea under every question. Comments are saved as `comment` in `answers.json` and included in `answers.md`.

## Saved Answer Example

```json
{
  "id": "visual_style",
  "title": "Which visual style should we use?",
  "type": "single_choice",
  "value": "__other__",
  "selected_options": [
    {
      "value": "__other__",
      "label": "Other / custom answer",
      "is_other": true,
      "is_recommendation_request": false
    }
  ],
  "selected_option_label": "Other / custom answer",
  "selected_option_labels": ["Other / custom answer"],
  "other_selected": true,
  "other_text": "A restrained banking-style interface",
  "comment": "Avoid decorative gradients.",
  "display_value": "Other / custom answer: A restrained banking-style interface"
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
  "title": "Landing Page Project Brief",
  "description": "Choose the practical direction for the landing page so the agent can produce a focused implementation plan.",
  "language": "en",
  "project_context": "The user wants a conversion-focused landing page for a new SaaS product.",
  "metadata": {
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
