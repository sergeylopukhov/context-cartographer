#!/usr/bin/env python3
"""Smoke tests for the interactive project questionnaire skill."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPT_PATH = Path(__file__).with_name("questionnaire_server.py")
UPDATE_SCRIPT_PATH = Path(__file__).with_name("check_update.py")
FILE_TEMPLATES_PATH = Path(__file__).parents[1] / "references" / "file-templates.md"
SKILL_PATH = Path(__file__).parents[1] / "SKILL.md"
SETUP_WORKFLOW_PATH = Path(__file__).parents[1] / "references" / "setup-workflow.md"
EXISTING_WORKFLOW_PATH = Path(__file__).parents[1] / "references" / "existing-docs-workflow.md"
REPOSITORY_ROOT = Path(__file__).parents[2]
CLAUDE_ADAPTER_PATH = REPOSITORY_ROOT / "adapters" / "claude" / "CLAUDE.md"
CURSOR_ADAPTER_PATH = REPOSITORY_ROOT / "adapters" / "cursor" / "context-cartographer.mdc"


def load_server_module():
    spec = importlib.util.spec_from_file_location("questionnaire_server", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_update_module():
    spec = importlib.util.spec_from_file_location("check_update", UPDATE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {UPDATE_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pass_line(message: str) -> None:
    print(f"PASS: {message}")


def fail_line(message: str) -> None:
    print(f"FAIL: {message}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def parse_simple_frontmatter(text: str, source: str) -> dict[str, str]:
    lines = text.splitlines()
    assert_true(lines and lines[0] == "---", f"{source} frontmatter is missing")

    values: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return values
        if not line or line.startswith((" ", "\t")):
            continue
        assert_true(":" in line, f"{source} has malformed frontmatter: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        assert_true(key not in values, f"{source} has duplicate frontmatter key: {key}")
        values[key] = value.strip().strip("\"'")

    raise AssertionError(f"{source} frontmatter is not closed")


def main() -> int:
    try:
        server = load_server_module()
        pass_line("questionnaire_server.py imports cleanly")

        updater = load_update_module()
        local_version = updater.read_local_version()
        assert_true(local_version, "local VERSION was not read")
        assert_true(updater.is_newer("0.1.1", "0.1.0"), "newer patch version was not detected")
        assert_true(not updater.is_newer("0.1.0", "0.1.0"), "same version was treated as newer")
        assert_true(updater.should_check({}, 1, False), "empty cache should trigger update check")
        assert_true(not updater.should_check({"checked_at": updater.time.time()}, 1, False), "fresh cache should skip update check")
        pass_line("check_update.py imports and compares versions")

        file_templates = FILE_TEMPLATES_PATH.read_text(encoding="utf-8")
        skill_text = SKILL_PATH.read_text(encoding="utf-8")
        setup_workflow = SETUP_WORKFLOW_PATH.read_text(encoding="utf-8")
        existing_workflow = EXISTING_WORKFLOW_PATH.read_text(encoding="utf-8")
        skill_frontmatter = parse_simple_frontmatter(skill_text, "SKILL.md")
        assert_true(
            len(skill_text.encode("utf-8")) <= 10_000,
            "SKILL.md exceeded the token-conscious 10 KB limit",
        )
        assert_true(
            "Do not use for routine edits" in skill_frontmatter.get("description", ""),
            "skill metadata does not exclude routine documentation edits",
        )
        assert_true(
            "automatic durable documentation maintenance already governed by project root instructions" in skill_text,
            "skill metadata does not preserve independent automatic maintenance",
        )
        assert_true(
            "always read `references/setup-workflow.md`" in skill_text
            and "always read `references/existing-docs-workflow.md`" in skill_text,
            "SKILL.md does not require the scenario workflows",
        )
        for required_setup_rule in (
            "Do not infer code-rules mode or documentation maintenance mode",
            "Create `docs/architecture.md` as a concise documentation map",
            "Require later agents to invoke `context-cartographer` before creating a new owner document",
        ):
            assert_true(required_setup_rule in setup_workflow, f"setup workflow lost rule: {required_setup_rule}")
        for required_existing_rule in (
            "Do not create a new Markdown file during routine maintenance",
            "Do not require a general cleanup strategy",
            "Ask for approval before creating the new owner",
            "Add the new owner to `docs/architecture.md`",
        ):
            assert_true(
                required_existing_rule in existing_workflow,
                f"existing-docs workflow lost rule: {required_existing_rule}",
            )
        assert_true(
            "resolve the project root once" in file_templates,
            "root agent template does not require project-root path resolution",
        )
        assert_true(
            "Do not read the same full file again" in file_templates,
            "root agent template does not prevent unnecessary full-file rereads",
        )
        assert_true(
            "Do not invoke `context-cartographer` for routine edits or automatic durable maintenance" in file_templates,
            "root agent template still routes routine maintenance through the skill",
        )
        assert_true(
            "If maintenance mode is `automatic durable maintenance`" in file_templates,
            "root agent template lost automatic durable maintenance",
        )
        assert_true(
            "do not create it during routine maintenance" in file_templates
            and "Invoke `context-cartographer`" in file_templates,
            "root agent template does not route missing ownership through the skill",
        )
        if CLAUDE_ADAPTER_PATH.exists() and CURSOR_ADAPTER_PATH.exists():
            claude_adapter = CLAUDE_ADAPTER_PATH.read_text(encoding="utf-8")
            cursor_adapter = CURSOR_ADAPTER_PATH.read_text(encoding="utf-8")
            cursor_frontmatter = parse_simple_frontmatter(cursor_adapter, "Cursor adapter")
            for durable_trigger in (
                "durable behavior",
                "setup",
                "data-model",
                "agent-workflow",
                "documentation-ownership",
            ):
                assert_true(
                    durable_trigger in claude_adapter and durable_trigger in cursor_adapter,
                    f"Claude or Cursor adapter lost durable maintenance trigger: {durable_trigger}",
                )
            assert_true(
                cursor_frontmatter.get("alwaysApply") == "true",
                "Cursor root rule must always load to preserve automatic durable maintenance",
            )
            assert_true(
                "do not invoke the skill when ownership is already clear" in claude_adapter
                and "do not invoke the skill when ownership is already clear" in cursor_adapter,
                "Claude or Cursor adapter still routes routine maintenance through the skill",
            )
            assert_true(
                "If no existing owner fits" in claude_adapter and "If no existing owner fits" in cursor_adapter,
                "Claude or Cursor adapter does not route missing ownership through the skill",
            )
        pass_line("skill routing is narrow while root instructions preserve automatic maintenance")

        valid_questionnaire = {
            "title": "Тестовая анкета",
            "description": "Корректная анкета для smoke-теста.",
            "language": "ru",
            "project_context": {"project": "тест"},
            "metadata": {"suite": "smoke"},
            "questions": [
                {
                    "id": "audience",
                    "title": "Для кого это нужно?",
                    "type": "single_choice",
                    "required": True,
                    "recommended": "founders",
                    "allow_other": True,
                    "allow_recommend": True,
                    "options": [
                        {"value": "founders", "label": "Основатели"},
                        {"value": "teams", "label": "Внутренние команды"},
                    ],
                },
                {
                    "id": "channels",
                    "title": "Какие каналы важны?",
                    "type": "multiple_choice",
                    "required": True,
                    "default": ["email"],
                    "allow_other": True,
                    "options": [
                        {"value": "email", "label": "Email"},
                        {"value": "telegram", "label": "Telegram"},
                        {"value": "web", "label": "Веб"},
                    ],
                },
                {
                    "id": "telegram_detail",
                    "title": "Что должен делать Telegram?",
                    "type": "text",
                    "required": True,
                    "show_if": {
                        "question_id": "channels",
                        "includes": "telegram",
                    },
                },
                {
                    "id": "notes",
                    "title": "Заметки",
                    "type": "textarea",
                    "required": False,
                    "default": "Сделать проще.",
                },
                {
                    "id": "confidence",
                    "title": "Уверенность",
                    "type": "scale",
                    "min": 1,
                    "max": 5,
                    "default": 3,
                    "required": True,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            valid_path = temp_dir / "questions.json"
            valid_path.write_text(json.dumps(valid_questionnaire, indent=2), encoding="utf-8")

            loaded = server.load_questionnaire(valid_path)
            assert_true(loaded["title"] == "Тестовая анкета", "valid questionnaire title was not preserved")
            assert_true(len(loaded["questions"]) == 5, "valid questionnaire question count changed")
            pass_line("valid questionnaire parses and validates")

            direct = server.validate_questionnaire(valid_questionnaire)
            assert_true(direct["questions"][0]["id"] == "audience", "direct validation returned unexpected data")
            pass_line("schema validation accepts valid data")

            english_questionnaire = dict(valid_questionnaire)
            english_questionnaire["title"] = "Smoke Test Questionnaire"
            english_questionnaire["description"] = "Valid questionnaire for smoke tests."
            english_questionnaire.pop("language")
            english_loaded = server.validate_questionnaire(english_questionnaire)
            assert_true(english_loaded["language"] == "en", "default language should be English")
            assert_true(english_loaded["ui"]["other_label"] == "Other / custom answer", "English other label missing")
            english_html = server.build_html(english_loaded)
            assert_true("Save answers" in english_html, "English save button missing")
            assert_true("Other / custom answer" in english_html, "English other option label missing")
            assert_true("Сохранить ответы" not in english_html, "Russian save button leaked into English default UI")
            pass_line("English is the default UI language")

            malformed_path = temp_dir / "malformed.json"
            malformed_path.write_text('{"title": "Broken", "questions": [', encoding="utf-8")
            try:
                server.load_questionnaire(malformed_path)
            except server.QuestionnaireError as exc:
                assert_true("Malformed JSON" in str(exc), "malformed JSON error was not clean")
                pass_line("malformed JSON produces a clean failure")
            else:
                raise AssertionError("malformed JSON unexpectedly passed")

            answers = {
                "audience": {
                    "value": "__other__",
                    "other_text": "Руководители продуктовых команд",
                    "comment": "Не только основатели.",
                },
                "channels": {
                    "value": ["email", "telegram", "__other__"],
                    "other_text": "Партнерские рекомендации",
                    "comment": "Email нужен для отчетов.",
                },
                "telegram_detail": {"value": "Отправлять уведомления и собирать ответы.", "comment": ""},
                "notes": {"value": "Сначала MVP.", "comment": "Без лишней сложности."},
                "confidence": {"value": 4, "comment": "Достаточно уверенно."},
            }
            output, markdown = server.build_answer_documents(loaded, answers, source_path=valid_path)
            assert_true(output["answers"][0]["other_selected"] is True, "allow_other was not preserved")
            assert_true(output["answers"][0]["other_text"] == "Руководители продуктовых команд", "single_choice other_text was not saved")
            assert_true(output["answers"][1]["other_text"] == "Партнерские рекомендации", "multiple_choice other_text was not saved")
            assert_true(output["answers"][1]["comment"] == "Email нужен для отчетов.", "per-question comment was not saved")
            assert_true("Руководители продуктовых команд" in markdown, "single_choice other_text missing from answers.md")
            assert_true("Партнерские рекомендации" in markdown, "multiple_choice other_text missing from answers.md")
            assert_true("Email нужен для отчетов." in markdown, "comment missing from answers.md")
            assert_true("Отправлять уведомления и собирать ответы." in markdown, "answers.md did not include conditional answer")
            pass_line("answers.md generation works")

            invalid_other = dict(answers)
            invalid_other["audience"] = {"value": "__other__", "other_text": "", "comment": ""}
            try:
                server.build_answer_documents(loaded, invalid_other, source_path=valid_path)
            except server.QuestionnaireError as exc:
                assert_true(
                    "Введите свой вариант или выберите другой ответ." in str(exc),
                    "empty other_text did not produce the Russian validation message",
                )
                pass_line("empty other answer has a Russian validation message")
            else:
                raise AssertionError("empty other_text unexpectedly passed validation")

            html = server.build_html(loaded)
            assert_true(
                "JSON.stringify(questionnaire.project_context" not in html,
                "project_context should not be rendered as visible raw JSON in the form",
            )
            assert_true('context.textContent = "";' in html, "project_context display should be cleared in the form")
            for expected in (
                "Сохранить ответы",
                "Очистить локальный черновик",
                "Сводка ответов",
                "Другое / свой вариант",
                "Не уверен / порекомендуй сам",
                "Комментарий к ответу",
                "Можно добавить уточнение, ограничение или пояснение...",
                "Введите свой вариант или выберите другой ответ.",
                "Рекомендуемый вариант",
                "Обязательный вопрос",
            ):
                assert_true(expected in html, f"Russian UI label missing: {expected}")
            pass_line("Russian UI labels are present when language is ru")

            out_dir = temp_dir / ".project-questionnaire"
            save_result = server.save_answers(loaded, answers, out_dir, source_path=valid_path)
            assert_true((out_dir / ".gitignore").read_text(encoding="utf-8") == "*\n!.gitignore\n", ".gitignore was not created")
            assert_true((out_dir / "answers.json").exists(), "answers.json was not written")
            assert_true((out_dir / "answers.md").exists(), "answers.md was not written")
            assert_true(save_result["backups"] == [], "first save should not create backups")
            server.save_answers(loaded, answers, out_dir, source_path=valid_path)
            assert_true(any(path.name.startswith("answers.json.backup-") for path in out_dir.iterdir()), "backup was not created")
            pass_line("save creates .gitignore, answers files, and backups")

            (out_dir / "questions.json").write_text("{}", encoding="utf-8")
            (out_dir / "keep.txt").write_text("keep", encoding="utf-8")
            deleted = server.cleanup_questionnaire_dir(out_dir)
            assert_true((out_dir / ".gitignore").exists(), "cleanup removed .gitignore")
            assert_true(not (out_dir / "answers.json").exists(), "cleanup did not remove answers.json")
            assert_true(not (out_dir / "answers.md").exists(), "cleanup did not remove answers.md")
            assert_true(not (out_dir / "questions.json").exists(), "cleanup did not remove questions.json")
            assert_true((out_dir / "keep.txt").exists(), "cleanup removed a non-generated file")
            assert_true(any("answers.json" in path for path in deleted), "cleanup did not report deleted answers")
            pass_line("explicit cleanup removes generated files and keeps .gitignore")

        print("PASS: all smoke tests passed")
        return 0

    except Exception as exc:
        fail_line(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
