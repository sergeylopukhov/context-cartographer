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


def load_server_module():
    spec = importlib.util.spec_from_file_location("questionnaire_server", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
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


def main() -> int:
    try:
        server = load_server_module()
        pass_line("questionnaire_server.py imports cleanly")

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
