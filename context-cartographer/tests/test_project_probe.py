#!/usr/bin/env python3
"""Tests for the bounded folder-state probe (implementation plan 04-02 / 8.2).

Two fixture styles:

* committed folders under ``tests/fixtures/probe/`` for the stable classes
  (scaffold, brief, ready spec, existing app, component, hidden config,
  Git-ignored code, Unicode paths, mockups, unclassifiable);
* temporary folders for cases that can not be committed as-is (a folder that
  holds only ``.git``, an empty subfolder inside a monorepo, symlinks, entry and
  depth limits, an unreadable directory, a bounded document read, size caps).

The suite is standard library only, never touches the network and never lets
the probe or the interpreter write bytecode while a "no filesystem change"
test is running.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
REPO = HERE.parents[1]
SCRIPT = REPO / "scripts" / "project_probe.py"
FIXTURES = REPO / "tests" / "fixtures" / "probe"


def load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "context_cartographer_project_probe_tests", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load_probe_module()

EXPECTED_KEYS = {
    "schema_version",
    "classification",
    "basis",
    "selected_scope",
    "scan_complete",
    "diagnostics",
    "counts",
    "limits",
}
EXPECTED_SCOPE_KEYS = {
    "root",
    "resolved_root",
    "exists",
    "is_dir",
    "readable",
    "is_git_repo",
    "git_entry",
    "enclosing_git_root",
    "ancestor_instruction_files",
}
EXPECTED_COUNT_KEYS = {"entries", "files", "dirs", "symlinks"}
EXPECTED_LIMIT_KEYS = {"max_entries", "max_depth", "max_identity_bytes"}

SECRET_SENTINEL = "PROBE_SECRET_SENTINEL_9f3a2b"
README_SENTENCE = "printable index of the daily readings"

FORBIDDEN_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+"
    r"(socket|urllib|http|requests|subprocess|socketserver|ftplib|telnetlib|"
    r"smtplib|ssl|asyncio)\b",
    re.MULTILINE,
)


class _CountingScandir:
    """Wrap ``os.scandir`` to count how many entries a scan really consumes."""

    def __init__(self, inner, counter):
        self._inner = inner
        self._counter = counter

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)

    def __iter__(self):
        for item in self._inner:
            self._counter["yielded"] += 1
            yield item

    def close(self):
        self._inner.close()


class _FakeScandir:
    """Minimal stand-in for the ``os.scandir`` context manager."""

    def __init__(self, entries):
        self._entries = list(entries)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._entries)

    def close(self):
        self._entries = []


class _FakeEntry:
    """A directory entry whose type lookup always fails."""

    def __init__(self, name, path):
        self.name = name
        self.path = path

    def is_symlink(self):
        return False

    def is_dir(self, follow_symlinks=True):
        raise OSError(5, "Input/output error")


def probe(path, **kwargs):
    return PROBE.probe_project(str(path), **kwargs)


def run_cli(root, *extra, cwd=None):
    """Run the CLI from ``cwd`` in a subprocess that writes no bytecode."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--root", str(root), "--json", *extra],
        cwd=str(cwd or tempfile.gettempdir()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def tree_snapshot(root):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            info = os.lstat(path)
            items.append(
                (
                    os.path.relpath(path, root),
                    info.st_mode,
                    info.st_size,
                    info.st_mtime_ns,
                )
            )
    return items


def codes(result):
    return [item["code"] for item in result["diagnostics"]]


def basis_kinds(result):
    return {item["kind"] for item in result["basis"]}


def basis_paths(result):
    return {item["path"] for item in result["basis"]}


class SchemaTests(unittest.TestCase):
    def test_result_shape_is_stable(self):
        result = probe(FIXTURES / "existing_app")
        self.assertEqual(set(result), EXPECTED_KEYS)
        self.assertEqual(set(result["selected_scope"]), EXPECTED_SCOPE_KEYS)
        self.assertEqual(set(result["counts"]), EXPECTED_COUNT_KEYS)
        self.assertEqual(set(result["limits"]), EXPECTED_LIMIT_KEYS)
        self.assertEqual(result["schema_version"], 1)
        self.assertIn(result["classification"], PROBE.CLASSIFICATIONS)
        self.assertIsInstance(result["basis"], list)
        self.assertIsInstance(result["scan_complete"], bool)
        self.assertIsInstance(result["diagnostics"], list)
        for item in result["basis"]:
            self.assertEqual(set(item), {"path", "kind", "reason"})

    def test_json_serializable(self):
        result = probe(FIXTURES / "existing_monorepo")
        self.assertEqual(json.loads(json.dumps(result))["classification"], "existing")

    def test_rejects_nonsense_limits(self):
        for bad in ({"max_entries": 0}, {"max_depth": 0}, {"max_identity_bytes": 0}):
            with self.assertRaises(ValueError):
                probe(FIXTURES / "scaffold", **bad)

    def test_rejects_bool_and_non_int_limits(self):
        for bad in (
            {"max_entries": True},
            {"max_entries": "5"},
            {"max_depth": 2.5},
            {"max_identity_bytes": None},
        ):
            with self.assertRaises(TypeError):
                probe(FIXTURES / "scaffold", **bad)


class EmptyFolderTests(unittest.TestCase):
    def test_truly_empty_folder_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = probe(tmp)
            self.assertEqual(result["classification"], "empty")
            self.assertTrue(result["scan_complete"])
            self.assertEqual(result["basis"], [])
            self.assertEqual(result["diagnostics"], [])
            self.assertEqual(result["counts"]["entries"], 0)
            self.assertEqual(result["selected_scope"]["root"], os.path.abspath(tmp))

    def test_only_git_metadata_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            git_dir = Path(tmp) / ".git"
            (git_dir / "objects").mkdir(parents=True)
            (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            result = probe(tmp)
            self.assertEqual(result["classification"], "empty")
            self.assertTrue(result["scan_complete"])
            self.assertTrue(result["selected_scope"]["is_git_repo"])
            self.assertEqual(result["selected_scope"]["git_entry"], ".git")
            # The metadata directory itself is seen, its internals are not walked.
            self.assertEqual(result["counts"]["dirs"], 1)
            self.assertEqual(result["counts"]["files"], 0)

    def test_only_os_metadata_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".DS_Store").write_bytes(b"\x00\x01")
            result = probe(tmp)
            self.assertEqual(result["classification"], "empty")
            self.assertTrue(result["scan_complete"])
            self.assertEqual(result["diagnostics"], [])

    def test_regenerable_cache_directory_is_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "__pycache__"
            cache.mkdir()
            (cache / "module.cpython-314.pyc").write_bytes(b"\x00")
            result = probe(tmp)
            self.assertEqual(result["classification"], "empty")
            self.assertTrue(result["scan_complete"])
            # The cache directory is named, its contents are not counted.
            self.assertEqual(result["counts"]["dirs"], 1)
            self.assertEqual(result["counts"]["files"], 0)

    def test_git_pointer_file_and_git_directory_are_both_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            as_file = Path(tmp) / "worktree"
            as_file.mkdir()
            pointer = "gitdir: /tmp/elsewhere/.git/worktrees/wt\n"
            (as_file / ".git").write_text(pointer, encoding="utf-8")

            as_dir = Path(tmp) / "checkout"
            (as_dir / ".git" / "objects").mkdir(parents=True)
            (as_dir / ".git" / "HEAD").write_text(
                "ref: refs/heads/main\n", encoding="utf-8"
            )

            file_result = probe(as_file)
            dir_result = probe(as_dir)

            for result in (file_result, dir_result):
                self.assertEqual(result["classification"], "empty")
                self.assertTrue(result["scan_complete"])
                self.assertEqual(result["diagnostics"], [])
                self.assertTrue(result["selected_scope"]["is_git_repo"])
                self.assertEqual(result["selected_scope"]["git_entry"], ".git")
                self.assertEqual(basis_kinds(result), {"metadata"})

            # A `.git` file is metadata, not an unrecognized file, and the
            # `gitdir:` pointer target is never read or echoed.
            self.assertNotIn(
                "worktrees/wt", json.dumps(file_result, ensure_ascii=False)
            )
            self.assertEqual(
                file_result["counts"],
                {"entries": 1, "files": 1, "dirs": 0, "symlinks": 0},
            )
            self.assertEqual(
                dir_result["counts"],
                {"entries": 1, "files": 0, "dirs": 1, "symlinks": 0},
            )

    def test_missing_root_is_unknown_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = probe(Path(tmp) / "absent")
            self.assertEqual(result["classification"], "unknown")
            self.assertFalse(result["scan_complete"])
            self.assertEqual(codes(result), ["root_missing"])
            self.assertEqual(result["selected_scope"]["exists"], False)

    def test_root_that_is_a_file_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file.txt"
            target.write_text("not a folder\n", encoding="utf-8")
            result = probe(target)
            self.assertEqual(result["classification"], "unknown")
            self.assertIn("root_not_directory", codes(result))
            self.assertFalse(result["scan_complete"])

    def test_unclassifiable_content_is_unknown_not_empty(self):
        result = probe(FIXTURES / "unclassifiable")
        self.assertEqual(result["classification"], "unknown")
        self.assertTrue(result["scan_complete"])
        self.assertIn("no_decision_evidence", codes(result))

    def test_stub_readme_is_unknown_not_brief(self):
        result = probe(FIXTURES / "stub_readme")
        self.assertEqual(result["classification"], "unknown")
        self.assertIn("no_decision_evidence", codes(result))


class ScaffoldTests(unittest.TestCase):
    def test_license_and_gitignore_are_a_scaffold(self):
        result = probe(FIXTURES / "scaffold")
        self.assertEqual(result["classification"], "scaffold")
        self.assertTrue(result["scan_complete"])
        self.assertEqual(basis_kinds(result), {"scaffold"})
        self.assertIn("LICENSE", basis_paths(result))

    def test_empty_directories_are_structure_not_a_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            result = probe(tmp)
            self.assertEqual(result["classification"], "scaffold")
            self.assertEqual(result["counts"]["dirs"], 1)


class BriefOnlyTests(unittest.TestCase):
    def test_substantive_readme_is_brief_only(self):
        result = probe(FIXTURES / "brief_readme")
        self.assertEqual(result["classification"], "brief_only")
        self.assertTrue(result["scan_complete"])
        self.assertEqual(basis_kinds(result), {"document"})

    def test_idea_with_requirements_and_mockup_is_brief_only(self):
        result = probe(FIXTURES / "brief_idea")
        self.assertEqual(result["classification"], "brief_only")
        self.assertIn("document", basis_kinds(result))
        self.assertIn("mockup", basis_kinds(result))

    def test_ready_spec_without_code_is_brief_only(self):
        result = probe(FIXTURES / "ready_spec")
        self.assertEqual(result["classification"], "brief_only")
        self.assertIn("AGENTS.md", basis_paths(result))
        self.assertIn("requirements.md", basis_paths(result))

    def test_mockups_alone_are_brief_only(self):
        result = probe(FIXTURES / "mockup_only")
        self.assertEqual(result["classification"], "brief_only")
        self.assertEqual(basis_kinds(result), {"dir", "mockup"})


class ExistingTests(unittest.TestCase):
    def test_code_and_config_are_existing(self):
        result = probe(FIXTURES / "existing_app")
        self.assertEqual(result["classification"], "existing")
        self.assertTrue(result["scan_complete"])
        self.assertIn("code", basis_kinds(result))
        self.assertIn("config", basis_kinds(result))

    def test_monorepo_root_is_existing(self):
        result = probe(FIXTURES / "existing_monorepo")
        self.assertEqual(result["classification"], "existing")

    def test_nested_component_is_existing(self):
        target = FIXTURES / "existing_monorepo" / "packages" / "widget"
        result = probe(target)
        self.assertEqual(result["classification"], "existing")
        self.assertEqual(result["selected_scope"]["root"], str(target))
        self.assertIn("code", basis_kinds(result))
        self.assertIn("config", basis_kinds(result))
        self.assertTrue(all(not p.startswith("packages/") for p in basis_paths(result)))

    def test_hidden_container_config_is_existing(self):
        result = probe(FIXTURES / "hidden_config")
        self.assertEqual(result["classification"], "existing")
        self.assertIn("config", basis_kinds(result))
        self.assertIn("data", basis_kinds(result))
        self.assertIn("secret", basis_kinds(result))
        self.assertIn("scripts/deploy.sh", basis_paths(result))

    def test_hidden_and_gitignored_code_still_counts(self):
        result = probe(FIXTURES / "ignored_code")
        self.assertEqual(result["classification"], "existing")
        self.assertIn("build/generated.py", basis_paths(result))
        self.assertIn(".hidden_notes.md", basis_paths(result))


class StaticSiteTests(unittest.TestCase):
    def test_static_site_is_existing(self):
        result = probe(FIXTURES / "static_site")
        self.assertEqual(result["classification"], "existing")
        self.assertTrue(result["scan_complete"])
        self.assertIn("code", basis_kinds(result))
        self.assertIn("index.html", basis_paths(result))
        self.assertIn("styles/site.css", basis_paths(result))
        self.assertIn("templates/index.jinja", basis_paths(result))

    def test_static_and_template_suffixes_are_code(self):
        # The deliberate minimum for a static site: markup, stylesheets and the
        # common template languages. The list is not meant to grow without a
        # concrete case.
        for suffix in (
            ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
            ".styl", ".jinja", ".jinja2", ".j2", ".twig", ".liquid", ".njk",
            ".hbs", ".handlebars", ".ejs", ".mustache", ".erb",
        ):
            self.assertIn(suffix, PROBE.CODE_SUFFIXES, suffix)
            self.assertEqual(
                PROBE._classify_file("page" + suffix, [])[0], "code", suffix
            )

    def test_single_stylesheet_folder_is_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "styles.css").write_text(
                "body { margin: 0; }\n", encoding="utf-8"
            )
            result = probe(root)
            self.assertEqual(result["classification"], "existing")
            self.assertIn("styles.css", basis_paths(result))


class RequirementsPolicyTests(unittest.TestCase):
    """The ambiguous ``requirements`` name has one documented policy:
    ``requirements*.txt``/``*.in`` are dependency manifests (configuration),
    ``requirements.md``/``requirements.rst`` are written requirements."""

    def test_requirements_txt_is_a_manifest_not_a_brief(self):
        result = probe(FIXTURES / "requirements_manifest")
        self.assertEqual(result["classification"], "existing")
        self.assertEqual(basis_kinds(result), {"config"})
        self.assertIn("requirements.txt", basis_paths(result))

    def test_requirements_md_is_a_written_brief(self):
        result = probe(FIXTURES / "requirements_brief")
        self.assertEqual(result["classification"], "brief_only")
        self.assertEqual(basis_kinds(result), {"document"})

    def test_requirements_name_table_is_predictable(self):
        for name in (
            "requirements.txt", "requirements-dev.txt", "requirements-prod.txt",
            "requirements.in", "requirements-v2.txt", "requirements.test.txt",
        ):
            self.assertTrue(PROBE._is_config_name(name), name)
            self.assertEqual(PROBE._classify_file(name, [])[0], "config", name)
        for name in ("requirements.md", "requirements.rst"):
            self.assertFalse(PROBE._is_config_name(name), name)
            self.assertEqual(PROBE._classify_file(name, [])[0], "document", name)


class ScopeTests(unittest.TestCase):
    def test_empty_subfolder_in_monorepo_stays_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "monorepo"
            shutil.copytree(FIXTURES / "existing_monorepo", repo)
            (repo / ".git").mkdir()
            (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            target = repo / "packages" / "empty-target"
            target.mkdir()

            result = probe(target)
            self.assertEqual(result["selected_scope"]["root"], str(target))
            self.assertEqual(result["classification"], "empty")
            self.assertTrue(result["scan_complete"])
            # The parent repository is context, never the target.
            self.assertEqual(
                os.path.realpath(result["selected_scope"]["enclosing_git_root"]),
                os.path.realpath(str(repo)),
            )
            self.assertFalse(result["selected_scope"]["is_git_repo"])
            self.assertEqual(basis_paths(result), set())

    def test_probe_does_not_create_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "plain"
            target.mkdir()
            (target / "README.md").write_text(
                "# Notes\n\nA short but substantive note describing the intended "
                "product and its first useful version for its readers today.\n",
                encoding="utf-8",
            )
            result = probe(target)
            self.assertEqual(result["classification"], "brief_only")
            self.assertFalse((target / ".git").exists())
            self.assertFalse(result["selected_scope"]["is_git_repo"])

    def test_instruction_files_are_reported(self):
        result = probe(FIXTURES / "ready_spec")
        listed = result["selected_scope"]["ancestor_instruction_files"]
        self.assertIn(str(FIXTURES / "ready_spec" / "AGENTS.md"), listed)

    def test_counts_reflect_the_selected_root_only(self):
        target = FIXTURES / "existing_monorepo" / "packages" / "widget"
        result = probe(target)
        self.assertEqual(result["counts"]["files"], 2)
        self.assertEqual(result["counts"]["dirs"], 1)


class SecretSafetyTests(unittest.TestCase):
    def test_secret_file_is_listed_but_never_read(self):
        result = probe(FIXTURES / "hidden_config")
        rendered = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(SECRET_SENTINEL, rendered)
        self.assertIn(".env", basis_paths(result))
        secret_items = [item for item in result["basis"] if item["kind"] == "secret"]
        self.assertEqual(len(secret_items), 1)
        self.assertIn("never read", secret_items[0]["reason"])

    def test_secret_sentinel_is_absent_from_cli_output(self):
        proc = run_cli(FIXTURES / "hidden_config")
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn(SECRET_SENTINEL, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["classification"], "existing")

    def test_document_body_is_never_echoed(self):
        proc = run_cli(FIXTURES / "brief_readme")
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn(README_SENTENCE, proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["classification"], "brief_only")
        for item in result["basis"]:
            self.assertNotIn("\n", item["reason"])

    def test_secret_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "real.env").write_text(
                "TOKEN={}\n".format(SECRET_SENTINEL), encoding="utf-8"
            )
            root = Path(tmp) / "root"
            root.mkdir()
            os.symlink(str(outside / "real.env"), str(root / ".env"))
            result = probe(root)
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(SECRET_SENTINEL, rendered)
            self.assertEqual(result["classification"], "unknown")
            self.assertIn("symlink_not_followed", codes(result))


class SymlinkTests(unittest.TestCase):
    def test_symlink_to_folder_outside_root_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "app.py").write_text("print('code')\n", encoding="utf-8")
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "README.md").write_text(
                "# Plan\n\nA short description of the intended product that is long "
                "enough to read as a real written idea for its first version.\n",
                encoding="utf-8",
            )
            os.symlink(str(outside), str(root / "linked"))

            result = probe(root)
            self.assertEqual(result["classification"], "brief_only")
            self.assertNotIn("code", basis_kinds(result))
            self.assertIn("symlink_not_followed", codes(result))
            self.assertEqual(result["counts"]["symlinks"], 1)

    def test_dangling_symlink_is_reported_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            os.symlink(str(root / "gone"), str(root / "dangling"))
            result = probe(root)
            self.assertEqual(result["classification"], "unknown")
            self.assertIn("symlink_not_followed", codes(result))
            self.assertIn("no_decision_evidence", codes(result))

    def test_symlink_inside_root_is_also_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            (root / "real").mkdir(parents=True)
            (root / "real" / "app.py").write_text("print('code')\n", encoding="utf-8")
            os.symlink(str(root / "real"), str(root / "alias"))
            result = probe(root)
            self.assertIn("symlink_not_followed", codes(result))
            # The real folder is still walked, so the product is found once.
            self.assertEqual(result["classification"], "existing")
            self.assertEqual(result["counts"]["symlinks"], 1)


class InaccessibleTests(unittest.TestCase):
    def test_unreadable_directory_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            blocked = root / "blocked"
            blocked.mkdir()

            real_scandir = os.scandir

            def fake_scandir(path=".", *args, **kwargs):
                if os.path.realpath(os.fspath(path)) == os.path.realpath(str(blocked)):
                    raise PermissionError(13, "Permission denied")
                return real_scandir(path, *args, **kwargs)

            with mock.patch("os.scandir", side_effect=fake_scandir):
                result = probe(root)

            self.assertEqual(result["classification"], "unknown")
            self.assertFalse(result["scan_complete"])
            self.assertIn("directory_unreadable", codes(result))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores permissions")
    def test_real_unreadable_directory_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            blocked = root / "blocked"
            blocked.mkdir()
            (blocked / "app.py").write_text("print('code')\n", encoding="utf-8")
            os.chmod(blocked, 0o000)
            try:
                if os.access(blocked, os.R_OK):
                    self.skipTest("permissions are not enforced in this environment")
                result = probe(root)
            finally:
                os.chmod(blocked, 0o700)

            self.assertEqual(result["classification"], "unknown")
            self.assertFalse(result["scan_complete"])
            self.assertIn("directory_unreadable", codes(result))

    def test_missing_root_is_unknown_via_cli_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(Path(tmp) / "absent")
            self.assertEqual(proc.returncode, 0)
            result = json.loads(proc.stdout)
            self.assertEqual(result["classification"], "unknown")
            self.assertFalse(result["scan_complete"])


class LimitTests(unittest.TestCase):
    def test_entry_limit_marks_the_scan_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            for index in range(20):
                (root / "file_{:02d}.py".format(index)).write_text(
                    "print({})\n".format(index), encoding="utf-8"
                )
            result = probe(root, max_entries=5)
            self.assertIn("entry_limit_reached", codes(result))
            self.assertFalse(result["scan_complete"])
            self.assertEqual(result["counts"]["entries"], 5)
            self.assertLessEqual(len(result["basis"]), 48)

    def test_entry_limit_never_reports_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            for index in range(10):
                (root / "note_{:02d}.xyz".format(index)).write_text("x\n", encoding="utf-8")
            result = probe(root, max_entries=3)
            self.assertEqual(result["classification"], "unknown")
            self.assertIn("entry_limit_reached", codes(result))

    def test_depth_limit_marks_the_scan_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            deep = root / "one" / "two" / "three"
            deep.mkdir(parents=True)
            (deep / "app.py").write_text("print('deep')\n", encoding="utf-8")
            result = probe(root, max_depth=2)
            self.assertIn("depth_limit_reached", codes(result))
            self.assertFalse(result["scan_complete"])
            self.assertEqual(result["classification"], "unknown")

    def test_content_limit_marks_the_scan_incomplete_and_classification_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            body = "# Very long idea\n\n" + ("A meaningful sentence about the plan. " * 200)
            (root / "README.md").write_text(body, encoding="utf-8")
            result = probe(root, max_identity_bytes=120)
            self.assertEqual(result["classification"], "unknown")
            self.assertFalse(result["scan_complete"])
            self.assertIn("content_limit_reached", codes(result))

    def test_generous_limits_keep_a_normal_tree_complete(self):
        result = probe(FIXTURES / "existing_monorepo")
        self.assertTrue(result["scan_complete"])
        self.assertEqual(result["limits"]["max_entries"], PROBE.DEFAULT_MAX_ENTRIES)


class DeterminismTests(unittest.TestCase):
    def test_identical_inputs_give_identical_output(self):
        first = probe(FIXTURES / "existing_monorepo")
        second = probe(FIXTURES / "existing_monorepo")
        self.assertEqual(
            json.dumps(first, ensure_ascii=False), json.dumps(second, ensure_ascii=False)
        )

    def test_cli_and_function_agree(self):
        proc = run_cli(FIXTURES / "brief_idea")
        self.assertEqual(json.loads(proc.stdout), probe(FIXTURES / "brief_idea"))

    def test_unicode_and_space_paths_survive_the_round_trip(self):
        result = probe(FIXTURES / "unicode")
        self.assertEqual(result["classification"], "brief_only")
        paths = basis_paths(result)
        self.assertIn("docs/\u0434\u043e\u043a \u0441 \u043f\u0440\u043e\u0431\u0435\u043b\u043e\u043c.md", paths)
        proc = run_cli(FIXTURES / "unicode")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["classification"], "brief_only")


class NoMutationTests(unittest.TestCase):
    def test_probe_does_not_change_the_tree(self):
        target = FIXTURES / "hidden_config"
        before = tree_snapshot(target)
        result = probe(target)
        after = tree_snapshot(target)
        self.assertEqual(result["classification"], "existing")
        self.assertEqual(before, after)
        self.assertFalse((target / ".git").exists())

    def test_cli_from_another_cwd_writes_nothing(self):
        target = FIXTURES / "existing_app"
        with tempfile.TemporaryDirectory() as cwd:
            before = tree_snapshot(target)
            scripts_before = sorted(
                str(path.relative_to(REPO)) for path in (REPO / "scripts").rglob("*")
            )
            proc = run_cli(target, cwd=cwd)
            after = tree_snapshot(target)
            scripts_after = sorted(
                str(path.relative_to(REPO)) for path in (REPO / "scripts").rglob("*")
            )

        self.assertEqual(proc.returncode, 0)
        result = json.loads(proc.stdout)
        self.assertEqual(result["selected_scope"]["root"], str(target))
        self.assertEqual(result["classification"], "existing")
        self.assertEqual(before, after)
        self.assertEqual(scripts_before, scripts_after)
        self.assertFalse((Path(cwd) / ".git").exists())

    def test_running_the_probe_writes_no_bytecode(self):
        pycache = REPO / "scripts" / "__pycache__"

        def listing():
            if not pycache.is_dir():
                return []
            return sorted(path.name for path in pycache.glob("project_probe*"))

        before = listing()
        result = probe(FIXTURES / "scaffold")
        proc = run_cli(FIXTURES / "scaffold")
        self.assertEqual(result["classification"], "scaffold")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(listing(), before)
class NoNetworkTests(unittest.TestCase):
    def test_no_network_or_subprocess_imports(self):
        source = SCRIPT.read_text(encoding="utf-8")
        matches = FORBIDDEN_IMPORT_RE.findall(source)
        self.assertEqual(matches, [], "network or subprocess import found")

    def test_probe_works_with_sockets_disabled(self):
        def explode(*_args, **_kwargs):
            raise AssertionError("probe opened a socket")

        with mock.patch.object(socket, "socket", explode), mock.patch.object(
            socket, "create_connection", explode
        ):
            result = probe(FIXTURES / "existing_app")
        self.assertEqual(result["classification"], "existing")


class CliTests(unittest.TestCase):
    def test_cli_prints_json_from_an_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as cwd:
            proc = run_cli(FIXTURES / "scaffold", cwd=cwd)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["classification"], "scaffold")
        self.assertTrue(payload["scan_complete"])

    def test_cli_without_root_is_a_usage_error(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_cli_reports_unknown_root_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(Path(tmp) / "gone")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["classification"], "unknown")

    def test_cli_relative_root_follows_the_invocation_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "brief"
            target.mkdir()
            (target / "README.md").write_text(
                "# Idea\n\nA description of the planned tool that is detailed enough "
                "to be read as a real intention rather than an empty placeholder.\n",
                encoding="utf-8",
            )
            proc = run_cli("brief", cwd=tmp)
        self.assertEqual(proc.returncode, 0)
        result = json.loads(proc.stdout)
        self.assertEqual(result["classification"], "brief_only")
        # The subprocess resolves its own cwd, so compare canonical paths.
        self.assertEqual(
            os.path.realpath(result["selected_scope"]["root"]),
            os.path.realpath(str(target)),
        )

    def test_cli_rejects_a_non_positive_limit(self):
        proc = subprocess.run(
            [
                sys.executable, "-B", str(SCRIPT),
                "--root", str(FIXTURES / "scaffold"),
                "--max-entries", "0",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("--max-entries", proc.stderr)


class BoundedScanTests(unittest.TestCase):
    def test_directory_listing_is_capped_by_the_entry_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            for index in range(50):
                (root / "f{:02d}.py".format(index)).write_text(
                    "print({})\n".format(index), encoding="utf-8"
                )
            counter = {"yielded": 0}
            real_scandir = os.scandir

            def counting_scandir(path=".", *args, **kwargs):
                return _CountingScandir(
                    real_scandir(path, *args, **kwargs), counter
                )

            with mock.patch("os.scandir", side_effect=counting_scandir):
                result = probe(root, max_entries=5)

            self.assertIn("entry_limit_reached", codes(result))
            self.assertFalse(result["scan_complete"])
            self.assertEqual(result["counts"]["entries"], 5)
            # Five entries plus the single probe that detects the overflow.
            self.assertLessEqual(counter["yielded"], 6)
            self.assertLess(counter["yielded"], 50)


class ErrorReportingTests(unittest.TestCase):
    def test_entry_type_error_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            bad = root / "bad"
            bad.mkdir()
            real_scandir = os.scandir

            def wrapper(path=".", *args, **kwargs):
                if os.path.realpath(os.fspath(path)) == os.path.realpath(str(bad)):
                    return _FakeScandir([_FakeEntry("child", str(bad / "child"))])
                return real_scandir(path, *args, **kwargs)

            with mock.patch("os.scandir", side_effect=wrapper):
                result = probe(root)

            self.assertIn("entry_unreadable", codes(result))
            self.assertFalse(result["scan_complete"])

    def test_unreadable_document_is_unknown_not_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            readme = root / "README.md"
            readme.write_text(
                "# Idea\n\n" + "A substantive sentence about the plan. " * 5,
                encoding="utf-8",
            )
            real_open = os.open

            def guarded_open(path, flags, *args, **kwargs):
                if os.path.realpath(os.fspath(path)) == os.path.realpath(str(readme)):
                    raise PermissionError(13, "Permission denied")
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=guarded_open):
                result = probe(root)

            self.assertIn("document_unreadable", codes(result))
            self.assertFalse(result["scan_complete"])
            self.assertEqual(result["classification"], "unknown")

    def test_document_read_cap_is_reported_and_not_confident(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            for index in range(5):
                (root / "doc{}.md".format(index)).write_text(
                    "# Doc\n\n" + "A substantive sentence about the product. " * 3,
                    encoding="utf-8",
                )
            with mock.patch.object(PROBE, "MAX_DOCUMENT_READS", 3):
                result = probe(root)

            self.assertIn("document_read_limit_reached", codes(result))
            self.assertFalse(result["scan_complete"])
            self.assertEqual(result["classification"], "unknown")

    def test_depth_probe_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            shallow = root / "one"
            (shallow / "two").mkdir(parents=True)
            real_scandir = os.scandir

            def wrapper(path=".", *args, **kwargs):
                if os.path.realpath(os.fspath(path)) == os.path.realpath(str(shallow)):
                    raise PermissionError(13, "Permission denied")
                return real_scandir(path, *args, **kwargs)

            with mock.patch("os.scandir", side_effect=wrapper):
                result = probe(root, max_depth=1)

            self.assertIn("directory_unreadable", codes(result))
            self.assertFalse(result["scan_complete"])


class SensitiveAreaTests(unittest.TestCase):
    def test_sensitive_directory_is_reported_but_never_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            (root / ".ssh").mkdir(parents=True)
            (root / ".ssh" / "README.md").write_text(
                "SECRET-NOTE {}\n".format(SECRET_SENTINEL), encoding="utf-8"
            )
            (root / ".ssh" / "id_rsa").write_text(
                "PRIVATE KEY MATERIAL\n", encoding="utf-8"
            )
            opened = []
            real_open = os.open

            def guarded_open(path, flags, *args, **kwargs):
                opened.append(os.fspath(path))
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=guarded_open):
                result = probe(root)

            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(SECRET_SENTINEL, rendered)
            self.assertEqual([p for p in opened if ".ssh" in p], [])
            self.assertIn("secret", basis_kinds(result))
            self.assertIn(".ssh", basis_paths(result))
            self.assertEqual(result["classification"], "existing")

    def test_env_only_folder_is_existing_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".env").write_text(
                "TOKEN={}\n".format(SECRET_SENTINEL), encoding="utf-8"
            )
            result = probe(tmp)
            self.assertEqual(result["classification"], "existing")
            self.assertTrue(result["scan_complete"])
            self.assertIn("secret", basis_kinds(result))
            self.assertNotIn(SECRET_SENTINEL, json.dumps(result, ensure_ascii=False))


class RootSymlinkTests(unittest.TestCase):
    def test_selected_root_symlink_is_resolved_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            (real / "src").mkdir(parents=True)
            (real / ".git").mkdir()
            (real / "src" / "app.py").write_text("print('code')\n", encoding="utf-8")
            link = Path(tmp) / "link"
            os.symlink(str(real), str(link))

            result = probe(link)
            self.assertEqual(
                result["selected_scope"]["root"], os.path.abspath(str(link))
            )
            self.assertEqual(
                result["selected_scope"]["resolved_root"],
                os.path.realpath(str(real)),
            )
            self.assertTrue(result["selected_scope"]["is_git_repo"])
            self.assertEqual(result["classification"], "existing")

    def test_symlinked_parent_directory_is_traversed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_parent = Path(tmp) / "realparent"
            (real_parent / "child" / "src").mkdir(parents=True)
            (real_parent / "child" / "src" / "app.py").write_text(
                "print('code')\n", encoding="utf-8"
            )
            link_parent = Path(tmp) / "linkparent"
            os.symlink(str(real_parent), str(link_parent))

            result = probe(link_parent / "child")
            self.assertEqual(result["classification"], "existing")
            self.assertEqual(
                result["selected_scope"]["root"],
                os.path.abspath(str(link_parent / "child")),
            )


if __name__ == "__main__":
    unittest.main()
