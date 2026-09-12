#!/usr/bin/env python3
"""Packaging and self-containment tests for the context-cartographer skill.

The tests copy only the installable ``context-cartographer`` package into a
temporary directory (no repository README, no top-level ``adapters`` folder)
and run the packaged helpers from another working directory. When a supported
route or contract disappears from the package, the smoke test must fail instead
of reporting a skip as success.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_skill  # noqa: E402  (imported after the sys.path bootstrap)

CURSOR_ROUTE_TOKEN = ".cursor/rules/context-cartographer.mdc"
REQUIRED_OWNER_PHRASE = "without asking merely for permission to create a Markdown file"
LOCAL_SUFFICIENCY_PHRASE = (
    "the local project instructions and existing owner documents suffice"
)
TEMPLATES_DIR = PACKAGE_DIR / "references" / "templates"


def copy_package(destination: Path) -> Path:
    installed = destination / "context-cartographer"
    shutil.copytree(
        PACKAGE_DIR,
        installed,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return installed


def run_script(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def tree_snapshot(root: Path) -> dict[str, str]:
    """Map each file under ``root`` to a content digest, to detect writes."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[path.relative_to(root).as_posix()] = digest
    return snapshot


def strip_phrase(installed: Path, phrase: str) -> None:
    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    for path in sorted((installed / "references").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub("", text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def find_root_template(installed: Path) -> Path:
    for name in ("root-instructions.md", "root-agents.md"):
        candidate = installed / "references" / "templates" / name
        if candidate.is_file():
            return candidate
    raise AssertionError("the routed root instruction template is missing")


def find_router_doc(installed: Path) -> Path:
    link_re = re.compile(r"\]\(templates/[A-Za-z0-9._-]+\.md\)")
    for path in sorted((installed / "references").rglob("*.md")):
        if link_re.search(path.read_text(encoding="utf-8")):
            return path
    raise AssertionError("no reference document links the split templates")


def strip_always_apply(installed: Path) -> None:
    path = find_root_template(installed)
    key_re = re.compile(r"^alwaysApply\s*:\s*true\s*$", re.IGNORECASE)
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not key_re.match(line.strip())
    ]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def break_root_adapter_link(installed: Path) -> None:
    path = find_root_template(installed)
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r"\]\((?:\.\./\.\./)?docs/documentation-rules\.md\)",
        "](../docs/missing-rules.md)",
        text,
    )
    if updated == text:
        raise AssertionError("the root adapter has no real link to the contract")
    path.write_text(updated, encoding="utf-8")


def add_second_maintenance_mode(installed: Path) -> None:
    path = find_root_template(installed)
    text = path.read_text(encoding="utf-8")
    needle = "Maintenance mode: `automatic durable maintenance`."
    if needle not in text:
        raise AssertionError("the root template has no maintenance mode bullet")
    path.write_text(
        text.replace(
            needle,
            needle + "\n- Maintenance mode: `request-only maintenance`.",
            1,
        ),
        encoding="utf-8",
    )


def make_cursor_link_nonrelative(installed: Path) -> None:
    path = find_root_template(installed)
    text = path.read_text(encoding="utf-8")
    needle = "](../../docs/documentation-rules.md)"
    if needle not in text:
        raise AssertionError("the Cursor body has no project-relative contract link")
    path.write_text(
        text.replace(needle, "](docs/documentation-rules.md)", 1), encoding="utf-8"
    )


def ship_code_rules_row_in_main_map(installed: Path) -> None:
    path = installed / "references" / "templates" / "documentation-map.md"
    text = path.read_text(encoding="utf-8")
    needle = "## Topic Map\n"
    if needle not in text:
        raise AssertionError("the map template has no topic map section")
    row = (
        "| code.rules | Code-editing rules | [Code Rules](code_rules.md) | "
        "Changing code |\n"
    )
    path.write_text(text.replace(needle, needle + "\n" + row, 1), encoding="utf-8")


class SkillPackagingTests(unittest.TestCase):
    def test_installed_package_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)

            self.assertFalse((workdir / "README.md").exists())
            self.assertFalse((workdir / "adapters").exists())
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "VERSION").is_file())
            self.assertTrue((installed / "references").is_dir())
            self.assertTrue((installed / "scripts").is_dir())

    def test_validate_skill_runs_from_another_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            result = run_script(
                installed / "scripts" / "validate_skill.py",
                str(installed),
                cwd=workdir,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS: frontmatter and reference routing are valid", result.stdout)

    def test_questionnaire_and_decision_helpers_start_from_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            scripts = installed / "scripts"

            demo = run_script(scripts / "questionnaire_server.py", "--print-demo", cwd=workdir)
            self.assertEqual(demo.returncode, 0, demo.stdout + demo.stderr)
            questionnaire = workdir / "questions.json"
            questionnaire.write_text(demo.stdout, encoding="utf-8")

            validated = run_script(
                scripts / "questionnaire_server.py",
                "--input",
                str(questionnaire),
                "--validate-only",
                cwd=workdir,
            )
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            self.assertIn("PASS: questionnaire is valid", validated.stdout)

            for helper in ("decision_state.py", "check_update.py"):
                result = run_script(scripts / helper, "--help", cwd=workdir)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_smoke_runs_from_installed_package_with_explicit_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("FAIL:", result.stdout)
            self.assertIn("SKIP (optional, not applicable here)", result.stdout)
            self.assertIn("explicitly skipped", result.stdout)

    def test_packaged_helpers_avoid_repository_root_paths(self) -> None:
        for name in (
            "check_update.py",
            "decision_state.py",
            "project_probe.py",
            "questionnaire_server.py",
            "validate_skill.py",
        ):
            text = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn("parents[2]", text, f"{name} reaches outside the skill package")

    def test_smoke_fails_when_cursor_route_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            strip_phrase(installed, CURSOR_ROUTE_TOKEN)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("Cursor target", result.stdout)

    def test_smoke_fails_when_owner_contract_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            strip_phrase(installed, REQUIRED_OWNER_PHRASE)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn(
                "documentation-rules template lost contract phrases", result.stdout
            )

    def test_smoke_fails_when_root_adapter_link_to_contract_is_broken(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            break_root_adapter_link(installed)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("no real Markdown link to docs/documentation-rules.md", result.stdout)

    def test_smoke_fails_when_adapter_pins_two_maintenance_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            add_second_maintenance_mode(installed)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("exactly one maintenance mode", result.stdout)

    def test_smoke_fails_when_cursor_link_is_not_project_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            make_cursor_link_nonrelative(installed)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("project-relative Markdown link", result.stdout)

    def test_smoke_fails_when_main_map_ships_code_rules_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            ship_code_rules_row_in_main_map(installed)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("must not ship a row for code_rules.md", result.stdout)

    def test_smoke_fails_when_local_sufficiency_rule_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            strip_phrase(installed, LOCAL_SUFFICIENCY_PHRASE)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("lost contract phrases", result.stdout)

    def test_smoke_fails_when_cursor_always_apply_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            strip_always_apply(installed)

            result = run_script(installed / "scripts" / "smoke_test.py", cwd=workdir)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("alwaysApply", result.stdout)

    def test_validate_skill_fails_when_a_routed_template_is_unlinked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            router = find_router_doc(installed)
            text = router.read_text(encoding="utf-8")
            updated = re.sub(
                r"\]\(templates/root-instructions\.md\)",
                "](templates/missing-root.md)",
                text,
            )
            self.assertNotEqual(text, updated, "router did not link the root template")
            router.write_text(updated, encoding="utf-8")

            result = run_script(
                installed / "scripts" / "validate_skill.py",
                str(installed),
                cwd=workdir,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("missing", result.stdout)

    def test_validate_skill_fails_when_a_routed_script_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            (installed / "scripts" / "documentation_index.py").unlink()

            result = run_script(
                installed / "scripts" / "validate_skill.py",
                str(installed),
                cwd=workdir,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL:", result.stdout)
            self.assertIn("routes to a missing resource", result.stdout)


class InstalledHelperIntegrationTests(unittest.TestCase):
    """0.4 helpers must work from the installed package with no side effects.

    These checks exercise the packaged copies from a different working
    directory: the new probe helper and the decision-state legacy/current
    contract. They are unconditional on purpose - a missing helper or fixture
    is a real failure, never a skip.
    """

    def test_project_probe_imports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            before = tree_snapshot(installed)
            program = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import project_probe; print('OK')"
            )
            result = subprocess.run(
                [sys.executable, "-B", "-c", program, str(installed / "scripts")],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK", result.stdout)
            self.assertEqual(
                tree_snapshot(installed),
                before,
                "importing project_probe wrote into the installed package",
            )
            self.assertFalse((workdir / ".git").exists(), "probe import initialised git")

    def test_project_probe_reports_selected_root_from_another_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            project = workdir / "selected-project"
            project.mkdir()
            before = tree_snapshot(installed)

            result = run_script(
                installed / "scripts" / "project_probe.py",
                "--root",
                str(project),
                "--json",
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["classification"], "empty")
            self.assertIs(payload["scan_complete"], True)
            self.assertEqual(
                os.path.realpath(payload["selected_scope"]["root"]),
                os.path.realpath(str(project)),
                "probe reported a root other than the selected one",
            )
            self.assertIs(payload["selected_scope"]["is_git_repo"], False)
            self.assertIsNone(payload["selected_scope"]["git_entry"])
            self.assertEqual(payload["counts"]["files"], 0)
            self.assertEqual(payload["diagnostics"], [])
            self.assertFalse((project / ".git").exists(), "probe initialised a git repository")
            self.assertFalse((workdir / ".git").exists(), "probe initialised git in the cwd")
            self.assertEqual(
                tree_snapshot(installed),
                before,
                "running the probe CLI wrote into the installed package",
            )

    def test_project_probe_unknown_root_is_not_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            missing = workdir / "not-a-project"

            result = run_script(
                installed / "scripts" / "project_probe.py",
                "--root",
                str(missing),
                "--json",
                cwd=workdir,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "unknown")
            self.assertIs(payload["scan_complete"], False)
            self.assertFalse(missing.exists(), "probe created a missing root")

    def test_decision_state_handles_legacy_and_current_input_from_another_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            installed = copy_package(workdir)
            state_script = installed / "scripts" / "decision_state.py"
            legacy = installed / "tests" / "fixtures" / "decision-state" / "legacy_v1.json"
            self.assertTrue(legacy.is_file(), "legacy decision-state fixture is missing")
            legacy_bytes = legacy.read_bytes()
            before = tree_snapshot(installed)

            validated = run_script(
                state_script, "--input", str(legacy), "--validate-only", cwd=workdir
            )
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            self.assertIn("PASS: decision state is valid", validated.stdout)

            revision = run_script(
                state_script, "--input", str(legacy), "--idea-revision", cwd=workdir
            )
            self.assertEqual(revision.returncode, 0, revision.stdout + revision.stderr)
            self.assertRegex(revision.stdout.strip(), r"^[0-9a-f]{16}$")

            legacy_state = json.loads(legacy.read_text(encoding="utf-8"))
            decision_id = legacy_state["decisions"][0]["id"]
            revised = run_script(
                state_script,
                "--input",
                str(legacy),
                "--revise-decision",
                decision_id,
                "--answer",
                "Probe",
                cwd=workdir,
            )
            self.assertEqual(revised.returncode, 0, revised.stdout + revised.stderr)
            current_path = workdir / "current_v2.json"
            current_path.write_text(revised.stdout, encoding="utf-8")
            revalidated = run_script(
                state_script, "--input", str(current_path), "--validate-only", cwd=workdir
            )
            self.assertEqual(
                revalidated.returncode, 0, revalidated.stdout + revalidated.stderr
            )

            self.assertEqual(
                legacy.read_bytes(),
                legacy_bytes,
                "--revise-decision rewrote the input file instead of printing v2",
            )
            self.assertEqual(
                tree_snapshot(installed),
                before,
                "running the decision-state CLI wrote into the installed package",
            )


def write_minimal_skill(root: Path, frontmatter: str) -> Path:
    skill = root / "demo-skill"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n# Demo\n", encoding="utf-8"
    )
    (skill / "VERSION").write_text("0.3.0\n", encoding="utf-8")
    return skill


class FrontmatterSubsetTests(unittest.TestCase):
    """The stdlib parser supports a flat scalar subset and must reject the rest.

    These checks build throwaway skills so the real package frontmatter stays
    untouched, and they fail loudly instead of accepting an unsupported YAML
    shape as literal text.
    """

    def problems_for(self, frontmatter: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_name:
            skill = write_minimal_skill(Path(temp_name), frontmatter)
            return validate_skill.check_frontmatter(skill)

    def test_flat_scalar_frontmatter_is_accepted(self) -> None:
        problems = self.problems_for(
            "name: demo-skill\ndescription: A flat scalar description."
        )
        self.assertEqual(problems, [])

    def test_real_package_frontmatter_still_validates(self) -> None:
        report = validate_skill.validate_package(PACKAGE_DIR)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["skill_dir"], str(PACKAGE_DIR.resolve()))

    def test_block_scalar_description_is_rejected(self) -> None:
        problems = self.problems_for(
            "name: demo-skill\ndescription: |\n  first line\n  second line"
        )
        self.assertTrue(
            any("unsupported YAML" in problem for problem in problems), problems
        )

    def test_folded_scalar_description_is_rejected(self) -> None:
        problems = self.problems_for("name: demo-skill\ndescription: >\n  folded text")
        self.assertTrue(
            any("unsupported YAML" in problem for problem in problems), problems
        )

    def test_empty_block_description_is_rejected(self) -> None:
        problems = self.problems_for("name: demo-skill\ndescription: |")
        self.assertTrue(
            any("unsupported YAML" in problem for problem in problems), problems
        )

    def test_empty_description_value_is_rejected(self) -> None:
        problems = self.problems_for("name: demo-skill\ndescription:")
        self.assertTrue(
            any("non-empty 'description'" in problem for problem in problems), problems
        )

    def test_non_string_name_is_rejected(self) -> None:
        problems = self.problems_for("name: 123\ndescription: A description.")
        self.assertTrue(
            any("must be a string scalar" in problem for problem in problems), problems
        )

    def test_flow_sequence_value_is_rejected(self) -> None:
        problems = self.problems_for("name: [demo-skill]\ndescription: A description.")
        self.assertTrue(
            any("unsupported YAML" in problem for problem in problems), problems
        )

    def test_nested_mapping_is_rejected(self) -> None:
        problems = self.problems_for(
            "name: demo-skill\ndescription: A description.\nmetadata:\n  short: value"
        )
        self.assertTrue(
            any("nested or indented" in problem for problem in problems), problems
        )

    def test_malformed_line_is_rejected(self) -> None:
        problems = self.problems_for("name demo-skill\ndescription: A description.")
        self.assertTrue(
            any("malformed frontmatter line" in problem for problem in problems), problems
        )

    def test_duplicate_key_is_rejected(self) -> None:
        problems = self.problems_for(
            "name: demo-skill\nname: demo-skill\ndescription: A description."
        )
        self.assertTrue(
            any("duplicate frontmatter key" in problem for problem in problems), problems
        )

    def test_unclosed_frontmatter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            skill = Path(temp_name) / "demo-skill"
            skill.mkdir(parents=True, exist_ok=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: A description.\n", encoding="utf-8"
            )
            (skill / "VERSION").write_text("0.3.0\n", encoding="utf-8")
            problems = validate_skill.check_frontmatter(skill)
        self.assertTrue(any("not closed" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
