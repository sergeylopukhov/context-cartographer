#!/usr/bin/env python3
"""Dependency-free local questionnaire server for Codex project planning."""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import html
import json
import re
import shutil
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOST = "127.0.0.1"
VERSION = "1.1.0"
SUPPORTED_TYPES = {"single_choice", "multiple_choice", "text", "textarea", "scale"}
CHOICE_TYPES = {"single_choice", "multiple_choice"}
NOT_SURE_VALUE = "__not_sure__"
OTHER_VALUE = "__other__"
NOT_SURE_LABEL = "Не уверен / порекомендуй сам"
OTHER_LABEL = "Другое / свой вариант"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
GITIGNORE_CONTENT = "*\n!.gitignore\n"


class QuestionnaireError(Exception):
    """Raised for clean, user-facing questionnaire errors."""


DEFAULT_DEMO_QUESTIONNAIRE = {
    "title": "Демо-анкета проекта",
    "description": "Короткая встроенная анкета для проверки локальной формы.",
    "project_context": "Только демонстрация. Для реальной работы передайте --input .codex-questionnaire/questions.json.",
    "metadata": {"demo": True},
    "questions": [
        {
            "id": "project_kind",
            "title": "Какой это тип проекта?",
            "type": "single_choice",
            "required": True,
            "recommended": "web_app",
            "allow_other": True,
            "allow_recommend": True,
            "options": [
                {"value": "web_app", "label": "Веб-приложение"},
                {"value": "automation", "label": "Автоматизация"},
                {"value": "content", "label": "Контент или проектный бриф"},
            ],
        },
        {
            "id": "must_have",
            "title": "Какой результат самый важный?",
            "type": "textarea",
            "required": True,
        },
        {
            "id": "confidence",
            "title": "Насколько вы уверены в выбранном направлении?",
            "type": "scale",
            "min": 1,
            "max": 5,
            "default": 3,
            "required": True,
        },
    ],
}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuestionnaireError(f"{label} must be an object.")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise QuestionnaireError(f"{label} must be true or false.")
    return value


def _json_scalar_to_str(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_option(raw: Any, question_id: str, index: int) -> dict[str, Any]:
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            raise QuestionnaireError(f"Question '{question_id}' option {index + 1} cannot be empty.")
        return {"value": value, "label": value}

    if not isinstance(raw, dict):
        raise QuestionnaireError(f"Question '{question_id}' option {index + 1} must be a string or object.")

    if not _is_nonempty_string(raw.get("value")):
        raise QuestionnaireError(f"Question '{question_id}' option {index + 1} needs a non-empty string value.")

    value = raw["value"].strip()
    label = raw.get("label", value)
    if not _is_nonempty_string(label):
        raise QuestionnaireError(f"Question '{question_id}' option '{value}' has an empty label.")

    option = {
        "value": value,
        "label": label.strip(),
    }

    if "help_text" in raw:
        if not isinstance(raw["help_text"], str):
            raise QuestionnaireError(f"Question '{question_id}' option '{value}' help_text must be a string.")
        option["help_text"] = raw["help_text"]

    if "recommended" in raw:
        option["recommended"] = _require_bool(raw["recommended"], f"Question '{question_id}' option '{value}' recommended")

    if "metadata" in raw:
        option["metadata"] = _require_object(raw["metadata"], f"Question '{question_id}' option '{value}' metadata")

    return option


def _normalize_show_if(raw: Any, question_id: str) -> dict[str, Any]:
    show_if = _require_object(raw, f"Question '{question_id}' show_if")
    if not _is_nonempty_string(show_if.get("question_id")):
        raise QuestionnaireError(f"Question '{question_id}' show_if.question_id must be a non-empty string.")

    operators = [key for key in ("equals", "not_equals", "includes", "is_answered") if key in show_if]
    if len(operators) != 1:
        raise QuestionnaireError(
            f"Question '{question_id}' show_if must include exactly one of equals, not_equals, includes, or is_answered."
        )

    normalized = {"question_id": show_if["question_id"].strip(), operators[0]: show_if[operators[0]]}
    if operators[0] == "is_answered" and not isinstance(show_if[operators[0]], bool):
        raise QuestionnaireError(f"Question '{question_id}' show_if.is_answered must be true or false.")
    return normalized


def _validate_choice_value(question: dict[str, Any], value: Any, label: str) -> None:
    allowed = {option["value"] for option in question.get("options", [])}
    if question.get("allow_recommend"):
        allowed.add(NOT_SURE_VALUE)
    if value not in allowed:
        raise QuestionnaireError(
            f"Question '{question['id']}' {label} must match an option value"
            + (" or __not_sure__." if question.get("allow_recommend") else ".")
        )


def _normalize_question(raw: Any, index: int) -> dict[str, Any]:
    question = _require_object(raw, f"Question {index + 1}")

    if not _is_nonempty_string(question.get("id")):
        raise QuestionnaireError(f"Question {index + 1} needs a non-empty string id.")
    qid = question["id"].strip()
    if not ID_RE.match(qid):
        raise QuestionnaireError(f"Question '{qid}' id may only contain letters, numbers, underscores, and hyphens.")

    if not _is_nonempty_string(question.get("title")):
        raise QuestionnaireError(f"Question '{qid}' needs a non-empty title.")

    qtype = question.get("type")
    if qtype not in SUPPORTED_TYPES:
        raise QuestionnaireError(f"Question '{qid}' type must be one of: {', '.join(sorted(SUPPORTED_TYPES))}.")

    normalized: dict[str, Any] = {
        "id": qid,
        "title": question["title"].strip(),
        "type": qtype,
        "required": bool(question.get("required", False)),
        "metadata": {},
    }

    if "required" in question:
        normalized["required"] = _require_bool(question["required"], f"Question '{qid}' required")

    help_text = question.get("help_text", question.get("help"))
    if help_text is not None:
        if not isinstance(help_text, str):
            raise QuestionnaireError(f"Question '{qid}' help_text must be a string.")
        normalized["help_text"] = help_text

    if "metadata" in question:
        normalized["metadata"] = _require_object(question["metadata"], f"Question '{qid}' metadata")

    if "show_if" in question:
        normalized["show_if"] = _normalize_show_if(question["show_if"], qid)

    if qtype in CHOICE_TYPES:
        options_raw = question.get("options")
        if not isinstance(options_raw, list) or len(options_raw) < 2:
            raise QuestionnaireError(f"Question '{qid}' must include at least two options.")
        options = [_normalize_option(option, qid, idx) for idx, option in enumerate(options_raw)]
        values = [option["value"] for option in options]
        if len(values) != len(set(values)):
            raise QuestionnaireError(f"Question '{qid}' options must have unique values.")
        normalized["options"] = options

        if "allow_other" in question:
            normalized["allow_other"] = _require_bool(question["allow_other"], f"Question '{qid}' allow_other")
        else:
            normalized["allow_other"] = False

        if "allow_recommend" in question:
            normalized["allow_recommend"] = _require_bool(
                question["allow_recommend"], f"Question '{qid}' allow_recommend"
            )
        else:
            normalized["allow_recommend"] = False

        option_recommendations = [option["value"] for option in options if option.get("recommended")]
        if "recommended" in question:
            recommended = question["recommended"]
        elif option_recommendations:
            recommended = option_recommendations if qtype == "multiple_choice" else option_recommendations[0]
        else:
            recommended = None

        if recommended is not None:
            if qtype == "multiple_choice":
                if not isinstance(recommended, list):
                    raise QuestionnaireError(f"Question '{qid}' recommended must be an array for multiple_choice.")
                for item in recommended:
                    _validate_choice_value(normalized, item, "recommended")
            else:
                _validate_choice_value(normalized, recommended, "recommended")
            normalized["recommended"] = recommended

        if "default" in question:
            default = question["default"]
            if qtype == "multiple_choice":
                if not isinstance(default, list):
                    raise QuestionnaireError(f"Question '{qid}' default must be an array for multiple_choice.")
                for item in default:
                    _validate_choice_value(normalized, item, "default")
            else:
                _validate_choice_value(normalized, default, "default")
            normalized["default"] = default

    else:
        if "options" in question:
            raise QuestionnaireError(f"Question '{qid}' options are only valid for choice questions.")
        if "allow_other" in question:
            raise QuestionnaireError(f"Question '{qid}' allow_other is only valid for choice questions.")
        if "allow_recommend" in question:
            raise QuestionnaireError(f"Question '{qid}' allow_recommend is only valid for choice questions.")

    if qtype in {"text", "textarea"} and "default" in question:
        if not isinstance(question["default"], str):
            raise QuestionnaireError(f"Question '{qid}' default must be a string.")
        normalized["default"] = question["default"]

    if qtype == "scale":
        min_value = question.get("min", 1)
        max_value = question.get("max", 5)
        if min_value != 1 or max_value not in (5, 10):
            raise QuestionnaireError(f"Question '{qid}' scale must use min 1 and max 5 or 10.")
        normalized["min"] = min_value
        normalized["max"] = max_value

        for field in ("default", "recommended"):
            if field in question:
                value = question[field]
                if not isinstance(value, int) or not (min_value <= value <= max_value):
                    raise QuestionnaireError(f"Question '{qid}' {field} must be an integer from {min_value} to {max_value}.")
                normalized[field] = value

    return normalized


def validate_questionnaire(raw: Any, source: str = "<memory>") -> dict[str, Any]:
    data = _require_object(raw, f"Questionnaire {source}")

    if not _is_nonempty_string(data.get("title")):
        raise QuestionnaireError("Questionnaire title must be a non-empty string.")

    normalized: dict[str, Any] = {
        "title": data["title"].strip(),
        "description": "",
        "project_context": "",
        "metadata": {},
        "questions": [],
    }

    if "description" in data:
        if not isinstance(data["description"], str):
            raise QuestionnaireError("Questionnaire description must be a string.")
        normalized["description"] = data["description"]

    if "project_context" in data:
        if not isinstance(data["project_context"], (str, dict, list)):
            raise QuestionnaireError("Questionnaire project_context must be a string, object, or array.")
        normalized["project_context"] = data["project_context"]

    if "metadata" in data:
        normalized["metadata"] = _require_object(data["metadata"], "Questionnaire metadata")

    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise QuestionnaireError("Questionnaire questions must be a non-empty array.")

    normalized_questions = [_normalize_question(question, idx) for idx, question in enumerate(questions)]
    ids = [question["id"] for question in normalized_questions]
    if len(ids) != len(set(ids)):
        raise QuestionnaireError("Question ids must be unique.")

    known_ids = set(ids)
    for question in normalized_questions:
        show_if = question.get("show_if")
        if not show_if:
            continue
        dependency = show_if["question_id"]
        if dependency not in known_ids:
            raise QuestionnaireError(f"Question '{question['id']}' show_if references unknown question '{dependency}'.")
        if dependency == question["id"]:
            raise QuestionnaireError(f"Question '{question['id']}' cannot depend on itself.")

    normalized["questions"] = normalized_questions
    return normalized


def load_questionnaire(input_path: Path | None) -> dict[str, Any]:
    if input_path is None:
        return validate_questionnaire(copy.deepcopy(DEFAULT_DEMO_QUESTIONNAIRE), "embedded demo")

    try:
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise QuestionnaireError(f"Could not read input questionnaire '{input_path}': {exc}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuestionnaireError(
            f"Malformed JSON in '{input_path}' at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    return validate_questionnaire(raw, str(input_path))


def _answer_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {"value": raw}


def _answer_values(raw: Any) -> list[Any]:
    if raw is None:
        return []
    value = _answer_object(raw).get("value")
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value == "":
        return []
    return [value]


def _has_answer(raw: Any) -> bool:
    answer = _answer_object(raw)
    value = answer.get("value")
    other = answer.get("other_text", answer.get("other", ""))
    if isinstance(value, list):
        if any(item not in ("", None) for item in value):
            if OTHER_VALUE not in value:
                return True
            return bool(str(other).strip()) or len([item for item in value if item != OTHER_VALUE]) > 0
        return False
    if value in (None, ""):
        return False
    if value == OTHER_VALUE:
        return bool(str(other).strip())
    return True


def _matches(actual_values: list[Any], expected: Any) -> bool:
    if isinstance(expected, list):
        return any(item in actual_values for item in expected)
    return expected in actual_values


def question_is_visible(question: dict[str, Any], answers: dict[str, Any]) -> bool:
    show_if = question.get("show_if")
    if not show_if:
        return True

    dependency_answer = answers.get(show_if["question_id"])
    actual_values = _answer_values(dependency_answer)

    if "equals" in show_if:
        return _matches(actual_values, show_if["equals"])
    if "includes" in show_if:
        return _matches(actual_values, show_if["includes"])
    if "not_equals" in show_if:
        return not _matches(actual_values, show_if["not_equals"])
    if "is_answered" in show_if:
        return _has_answer(dependency_answer) == show_if["is_answered"]
    return True


def _option_label_map(question: dict[str, Any]) -> dict[Any, str]:
    labels = {option["value"]: option["label"] for option in question.get("options", [])}
    if question.get("allow_recommend"):
        labels[NOT_SURE_VALUE] = NOT_SURE_LABEL
    if question.get("allow_other"):
        labels[OTHER_VALUE] = OTHER_LABEL
    return labels


def _display_answer(question: dict[str, Any], raw: Any) -> str | list[str]:
    answer = _answer_object(raw)
    value = answer.get("value")
    other = str(answer.get("other_text", answer.get("other", ""))).strip()
    qtype = question["type"]

    if value in (None, ""):
        return ""

    if qtype == "multiple_choice":
        if not isinstance(value, list):
            value = [value]
        labels = _option_label_map(question)
        rendered: list[str] = []
        for item in value:
            if item == OTHER_VALUE:
                rendered.append(f"{OTHER_LABEL}: {other}" if other else OTHER_LABEL)
            else:
                rendered.append(labels.get(item, _json_scalar_to_str(item)))
        return rendered

    if qtype == "single_choice":
        labels = _option_label_map(question)
        if value == OTHER_VALUE:
            return f"{OTHER_LABEL}: {other}" if other else OTHER_LABEL
        return labels.get(value, _json_scalar_to_str(value))

    if qtype == "scale":
        return f"{value} / {question.get('max', 5)}"

    return str(value).strip()


def _comment_text(raw: Any) -> str:
    return str(_answer_object(raw).get("comment", "")).strip()


def _selected_options(question: dict[str, Any], raw: Any) -> list[dict[str, Any]]:
    if question["type"] not in CHOICE_TYPES:
        return []
    labels = _option_label_map(question)
    values = _answer_values(raw)
    return [
        {
            "value": value,
            "label": labels.get(value, _json_scalar_to_str(value)),
            "is_other": value == OTHER_VALUE,
            "is_recommendation_request": value == NOT_SURE_VALUE,
        }
        for value in values
    ]


def _selected_other_without_text(question: dict[str, Any], raw: Any) -> bool:
    if question["type"] not in CHOICE_TYPES:
        return False
    values = _answer_values(raw)
    if OTHER_VALUE not in values:
        return False
    other_text = str(_answer_object(raw).get("other_text", _answer_object(raw).get("other", ""))).strip()
    return not other_text


def _validate_submitted_answers(questionnaire: dict[str, Any], answers: dict[str, Any]) -> None:
    missing: list[str] = []
    missing_other: list[str] = []
    for question in questionnaire["questions"]:
        if not question_is_visible(question, answers):
            continue
        raw = answers.get(question["id"])
        if question.get("required") and not _has_answer(raw):
            missing.append(question["title"])
        if _selected_other_without_text(question, raw):
            missing_other.append(question["title"])
    if missing_other:
        raise QuestionnaireError("Введите свой вариант или выберите другой ответ. Вопросы: " + "; ".join(missing_other))
    if missing:
        raise QuestionnaireError("Ответьте на обязательные вопросы: " + "; ".join(missing))


def _markdown_escape_inline(value: str) -> str:
    return value.replace("\n", " ").strip()


def _markdown_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        if not value:
            return "_Нет ответа_"
        return "\n".join(f"  - {_markdown_escape_inline(str(item))}" for item in value)
    if not value:
        return "_Нет ответа_"
    if "\n" in value:
        return "\n\n" + "\n".join(f"> {line}" if line else ">" for line in value.splitlines())
    return _markdown_escape_inline(str(value))


def build_answer_documents(
    questionnaire: dict[str, Any],
    answers: dict[str, Any],
    source_path: Path | None = None,
    saved_at: str | None = None,
) -> tuple[dict[str, Any], str]:
    if not isinstance(answers, dict):
        raise QuestionnaireError("Submitted answers must be a JSON object.")

    _validate_submitted_answers(questionnaire, answers)
    saved_at = saved_at or _dt.datetime.now().astimezone().isoformat(timespec="seconds")

    answer_items: list[dict[str, Any]] = []
    for index, question in enumerate(questionnaire["questions"], start=1):
        visible = question_is_visible(question, answers)
        raw = _answer_object(answers.get(question["id"], {}))
        display_value = _display_answer(question, raw) if visible else ""
        selected_options = _selected_options(question, raw) if visible else []
        other_text = str(raw.get("other_text", raw.get("other", ""))).strip()
        comment = _comment_text(raw)
        answer_items.append(
            {
                "index": index,
                "id": question["id"],
                "title": question["title"],
                "type": question["type"],
                "required": bool(question.get("required", False)),
                "visible": visible,
                "value": raw.get("value"),
                "selected_options": selected_options,
                "selected_option_labels": [option["label"] for option in selected_options],
                "selected_option_label": selected_options[0]["label"] if len(selected_options) == 1 else None,
                "other_selected": any(option["is_other"] for option in selected_options),
                "other_text": other_text,
                "other_value": other_text,
                "comment": comment,
                "display_value": display_value,
                "metadata": question.get("metadata", {}),
            }
        )

    output = {
        "questionnaire": {
            "title": questionnaire["title"],
            "description": questionnaire.get("description", ""),
            "project_context": questionnaire.get("project_context", ""),
            "source_path": str(source_path) if source_path else None,
        },
        "saved_at": saved_at,
        "answers": answer_items,
        "metadata": {
            "generated_by": "context-cartographer-questionnaire",
            "version": VERSION,
        },
    }

    lines = [
        f"# Ответы на анкету: {questionnaire['title']}",
        "",
        f"- Сохранено: {saved_at}",
    ]
    if source_path:
        lines.append(f"- Исходная анкета: `{source_path}`")

    description = questionnaire.get("description")
    if description:
        lines.extend(["", "## Описание анкеты", "", str(description).strip()])

    context = questionnaire.get("project_context")
    if context:
        context_text = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False, indent=2)
        lines.extend(["", "## Контекст проекта", "", str(context_text).strip()])

    lines.extend(["", "## Решения", ""])
    visible_answers = [item for item in answer_items if item["visible"]]
    if not visible_answers:
        lines.append("_Нет сохраненных видимых ответов._")
    else:
        for item in visible_answers:
            lines.append(f"### {item['index']}. {item['title']}")
            lines.append("")
            lines.append(f"- ID: `{item['id']}`")
            lines.append(f"- Тип: `{item['type']}`")
            lines.append("- Ответ: " + _markdown_value(item["display_value"]))
            if item["comment"]:
                lines.append("- Комментарий: " + _markdown_value(item["comment"]))
            lines.append("")

    hidden = [item for item in answer_items if not item["visible"]]
    if hidden:
        lines.extend(["## Скрыто условиями показа", ""])
        for item in hidden:
            lines.append(f"- `{item['id']}`: {item['title']}")

    markdown = "\n".join(lines).rstrip() + "\n"
    return output, markdown


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None

    stamp = _timestamp()
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{counter}")
        counter += 1
    shutil.copy2(path, candidate)
    return candidate


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(text)
    temp_path.replace(path)


def ensure_work_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    gitignore = out_dir / ".gitignore"
    if not gitignore.exists():
        _atomic_write_text(gitignore, GITIGNORE_CONTENT)


def cleanup_questionnaire_dir(out_dir: Path) -> list[str]:
    ensure_work_dir(out_dir)
    generated_names = {"questions.json", "questions.demo.json", "answers.json", "answers.md"}
    deleted: list[str] = []

    for child in sorted(out_dir.iterdir()):
        if child.name == ".gitignore" or not child.is_file():
            continue
        is_backup = ".backup-" in child.name
        if child.name in generated_names or is_backup:
            child.unlink()
            deleted.append(str(child))

    return deleted


def save_answers(
    questionnaire: dict[str, Any],
    answers: dict[str, Any],
    out_dir: Path,
    source_path: Path | None = None,
) -> dict[str, Any]:
    ensure_work_dir(out_dir)
    answers_json_path = out_dir / "answers.json"
    answers_md_path = out_dir / "answers.md"

    output, markdown = build_answer_documents(questionnaire, answers, source_path=source_path)

    backups = []
    for path in (answers_json_path, answers_md_path):
        backup = _backup_existing(path)
        if backup:
            backups.append(str(backup))

    _atomic_write_text(answers_json_path, json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(answers_md_path, markdown)

    return {
        "ok": True,
        "saved_at": output["saved_at"],
        "answers_json": str(answers_json_path),
        "answers_md": str(answers_md_path),
        "backups": backups,
        "answers": output["answers"],
    }


def _json_for_script(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def build_html(questionnaire: dict[str, Any]) -> str:
    page_title = html.escape(questionnaire["title"])
    questionnaire_json = _json_for_script(questionnaire)
    return HTML_TEMPLATE.replace("__PAGE_TITLE__", page_title).replace("__QUESTIONNAIRE_JSON__", questionnaire_json)


class QuestionnaireHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        questionnaire: dict[str, Any],
        out_dir: Path,
        source_path: Path | None,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.questionnaire = questionnaire
        self.out_dir = out_dir
        self.source_path = source_path


class QuestionnaireHandler(BaseHTTPRequestHandler):
    server: QuestionnaireHTTPServer

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self' data:; form-action 'self'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = build_html(self.server.questionnaire).encode("utf-8")
            self._send_bytes(200, "text/html; charset=utf-8", body)
            return
        if path == "/healthz":
            self._send_json(200, {"ok": True, "version": VERSION})
            return
        self._send_json(404, {"ok": False, "error": "Не найдено"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/save":
            self._send_json(404, {"ok": False, "error": "Не найдено"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"ok": False, "error": "Некорректный Content-Length"})
            return

        if content_length <= 0:
            self._send_json(400, {"ok": False, "error": "Пустое тело запроса"})
            return
        if content_length > 1024 * 1024:
            self._send_json(413, {"ok": False, "error": "Слишком большой объем ответов"})
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"ok": False, "error": f"Некорректный JSON в ответах: {exc}"})
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
            self._send_json(400, {"ok": False, "error": "Запрос должен быть объектом с объектом answers"})
            return

        try:
            result = save_answers(
                self.server.questionnaire,
                payload["answers"],
                self.server.out_dir,
                source_path=self.server.source_path,
            )
        except QuestionnaireError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except OSError as exc:
            self._send_json(500, {"ok": False, "error": f"Не удалось сохранить ответы: {exc}"})
            return

        self._send_json(200, result)


def positive_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not (0 <= port <= 65535):
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Запустить локальную кликабельную анкету Codex.")
    parser.add_argument("--input", type=Path, help="Путь к questions.json. Если не указан, используется встроенное демо.")
    parser.add_argument("--out-dir", type=Path, default=Path(".codex-questionnaire"), help="Папка для файлов ответов.")
    parser.add_argument("--port", type=positive_port, default=0, help="Порт на 127.0.0.1. Значение 0 выбирает свободный порт.")
    parser.add_argument("--validate-only", action="store_true", help="Проверить анкету и выйти без запуска сервера.")
    parser.add_argument("--print-demo", action="store_true", help="Вывести JSON встроенной демо-анкеты и выйти.")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Удалить сгенерированные файлы анкеты из --out-dir и выйти. .gitignore сохраняется.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.print_demo:
        print(json.dumps(DEFAULT_DEMO_QUESTIONNAIRE, ensure_ascii=False, indent=2))
        return 0

    if args.cleanup:
        try:
            deleted = cleanup_questionnaire_dir(args.out_dir)
        except OSError as exc:
            print(f"ERROR: Не удалось очистить '{args.out_dir}': {exc}", file=sys.stderr)
            return 2
        print(f"Очистка завершена для: {args.out_dir}")
        print("Сохранено: .gitignore")
        if deleted:
            print("Удалено:")
            for path in deleted:
                print(f"- {path}")
        else:
            print("Удалено: ничего")
        return 0

    try:
        questionnaire = load_questionnaire(args.input)
    except QuestionnaireError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.input is None:
        print("Параметр --input не указан; используется встроенная демо-анкета только для проверки.", file=sys.stderr)

    if args.validate_only:
        source = str(args.input) if args.input else "embedded demo"
        print(f"PASS: анкета корректна ({source})")
        return 0

    try:
        ensure_work_dir(args.out_dir)
    except OSError as exc:
        print(f"ERROR: Не удалось подготовить папку ответов '{args.out_dir}': {exc}", file=sys.stderr)
        return 2

    try:
        httpd = QuestionnaireHTTPServer((HOST, args.port), QuestionnaireHandler, questionnaire, args.out_dir, args.input)
    except OSError as exc:
        print(f"ERROR: Не удалось запустить сервер на {HOST}:{args.port}: {exc}", file=sys.stderr)
        return 2

    actual_port = httpd.server_address[1]
    url = f"http://{HOST}:{actual_port}/"
    print("")
    print(f"Анкета запущена по адресу: {url}")
    print(f"Сервер слушает только: {HOST}")
    print(f"Ответы будут сохранены в: {args.out_dir / 'answers.json'}")
    print(f"Markdown-сводка будет сохранена в: {args.out_dir / 'answers.md'}")
    print("Нажмите Ctrl+C, чтобы остановить сервер.")
    print("", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        httpd.server_close()
    return 0


HTML_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f5f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #596575;
      --border: #d7dee7;
      --accent: #0f766e;
      --accent-strong: #0b5f59;
      --accent-soft: #e0f2f1;
      --danger: #b42318;
      --success: #067647;
      --shadow: 0 12px 36px rgba(23, 32, 42, 0.12);
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111827;
        --panel: #1f2937;
        --text: #f8fafc;
        --muted: #bac4d1;
        --border: #3f4a5a;
        --accent: #5eead4;
        --accent-strong: #99f6e4;
        --accent-soft: #134e4a;
        --danger: #fda29b;
        --success: #86efac;
        --shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
      }
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }

    main {
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 32px 18px 56px;
    }

    header {
      margin-bottom: 20px;
    }

    h1 {
      margin: 0 0 10px;
      font-size: clamp(1.65rem, 4vw, 2.4rem);
      line-height: 1.12;
      letter-spacing: 0;
    }

    .description, .context, .help, .status-line {
      color: var(--muted);
    }

    .context {
      margin-top: 12px;
      padding: 12px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: color-mix(in srgb, var(--panel) 75%, var(--bg));
      white-space: pre-wrap;
    }

    .progress-wrap {
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 12px 0;
      background: var(--bg);
    }

    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.94rem;
    }

    .progress-track {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: color-mix(in srgb, var(--border) 70%, transparent);
    }

    .progress-bar {
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width 160ms ease;
    }

    form {
      display: grid;
      gap: 16px;
    }

    .question {
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .question[hidden] { display: none; }

    .question-title {
      display: flex;
      gap: 8px;
      align-items: baseline;
      margin: 0 0 6px;
      font-size: 1.08rem;
      font-weight: 700;
      letter-spacing: 0;
    }

    .required {
      color: var(--danger);
      font-weight: 700;
    }

    .help {
      margin: 0 0 14px;
      font-size: 0.95rem;
    }

    .options {
      display: grid;
      gap: 10px;
    }

    .option {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      align-items: start;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      cursor: pointer;
      background: color-mix(in srgb, var(--panel) 85%, var(--bg));
    }

    .option:hover {
      border-color: var(--accent);
    }

    .option input {
      margin-top: 3px;
    }

    .option-label {
      display: block;
      font-weight: 650;
    }

    .recommended {
      display: inline-block;
      margin-left: 8px;
      color: var(--accent-strong);
      font-size: 0.86rem;
      font-weight: 700;
    }

    .option-help {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 0.92rem;
    }

    input[type="text"], textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 13px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }

    textarea {
      min-height: 120px;
      resize: vertical;
    }

    .other-input {
      grid-column: 2;
      margin-top: 4px;
    }

    .other-input[hidden] {
      display: none;
    }

    .comment {
      margin-top: 14px;
    }

    .comment label {
      display: block;
      margin-bottom: 6px;
      font-weight: 650;
    }

    .comment textarea {
      min-height: 76px;
    }

    .scale {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .scale label {
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      border: 1px solid var(--border);
      border-radius: 8px;
      cursor: pointer;
      background: color-mix(in srgb, var(--panel) 85%, var(--bg));
      font-weight: 700;
    }

    .scale input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }

    .scale label:has(input:checked) {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent-strong);
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
    }

    button {
      border: 0;
      border-radius: 8px;
      padding: 11px 16px;
      background: var(--accent);
      color: #ffffff;
      font: inherit;
      font-weight: 750;
      cursor: pointer;
    }

    button:hover {
      background: var(--accent-strong);
    }

    .ghost {
      border: 1px solid var(--border);
      background: transparent;
      color: var(--text);
    }

    .ghost:hover {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent-strong);
    }

    .message {
      width: 100%;
      padding: 12px 14px;
      border-radius: 8px;
      display: none;
    }

    .message.show { display: block; }
    .message.success {
      border: 1px solid color-mix(in srgb, var(--success) 70%, var(--border));
      color: var(--success);
      background: color-mix(in srgb, var(--success) 12%, transparent);
    }
    .message.error {
      border: 1px solid color-mix(in srgb, var(--danger) 70%, var(--border));
      color: var(--danger);
      background: color-mix(in srgb, var(--danger) 12%, transparent);
    }

    .summary {
      margin-top: 16px;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      display: none;
    }

    .summary.show { display: block; }
    .summary h2 { margin: 0 0 12px; font-size: 1.25rem; }
    .summary dl { display: grid; gap: 12px; margin: 0; }
    .summary dt { font-weight: 750; }
    .summary dd { margin: 4px 0 0; color: var(--muted); white-space: pre-wrap; }

    @media (max-width: 640px) {
      main { padding: 22px 12px 44px; }
      .question, .actions, .summary { padding: 14px; }
      .option { grid-template-columns: 24px 1fr; }
      .other-input { grid-column: 1 / -1; }
      .progress-wrap { padding-top: 8px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1 id="title"></h1>
      <p class="description" id="description"></p>
      <div class="context" id="context" hidden></div>
    </header>

    <div class="progress-wrap" aria-live="polite">
      <div class="progress-meta">
        <span id="progressText">Отвечено: 0 из 0</span>
        <span id="draftStatus">Автосохранение черновика готово</span>
      </div>
      <div class="progress-track" aria-hidden="true"><div class="progress-bar" id="progressBar"></div></div>
    </div>

    <form id="form"></form>

    <section class="actions">
      <button type="button" id="saveButton">Сохранить ответы</button>
      <button type="button" class="ghost" id="clearDraftButton">Очистить локальный черновик</button>
      <span class="status-line">После сохранения файлы появятся в локальной папке проекта.</span>
      <div class="message" id="message"></div>
    </section>

    <section class="summary" id="summary">
      <h2>Сводка ответов</h2>
      <dl id="summaryList"></dl>
    </section>
  </main>

  <script id="questionnaire-data" type="application/json">__QUESTIONNAIRE_JSON__</script>
  <script>
    const questionnaire = JSON.parse(document.getElementById("questionnaire-data").textContent);
    const storageKey = "codex-questionnaire:" + questionnaire.title + ":" + questionnaire.questions.map(q => q.id).join(",");
    const answers = {};
    const form = document.getElementById("form");
    const title = document.getElementById("title");
    const description = document.getElementById("description");
    const context = document.getElementById("context");
    const progressText = document.getElementById("progressText");
    const progressBar = document.getElementById("progressBar");
    const draftStatus = document.getElementById("draftStatus");
    const message = document.getElementById("message");
    const summary = document.getElementById("summary");
    const summaryList = document.getElementById("summaryList");

    function optionList(question) {
      const options = Array.isArray(question.options) ? question.options.slice() : [];
      if (question.allow_recommend) {
        options.push({ value: "__not_sure__", label: "Не уверен / порекомендуй сам" });
      }
      if (question.allow_other) {
        options.push({ value: "__other__", label: "Другое / свой вариант" });
      }
      return options;
    }

    function initialAnswer(question) {
      if (question.type === "multiple_choice") {
        return { value: Array.isArray(question.default) ? question.default.slice() : [], other_text: "", comment: "" };
      }
      if (Object.prototype.hasOwnProperty.call(question, "default")) {
        return { value: question.default, other_text: "", comment: "" };
      }
      return { value: "", other_text: "", comment: "" };
    }

    function normalizeAnswer(question, raw) {
      const base = initialAnswer(question);
      if (!raw || typeof raw !== "object") return base;
      if (Object.prototype.hasOwnProperty.call(raw, "value")) base.value = raw.value;
      if (Object.prototype.hasOwnProperty.call(raw, "other_text")) base.other_text = raw.other_text || "";
      else if (Object.prototype.hasOwnProperty.call(raw, "other")) base.other_text = raw.other || "";
      if (Object.prototype.hasOwnProperty.call(raw, "comment")) base.comment = raw.comment || "";
      if (question.type === "multiple_choice" && !Array.isArray(base.value)) base.value = [];
      return base;
    }

    function initializeAnswers() {
      for (const question of questionnaire.questions) {
        answers[question.id] = initialAnswer(question);
      }

      try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && parsed.answers) {
            for (const question of questionnaire.questions) {
              if (parsed.answers[question.id]) {
                answers[question.id] = normalizeAnswer(question, parsed.answers[question.id]);
              }
            }
            draftStatus.textContent = "Локальный черновик восстановлен";
          }
        }
      } catch {
        draftStatus.textContent = "Не удалось восстановить локальный черновик";
      }
    }

    function saveDraft() {
      try {
        localStorage.setItem(storageKey, JSON.stringify({ answers, updated_at: new Date().toISOString() }));
        draftStatus.textContent = "Черновик сохранен локально";
      } catch {
        draftStatus.textContent = "Не удалось сохранить черновик";
      }
    }

    function answerValues(answer) {
      if (!answer) return [];
      const value = answer.value;
      if (Array.isArray(value)) return value;
      if (value === undefined || value === null || value === "") return [];
      return [value];
    }

    function hasAnswer(question) {
      const answer = answers[question.id];
      if (!answer) return false;
      const value = answer.value;
      if (Array.isArray(value)) {
        if (value.length === 0) return false;
        if (value.includes("__other__")) {
          return value.some(item => item !== "__other__") || String(answer.other_text || "").trim().length > 0;
        }
        return true;
      }
      if (value === "__other__") return String(answer.other_text || "").trim().length > 0;
      return value !== undefined && value !== null && value !== "";
    }

    function selectedOtherWithoutText(question) {
      const answer = answers[question.id];
      if (!answer || (question.type !== "single_choice" && question.type !== "multiple_choice")) return false;
      const values = answerValues(answer);
      return values.includes("__other__") && String(answer.other_text || "").trim().length === 0;
    }

    function matches(actual, expected) {
      if (Array.isArray(expected)) return expected.some(item => actual.includes(item));
      return actual.includes(expected);
    }

    function isVisible(question) {
      const rule = question.show_if;
      if (!rule) return true;
      const dependency = questionnaire.questions.find(q => q.id === rule.question_id);
      const actual = answerValues(answers[rule.question_id]);
      if (Object.prototype.hasOwnProperty.call(rule, "equals")) return matches(actual, rule.equals);
      if (Object.prototype.hasOwnProperty.call(rule, "includes")) return matches(actual, rule.includes);
      if (Object.prototype.hasOwnProperty.call(rule, "not_equals")) return !matches(actual, rule.not_equals);
      if (Object.prototype.hasOwnProperty.call(rule, "is_answered")) return dependency ? hasAnswer(dependency) === rule.is_answered : false;
      return true;
    }

    function textNode(text) {
      return document.createTextNode(text == null ? "" : String(text));
    }

    function appendText(parent, text) {
      parent.appendChild(textNode(text));
    }

    function makeQuestionShell(question) {
      const section = document.createElement("section");
      section.className = "question";
      section.dataset.questionId = question.id;

      const heading = document.createElement("h2");
      heading.className = "question-title";
      appendText(heading, question.title);
      if (question.required) {
        const required = document.createElement("span");
        required.className = "required";
        required.textContent = "*";
        required.title = "Обязательный вопрос";
        heading.appendChild(required);
      }
      section.appendChild(heading);

      if (question.help_text) {
        const help = document.createElement("p");
        help.className = "help";
        help.textContent = question.help_text;
        section.appendChild(help);
      }

      return section;
    }

    function appendComment(section, question) {
      const wrap = document.createElement("div");
      wrap.className = "comment";

      const label = document.createElement("label");
      label.setAttribute("for", `comment-${question.id}`);
      label.textContent = "Комментарий к ответу";

      const textarea = document.createElement("textarea");
      textarea.id = `comment-${question.id}`;
      textarea.placeholder = "Можно добавить уточнение, ограничение или пояснение…";
      textarea.value = (answers[question.id] && answers[question.id].comment) || "";
      textarea.addEventListener("input", () => {
        answers[question.id].comment = textarea.value;
        saveDraft();
      });

      wrap.appendChild(label);
      wrap.appendChild(textarea);
      section.appendChild(wrap);
    }

    function renderChoice(question, multiple) {
      const section = makeQuestionShell(question);
      const wrap = document.createElement("div");
      wrap.className = "options";
      const current = answers[question.id] || initialAnswer(question);

      for (const option of optionList(question)) {
        const label = document.createElement("label");
        label.className = "option";
        const input = document.createElement("input");
        input.type = multiple ? "checkbox" : "radio";
        input.name = question.id;
        input.value = option.value;

        const values = multiple ? (Array.isArray(current.value) ? current.value : []) : [current.value];
        input.checked = values.includes(option.value);

        input.addEventListener("change", () => {
          if (multiple) {
            const selected = Array.from(wrap.querySelectorAll("input[type=checkbox]:checked")).map(item => item.value);
            answers[question.id].value = selected;
          } else {
            answers[question.id].value = option.value;
          }
          saveDraft();
          refresh();
        });

        const content = document.createElement("span");
        const optionLabel = document.createElement("span");
        optionLabel.className = "option-label";
        appendText(optionLabel, option.label);
        const rec = question.recommended;
        const isRecommended = Array.isArray(rec) ? rec.includes(option.value) : rec === option.value;
        if (isRecommended) {
          const badge = document.createElement("span");
          badge.className = "recommended";
          badge.textContent = "рекомендуемый вариант";
          optionLabel.appendChild(badge);
        }
        content.appendChild(optionLabel);

        if (option.help_text) {
          const help = document.createElement("span");
          help.className = "option-help";
          help.textContent = option.help_text;
          content.appendChild(help);
        }

        label.appendChild(input);
        label.appendChild(content);
        wrap.appendChild(label);

        if (option.value === "__other__") {
          const other = document.createElement("textarea");
          other.className = "other-input";
          other.dataset.questionId = question.id;
          other.placeholder = "Напишите свой вариант…";
          other.value = current.other_text || "";
          other.hidden = !input.checked;
          other.addEventListener("input", () => {
            answers[question.id].other_text = other.value;
            if (multiple) {
              if (other.value.trim() && !answers[question.id].value.includes("__other__")) {
                answers[question.id].value.push("__other__");
                input.checked = true;
              }
            } else if (other.value.trim()) {
              answers[question.id].value = "__other__";
              input.checked = true;
            }
            saveDraft();
            refresh();
          });
          label.appendChild(other);
        }
      }

      section.appendChild(wrap);
      appendComment(section, question);
      return section;
    }

    function renderText(question, textarea) {
      const section = makeQuestionShell(question);
      const input = document.createElement(textarea ? "textarea" : "input");
      if (!textarea) input.type = "text";
      input.value = (answers[question.id] && answers[question.id].value) || "";
      input.addEventListener("input", () => {
        answers[question.id].value = input.value;
        saveDraft();
        refresh();
      });
      section.appendChild(input);
      appendComment(section, question);
      return section;
    }

    function renderScale(question) {
      const section = makeQuestionShell(question);
      const wrap = document.createElement("div");
      wrap.className = "scale";
      const min = question.min || 1;
      const max = question.max || 5;
      const current = answers[question.id] || { value: "" };
      for (let value = min; value <= max; value += 1) {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "radio";
        input.name = question.id;
        input.value = String(value);
        input.checked = Number(current.value) === value;
        input.addEventListener("change", () => {
          answers[question.id].value = value;
          saveDraft();
          refresh();
        });
        label.appendChild(input);
        appendText(label, value);
        if (question.recommended === value) label.title = "Рекомендуемый вариант";
        wrap.appendChild(label);
      }
      section.appendChild(wrap);
      appendComment(section, question);
      return section;
    }

    function renderForm() {
      title.textContent = questionnaire.title;
      description.textContent = questionnaire.description || "";
      if (questionnaire.project_context) {
        context.hidden = false;
        context.textContent = typeof questionnaire.project_context === "string"
          ? questionnaire.project_context
          : JSON.stringify(questionnaire.project_context, null, 2);
      }

      form.textContent = "";
      for (const question of questionnaire.questions) {
        let node;
        if (question.type === "single_choice") node = renderChoice(question, false);
        else if (question.type === "multiple_choice") node = renderChoice(question, true);
        else if (question.type === "textarea") node = renderText(question, true);
        else if (question.type === "scale") node = renderScale(question);
        else node = renderText(question, false);
        form.appendChild(node);
      }
    }

    function refresh() {
      let visible = 0;
      let answered = 0;
      for (const question of questionnaire.questions) {
        const node = form.querySelector(`[data-question-id="${CSS.escape(question.id)}"]`);
        const show = isVisible(question);
        if (node) node.hidden = !show;
        if (show) {
          visible += 1;
          if (hasAnswer(question)) answered += 1;
        }
        if (node) {
          const otherInput = node.querySelector(".other-input");
          if (otherInput) otherInput.hidden = !answerValues(answers[question.id]).includes("__other__");
        }
      }
      progressText.textContent = `Отвечено: ${answered} из ${visible}`;
      progressBar.style.width = visible ? `${Math.round((answered / visible) * 100)}%` : "0%";
    }

    function validate_required() {
      const missing = [];
      const missingOther = [];
      for (const question of questionnaire.questions) {
        if (isVisible(question) && question.required && !hasAnswer(question)) {
          missing.push(question.title);
        }
        if (isVisible(question) && selectedOtherWithoutText(question)) {
          missingOther.push(question.title);
        }
      }
      return { missing, missingOther };
    }

    function showMessage(kind, text) {
      message.className = `message show ${kind}`;
      message.textContent = text;
    }

    function answerDisplay(item) {
      if (Array.isArray(item.display_value)) return item.display_value.join("\\n");
      return item.display_value || "Нет ответа";
    }

    function render_svodka(items) {
      summaryList.textContent = "";
      for (const item of items.filter(entry => entry.visible)) {
        const dt = document.createElement("dt");
        dt.textContent = item.title;
        const dd = document.createElement("dd");
        const comment = item.comment ? `\\nКомментарий: ${item.comment}` : "";
        dd.textContent = answerDisplay(item) + comment;
        summaryList.appendChild(dt);
        summaryList.appendChild(dd);
      }
      summary.classList.add("show");
    }

    async function saveAnswers() {
      const validation = validate_required();
      if (validation.missingOther.length) {
        showMessage("error", "Введите свой вариант или выберите другой ответ.");
        return;
      }
      if (validation.missing.length) {
        showMessage("error", "Ответьте на обязательные вопросы: " + validation.missing.join("; "));
        return;
      }
      showMessage("success", "Сохраняю ответы…");
      try {
        const response = await fetch("/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answers })
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Не удалось сохранить ответы");
        }
        showMessage("success", `Ответы сохранены. Файлы answers.json и answers.md записаны локально: ${result.saved_at}.`);
        render_svodka(result.answers || []);
      } catch (error) {
        showMessage("error", error.message || String(error));
      }
    }

    function clearDraft() {
      localStorage.removeItem(storageKey);
      initializeAnswers();
      renderForm();
      refresh();
      showMessage("success", "Локальный черновик очищен. Сохраненные файлы ответов не изменены.");
    }

    initializeAnswers();
    renderForm();
    refresh();
    document.getElementById("saveButton").addEventListener("click", saveAnswers);
    document.getElementById("clearDraftButton").addEventListener("click", clearDraft);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
