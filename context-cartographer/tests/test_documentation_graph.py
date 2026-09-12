#!/usr/bin/env python3
"""Tests for the documentation_graph CLI.

Two layers:

* In-process tests inject fake index and renderer modules straight into the CLI
  (dependency injection inside the tests only; there is no public environment
  switch for helper paths). They cover report semantics, freshness, atomic
  writes, outline/section, and filesystem safety.
* End-to-end tests run the real CLI as a subprocess against the real
  ``documentation_index.py`` and ``documentation_html.py`` on temporary
  projects, including a copy of the installed package run from another working
  directory. They skip with an explicit reason while a helper is missing.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
REPO = HERE.parents[1]
SCRIPTS = REPO / "scripts"
GRAPH_PATH = SCRIPTS / "documentation_graph.py"
REAL_INDEX = SCRIPTS / "documentation_index.py"
REAL_RENDER = SCRIPTS / "documentation_html.py"
REAL_HELPERS_READY = REAL_INDEX.is_file() and REAL_RENDER.is_file()
GRAPH_RELPATH = Path(".context-cartographer") / "documentation-graph.html"


def load_real_index_module():
    """Load the shared index so the end-to-end tests can read the real parse result."""

    spec = importlib.util.spec_from_file_location(
        "cc_graph_tests_real_index", REAL_INDEX
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_graph_module():
    spec = importlib.util.spec_from_file_location("cc_graph_under_test", GRAPH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GRAPH = load_graph_module()


# --------------------------------------------------------------------------
# Fake helpers (injected only inside these tests)
# --------------------------------------------------------------------------


def heading(text, anchor, level=1, line_start=1, line_end=2):
    return {"text": text, "anchor": anchor, "level": level,
            "line_start": line_start, "line_end": line_end}


def link(target, resolved=True, line=1, raw=None):
    return {"text": "", "raw": raw or target, "target": target, "anchor": None,
            "resolved": resolved, "line": line, "kind": "link"}


def document(path, *, title="", text="", headings=(), links=(), fingerprint="sha256:doc"):
    return {"path": path, "title": title, "area": "docs", "text": text,
            "fingerprint": fingerprint, "parse_complete": True,
            "headings": list(headings), "links": list(links)}


def make_index(documents, *, topics=(), dependencies=(), issues=(), scan_complete=True,
               traversal_complete=True, owner_coverage_value="evaluated",
               fingerprint_value="sha256:fp1", scope_mode="declared",
               map_format_supported=True, has_topic_table=True):
    return {
        "schema_version": 1,
        "format_version": 1,
        "map_path": "docs/architecture.md",
        "scope_mode": scope_mode,
        "scan_complete": scan_complete,
        "traversal_complete": traversal_complete,
        "map_format_supported": map_format_supported,
        "has_topic_table": has_topic_table,
        "source_fingerprint": fingerprint_value,
        "owner_coverage": owner_coverage_value,
        "scope": {"roots": ["AGENTS.md"], "include": ["docs/"], "exclude": []},
        "documents": list(documents),
        "topics": list(topics),
        "dependencies": list(dependencies),
        "format_issues": list(issues),
    }


def base_documents():
    return [
        document("AGENTS.md", title="Agents", text="# Agents\n",
                 headings=[heading("Agents", "agents", line_start=1, line_end=2)],
                 links=[link("docs/architecture.md", line=1)]),
        document("docs/architecture.md", title="Map", text="# Map\n",
                 headings=[heading("Map", "map", line_start=1, line_end=2)],
                 links=[link("docs/deploy.md", line=1)]),
        document("docs/deploy.md", title="Deploy",
                 text="# Deploy\n\n## Rollback\n\nRestore the previous release.\n",
                 headings=[heading("Rollback", "rollback", level=2, line_start=3, line_end=5)]),
    ]


def base_topics():
    return [{"id": "deployment.rollback", "purpose": "Restore the previous release",
             "owner": "docs/deploy.md#rollback", "read_when": "Release work",
             "file": "docs/architecture.md", "line": 5}]


def topic_chain(total):
    topics = [{"id": f"topic.{i}", "purpose": "p", "owner": "docs/deploy.md#rollback",
               "read_when": "w", "file": "docs/architecture.md", "line": i + 1}
              for i in range(total)]
    dependencies = [{"topic": f"topic.{i}", "depends_on": [f"topic.{i + 1}"], "reason": "r",
                     "file": "docs/architecture.md", "line": i + 1}
                    for i in range(total - 1)]
    return topics, dependencies


def topic_cycle(total):
    topics = [{"id": f"topic.{i}", "purpose": "p", "owner": "docs/deploy.md#rollback",
               "read_when": "w", "file": "docs/architecture.md", "line": i + 1}
              for i in range(total)]
    dependencies = [{"topic": f"topic.{i}", "depends_on": [f"topic.{(i + 1) % total}"],
                     "reason": "r", "file": "docs/architecture.md", "line": i + 1}
                    for i in range(total)]
    return topics, dependencies


def fake_section_range(document_dict, anchor):
    """Mirror the shared index semantics: heading anchors and line ranges."""

    headings = list(document_dict.get("headings") or [])
    lines = str(document_dict.get("text", "")).splitlines()
    path = document_dict.get("path")
    first_heading_line = min(
        (int(item.get("line_start") or 1) for item in headings),
        default=1,
    )
    preamble = None
    if first_heading_line > 1:
        preamble = {
            "text": "\n".join(lines[:first_heading_line - 1]),
            "line_start": 1,
            "line_end": first_heading_line - 1,
        }
    matches = [h for h in headings if str(h.get("anchor")) == anchor]
    candidates = [
        {"anchor": h.get("anchor"), "title": h.get("text"), "level": h.get("level"),
         "line_start": h.get("line_start")}
        for h in headings
    ]
    if len(matches) != 1:
        return {
            "ok": False,
            "code": "anchor_collision" if len(matches) > 1 else "anchor_missing",
            "path": path, "anchor": anchor, "title": None, "level": None,
            "start": None, "end": None, "line_start": None, "line_end": None,
            "parents": [], "ancestors": [], "intro": [], "preamble": preamble,
            "candidates": candidates, "text": "",
        }
    target = matches[0]
    start = int(target.get("line_start") or 1)
    level = int(target.get("level") or 1)
    end = len(lines)
    for other in headings:
        other_line = int(other.get("line_start") or 0)
        other_level = int(other.get("level") or 1)
        if other_line > start and other_level <= level:
            end = other_line - 1
            break
    parents = [
        {"text": h.get("text"), "anchor": h.get("anchor"), "level": h.get("level"),
         "line_start": h.get("line_start")}
        for h in headings
        if int(h.get("level") or 1) < level and int(h.get("line_start") or 0) < start
    ]
    return {
        "ok": True, "code": None, "path": path, "anchor": anchor,
        "title": target.get("text"), "level": level,
        "start": start, "end": end, "line_start": start, "line_end": end,
        "parents": parents, "ancestors": parents, "intro": [], "preamble": preamble,
        "candidates": [], "text": "\n".join(lines[start - 1:end]),
    }


class FakeIndex:
    """Minimal stand-in for documentation_index.py used by the CLI."""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def build_index(self, root, map_path="docs/architecture.md", scope=None):
        index = copy.deepcopy(self.sequence[min(self.calls, len(self.sequence) - 1)])
        self.calls += 1
        index.setdefault("root", str(root))
        index.setdefault("map_path", map_path)
        return index

    def fingerprint(self, index):
        return index["source_fingerprint"]

    def owner_coverage(self, index):
        return index.get("owner_coverage") or "evaluated"

    def section_range(self, document_dict, anchor):
        return fake_section_range(document_dict, anchor)


class FakeRenderer:
    """Minimal stand-in for documentation_html.py used by the CLI."""

    RENDERER_VERSION = "test-1"

    def __init__(self, fingerprint=None, *, fail_render=False, fail_fingerprint=False):
        self._fingerprint = fingerprint or ("sha256:" + "a" * 64)
        self.fail_render = fail_render
        self.fail_fingerprint = fail_fingerprint

    def renderer_fingerprint(self):
        if self.fail_fingerprint:
            raise RuntimeError("fingerprint unavailable")
        return self._fingerprint

    def render_graph(self, index, report):
        if self.fail_render:
            raise ValueError("renderer exploded")
        payload = json.dumps(
            {"index": index, "report": report,
             "renderer_version": self.RENDERER_VERSION,
             "renderer_fingerprint": self.renderer_fingerprint()},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        for needle, escape in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                               ("/", "\\u002f")):
            payload = payload.replace(needle, escape)
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f'<meta name="context-cartographer-renderer" content="{self.renderer_fingerprint()}">'
            "</head><body>"
            f'<script type="application/json" id="documentation-graph-data">{payload}</script>'
            "</body></html>\n"
        )


def run_cli(args, *, index_module, render_module):
    """Run the CLI in-process with injected helper modules."""

    def load_index():
        if index_module is None:
            raise GRAPH.GraphError("helper_unavailable", "index helper missing", GRAPH.EXIT_USAGE)
        return index_module

    def load_render():
        if render_module is None:
            raise GRAPH.GraphError("renderer_unavailable", "renderer missing", GRAPH.EXIT_USAGE)
        return render_module

    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(GRAPH, "load_index_module", load_index), \
            mock.patch.object(GRAPH, "load_render_module", load_render):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = GRAPH.run(list(args))
    return code, out.getvalue(), err.getvalue()


class CycleDetectionTest(unittest.TestCase):
    """Guard the iterative SCC against deep chains and large cycles."""

    def test_long_chain_is_not_a_cycle(self):
        edges = {str(i): {str(i + 1)} for i in range(1200)}
        edges["1200"] = set()
        self.assertEqual(GRAPH._cycle_groups(edges), [])

    def test_large_cycle_is_one_group(self):
        total = 2000
        cycle = {str(i): {str((i + 1) % total)} for i in range(total)}
        groups = GRAPH._cycle_groups(cycle)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), total)

    def test_self_edges_are_not_cycle_groups(self):
        self.assertEqual(GRAPH._cycle_groups({"x": {"x"}}), [])
        self.assertEqual(GRAPH._self_edges({"x": {"x"}, "y": set()}), ["x"])


class GraphCliTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cc-graph-root-"))
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "architecture.md").write_text("# Map\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        self.renderer = FakeRenderer()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, args, sequence, *, renderer=..., index_module=None):
        if index_module is None:
            index_module = FakeIndex(sequence)
        if renderer is ...:
            renderer = self.renderer
        return run_cli(["--root", str(self.root), *args],
                       index_module=index_module, render_module=renderer)

    def artifact(self):
        return self.root / GRAPH_RELPATH

    def json_report(self, out):
        return json.loads(out)

    def codes(self, payload, level):
        return {entry["code"] for entry in payload[level]}

    def snapshot(self):
        entries = {}
        for path in sorted(self.root.rglob("*")):
            stat = path.lstat()
            entries[str(path.relative_to(self.root))] = (stat.st_mtime_ns, stat.st_size)
        return entries

    # -- check -----------------------------------------------------------

    def test_check_passes_and_emits_clean_json(self):
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["owner_coverage"], "evaluated")
        self.assertEqual(payload["files_checked"], 3)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["graph_status"], "missing")

    def test_check_writes_nothing_on_disk(self):
        before = self.snapshot()
        code, _, err = self.cli(["--check"], [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".context-cartographer").exists())

    def test_orphan_warning_and_link_cycle_info(self):
        docs = [
            document("AGENTS.md", headings=[heading("Agents", "agents")],
                     links=[link("docs/architecture.md")]),
            document("docs/architecture.md", headings=[heading("Map", "map")],
                     links=[link("docs/a.md")]),
            document("docs/a.md", headings=[heading("A", "a")], links=[link("docs/b.md")]),
            document("docs/b.md", headings=[heading("B", "b")], links=[link("docs/a.md")]),
            document("docs/lonely.md", headings=[heading("Lonely", "lonely")]),
        ]
        code, out, err = self.cli(["--check", "--json"], [make_index(docs)])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertIn("orphan_document", self.codes(payload, "warnings"))
        self.assertIn("link_cycle", self.codes(payload, "info"))
        self.assertTrue(any("docs/lonely.md" in (entry.get("message") or "")
                            for entry in payload["warnings"]))

    def test_ordinary_self_link_is_not_a_failure(self):
        docs = base_documents()
        docs[2]["links"] = [link("docs/deploy.md", line=1)]
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["errors"], [])
        self.assertNotIn("link_cycle", self.codes(payload, "info"))

    def test_image_links_do_not_create_document_edges(self):
        docs = base_documents()
        docs[0]["links"] = [{
            "text": "", "raw": "docs/architecture.md", "target": "docs/architecture.md",
            "anchor": None, "resolved": True, "line": 1, "kind": "image",
        }]
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertIn("owner_unreachable", self.codes(payload, "errors"))
        self.assertIn("orphan_document", self.codes(payload, "warnings"))

    # -- topics, dependencies, reachability ------------------------------

    def test_duplicate_topic_owner_is_error(self):
        topics = base_topics() + [{"id": "deployment.rollback", "purpose": "Other",
                                   "owner": "docs/architecture.md#map", "read_when": "x"}]
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=topics)])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "fail")
        self.assertIn("duplicate_topic_owner", self.codes(payload, "errors"))

    def test_topic_without_owner_is_error(self):
        topics = [{"id": "a.b", "purpose": "p", "owner": "", "read_when": "w"}]
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=topics)])
        self.assertEqual(code, 1, err)
        self.assertIn("topic_without_owner", self.codes(self.json_report(out), "errors"))

    def test_topic_owner_outside_scope_is_error(self):
        topics = [{"id": "a.b", "purpose": "p", "owner": "docs/ghost.md#x", "read_when": "w"}]
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=topics)])
        self.assertEqual(code, 1, err)
        self.assertIn("topic_owner_unresolved", self.codes(self.json_report(out), "errors"))

    def test_unreachable_required_owner_is_error(self):
        docs = base_documents() + [document("docs/hidden.md", headings=[heading("Hidden", "hidden")])]
        topics = [{"id": "a.b", "purpose": "p", "owner": "docs/hidden.md#hidden", "read_when": "w"}]
        code, out, err = self.cli(["--check", "--json"], [make_index(docs, topics=topics)])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertIn("owner_unreachable", self.codes(payload, "errors"))
        self.assertNotIn("orphan_document", self.codes(payload, "warnings"))

    def test_dependency_unknown_topic_is_error(self):
        dependencies = [{"topic": "deployment.rollback", "depends_on": ["ghost.topic"],
                         "reason": "needs it"}]
        code, out, err = self.cli(
            ["--check", "--json"],
            [make_index(base_documents(), topics=base_topics(), dependencies=dependencies)])
        self.assertEqual(code, 1, err)
        self.assertIn("dependency_unknown_topic", self.codes(self.json_report(out), "errors"))

    def test_prerequisite_cycle_is_warning(self):
        topics = base_topics() + [
            {"id": "deployment.backup", "purpose": "Backup",
             "owner": "docs/deploy.md#rollback", "read_when": "Backup work"},
        ]
        dependencies = [
            {"topic": "deployment.rollback", "depends_on": ["deployment.backup"], "reason": "r"},
            {"topic": "deployment.backup", "depends_on": ["deployment.rollback"], "reason": "r"},
        ]
        code, out, err = self.cli(
            ["--check", "--json"],
            [make_index(base_documents(), topics=topics, dependencies=dependencies)])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertIn("prerequisite_cycle", self.codes(payload, "warnings"))
        self.assertNotIn("prerequisite_cycle", self.codes(payload, "errors"))

    def test_prerequisite_self_cycle_is_reported(self):
        dependencies = [{"topic": "deployment.rollback",
                         "depends_on": ["deployment.rollback"], "reason": "self"}]
        code, out, err = self.cli(
            ["--check", "--json"],
            [make_index(base_documents(), topics=base_topics(), dependencies=dependencies)])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertIn("prerequisite_cycle", self.codes(payload, "warnings"))
        self.assertTrue(any("deployment.rollback -> deployment.rollback" in (e.get("message") or "")
                            for e in payload["warnings"]))

    def test_large_dependency_chain_does_not_crash(self):
        topics, dependencies = topic_chain(1201)
        code, out, err = self.cli(
            ["--check", "--json"],
            [make_index(base_documents(), topics=topics, dependencies=dependencies)])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["errors"], [])
        self.assertNotIn("prerequisite_cycle", self.codes(payload, "warnings"))

    def test_large_dependency_cycle_is_reported_once(self):
        topics, dependencies = topic_cycle(1500)
        code, out, err = self.cli(
            ["--check", "--json"],
            [make_index(base_documents(), topics=topics, dependencies=dependencies)])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        cycles = [e for e in payload["warnings"] if e["code"] == "prerequisite_cycle"]
        self.assertEqual(len(cycles), 1)

    # -- legacy and incomplete scans -------------------------------------

    def test_legacy_map_is_unknown_not_pass(self):
        index = make_index(base_documents(), owner_coverage_value="not_evaluated",
                           scope_mode="bootstrap", map_format_supported=False,
                           has_topic_table=False)
        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "unknown")
        self.assertEqual(payload["owner_coverage"], "not_evaluated")

    def test_incomplete_scan_is_unknown_not_pass(self):
        index = make_index(base_documents(), topics=base_topics(), scan_complete=False)
        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "unknown")
        self.assertFalse(payload["scan_complete"])

    def test_missing_scan_complete_is_unknown_not_pass(self):
        index = make_index(base_documents(), topics=base_topics())
        del index["scan_complete"]
        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "unknown")
        self.assertFalse(payload["scan_complete"])

    def test_stopped_traversal_is_unknown_not_pass(self):
        index = make_index(base_documents(), topics=base_topics(), traversal_complete=False)
        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.json_report(out)["status"], "unknown")

    def test_unsupported_construct_warning_blocks_pass(self):
        issues = [{"code": "unsupported_markdown", "severity": "warning",
                   "file": "docs/architecture.md", "line": 2, "section": None, "target": None,
                   "message": "Unsupported MDX block"}]
        index = make_index(base_documents(), topics=base_topics(), issues=issues,
                           scan_complete=False)
        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(self.json_report(out)["status"], "unknown")

    # -- graph requirement ----------------------------------------------

    def test_require_graph_missing_is_error(self):
        code, out, err = self.cli(["--check", "--json", "--require-graph"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "missing")
        self.assertIn("graph_missing", self.codes(payload, "errors"))

    def test_require_graph_without_check_is_usage_error(self):
        code, out, err = self.cli(["--write", "--require-graph", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        self.assertIn("invalid_arguments", self.codes(self.json_report(out), "errors"))

    # -- write, freshness, atomicity ------------------------------------

    def test_write_creates_graph_then_noop(self):
        index = make_index(base_documents(), topics=base_topics())
        code, out, err = self.cli(["--write", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertTrue(self.artifact().is_file())
        self.assertIn("documentation-graph-data", self.artifact().read_text(encoding="utf-8"))
        self.assertEqual(self.json_report(out)["graph_status"], "fresh")

        stamp = self.artifact().stat().st_mtime_ns
        code, out, err = self.cli(["--write"], [index])
        self.assertEqual(code, 0, err)
        self.assertIn("unchanged", out)
        self.assertEqual(self.artifact().stat().st_mtime_ns, stamp)

    def test_check_after_write_is_fresh_then_stale_on_text_change(self):
        index = make_index(base_documents(), topics=base_topics())
        self.assertEqual(self.cli(["--write"], [index])[0], 0)

        code, out, err = self.cli(["--check", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.json_report(out)["graph_status"], "fresh")

        changed = make_index(base_documents(), topics=base_topics(),
                             fingerprint_value="sha256:fp2")
        code, out, err = self.cli(["--check", "--json"], [changed])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "stale")
        self.assertIn("graph_stale", self.codes(payload, "warnings"))

    def test_require_graph_stale_is_error(self):
        self.cli(["--write"], [make_index(base_documents(), topics=base_topics())])
        changed = make_index(base_documents(), topics=base_topics(), fingerprint_value="sha256:fp2")
        code, out, err = self.cli(["--check", "--json", "--require-graph"], [changed])
        self.assertEqual(code, 1)
        self.assertIn("graph_stale", self.codes(self.json_report(out), "errors"))

    def test_renderer_change_invalidates_graph(self):
        self.cli(["--write"], [make_index(base_documents(), topics=base_topics())])
        other = FakeRenderer(fingerprint="sha256:" + "b" * 64)
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())],
                                  renderer=other)
        self.assertEqual(self.json_report(out)["graph_status"], "stale")

    def test_write_repairs_corrupted_artifact(self):
        index = make_index(base_documents(), topics=base_topics())
        self.cli(["--write"], [index])
        good = self.artifact().read_bytes()
        self.artifact().write_bytes(good + b"<!-- tampered -->\n")
        self.assertNotEqual(good, self.artifact().read_bytes())

        code, out, err = self.cli(["--write"], [index])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.artifact().read_bytes(), good)

    def test_recorded_source_missing_is_unverified_not_fresh(self):
        artifact = self.artifact()
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            '<script type="application/json" id="documentation-graph-data">'
            '{"index": {}, "renderer_fingerprint": "sha256:' + "a" * 64 + '"}'
            "</script>\n",
            encoding="utf-8",
        )
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "unverified")
        self.assertIn("graph_unverified", self.codes(payload, "warnings"))
        self.assertNotEqual(payload["status"], "pass")

    def test_renderer_fingerprint_failure_is_never_fresh(self):
        self.cli(["--write"], [make_index(base_documents(), topics=base_topics())])
        broken = FakeRenderer(fail_fingerprint=True)
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())],
                                  renderer=broken)
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "unverified")
        self.assertIn("graph_unverified", self.codes(payload, "warnings"))

        code, out, err = self.cli(["--write", "--json"],
                                  [make_index(base_documents(), topics=base_topics())],
                                  renderer=broken)
        self.assertEqual(code, 2)
        self.assertIn("renderer_fingerprint_failed", self.codes(self.json_report(out), "errors"))

    def test_write_aborts_when_sources_change_during_build(self):
        index = make_index(base_documents(), topics=base_topics())
        self.cli(["--write"], [index])
        before = self.artifact().read_bytes()

        changed = make_index(base_documents(), topics=base_topics(),
                             fingerprint_value="sha256:fp2")
        code, out, err = self.cli(["--write", "--json"], [index, changed])
        self.assertEqual(code, 2)
        self.assertIn("source_changed_during_write", self.codes(self.json_report(out), "errors"))
        self.assertEqual(self.artifact().read_bytes(), before)

    def test_renderer_failure_preserves_previous_artifact(self):
        index = make_index(base_documents(), topics=base_topics())
        self.cli(["--write"], [index])
        before = self.artifact().read_bytes()

        code, out, err = self.cli(["--write", "--json"], [index],
                                  renderer=FakeRenderer(fail_render=True))
        self.assertEqual(code, 2)
        self.assertIn("render_failed", self.codes(self.json_report(out), "errors"))
        self.assertEqual(self.artifact().read_bytes(), before)

    def test_write_with_docs_errors_still_writes_and_fails(self):
        topics = [{"id": "a.b", "purpose": "p", "owner": "docs/ghost.md#x", "read_when": "w"}]
        code, out, err = self.cli(["--write", "--json"],
                                  [make_index(base_documents(), topics=topics)])
        self.assertEqual(code, 1)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["graph_status"], "fresh")
        self.assertTrue(self.artifact().is_file())

    # -- boundary safety -------------------------------------------------

    def test_check_refuses_graph_directory_symlink_escape(self):
        outside = Path(tempfile.mkdtemp(prefix="cc-graph-outside-"))
        try:
            (self.root / ".context-cartographer").symlink_to(outside, target_is_directory=True)
            code, out, err = self.cli(["--check", "--json"],
                                      [make_index(base_documents(), topics=base_topics())])
            self.assertEqual(code, 2, out + err)
            self.assertIn("graph_dir_escape", self.codes(self.json_report(out), "errors"))
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_check_refuses_artifact_symlink(self):
        directory = self.root / ".context-cartographer"
        directory.mkdir()
        victim = self.root / "precious.txt"
        victim.write_text("keep me", encoding="utf-8")
        (directory / "documentation-graph.html").symlink_to(victim)
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2, out + err)
        self.assertIn("graph_path_symlink", self.codes(self.json_report(out), "errors"))
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep me")

    def test_write_refuses_graph_directory_symlink_escape(self):
        outside = Path(tempfile.mkdtemp(prefix="cc-graph-outside-"))
        try:
            (self.root / ".context-cartographer").symlink_to(outside, target_is_directory=True)
            code, out, err = self.cli(["--write", "--json"],
                                      [make_index(base_documents(), topics=base_topics())])
            self.assertEqual(code, 2)
            self.assertIn("graph_dir_escape", self.codes(self.json_report(out), "errors"))
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_write_refuses_artifact_symlink(self):
        directory = self.root / ".context-cartographer"
        directory.mkdir()
        victim = self.root / "precious.txt"
        victim.write_text("keep me", encoding="utf-8")
        (directory / "documentation-graph.html").symlink_to(victim)
        code, out, err = self.cli(["--write", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        self.assertIn("graph_path_symlink", self.codes(self.json_report(out), "errors"))
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep me")

    # -- outline and section --------------------------------------------

    def test_outline_uses_index_headings_only(self):
        text = "# Deploy\n\n```\n## Not A Heading\n```\n\n## Rollback\n\nRestore.\n"
        docs = base_documents()
        docs[2] = document(
            "docs/deploy.md", title="Deploy", text=text,
            headings=[heading("Deploy", "deploy", line_start=1, line_end=2),
                      heading("Rollback", "rollback", level=2, line_start=7, line_end=9)],
        )
        code, out, err = self.cli(["--outline", "docs/deploy.md", "--json"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual([h["anchor"] for h in payload["headings"]], ["deploy", "rollback"])

    def test_outline_rejects_out_of_scope_and_missing_headings(self):
        docs = base_documents()
        code, out, err = self.cli(["--outline", "docs/ghost.md"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 1)
        self.assertIn("document_not_in_scope", err)

        docs[2]["headings"] = None
        code, out, err = self.cli(["--outline", "docs/deploy.md", "--json"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 2)
        self.assertIn("index_contract_mismatch", self.codes(self.json_report(out), "errors"))

    def test_section_exact_line_range_and_missing_anchor(self):
        text = "# Deploy\n\n## Rollback\n\nRestore.\n\n## Other\n\nAgain.\n"
        docs = base_documents()
        docs[2] = document(
            "docs/deploy.md", title="Deploy", text=text,
            headings=[heading("Rollback", "rollback", level=2, line_start=3, line_end=5),
                      heading("Other", "other", level=2, line_start=7, line_end=9)],
        )
        index = make_index(docs, topics=base_topics())

        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertTrue(payload["ok"])
        self.assertEqual((payload["line_start"], payload["line_end"]), (3, 6))
        self.assertIn("Restore.", payload["text"])

        code, out, err = self.cli(["--section", "docs/deploy.md#nope", "--json"], [index])
        self.assertEqual(code, 1)
        payload = self.json_report(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "anchor_missing")
        self.assertTrue(payload["candidates"])

    def test_plain_section_includes_preamble_and_parent_headings(self):
        text = "Document constraint.\n\n# Deploy\n\nParent intro.\n\n## Rollback\n\nRestore.\n"
        docs = base_documents()
        docs[2] = document(
            "docs/deploy.md", title="Deploy", text=text,
            headings=[heading("Deploy", "deploy", level=1, line_start=3, line_end=9),
                      heading("Rollback", "rollback", level=2, line_start=7, line_end=9)],
        )
        index = make_index(docs, topics=base_topics())

        code, out, err = self.cli(["--section", "docs/deploy.md#rollback"], [index])

        self.assertEqual(code, 0, err)
        self.assertIn("Document constraint.", out)
        self.assertIn("# Deploy", out)
        self.assertIn("## Rollback", out)
        self.assertLess(out.index("Document constraint."), out.index("# Deploy"))
        self.assertLess(out.index("# Deploy"), out.index("## Rollback"))

    def test_section_requires_an_anchor(self):
        code, out, err = self.cli(["--section", "docs/deploy.md"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        self.assertIn("target_missing", err)

    def test_ambiguous_anchor_is_not_silently_substituted(self):
        text = "# D\n\n## Rollback\n\nA\n\n## Rollback\n\nB\n"
        docs = base_documents()
        docs[2] = document(
            "docs/deploy.md", title="Deploy", text=text,
            headings=[heading("Rollback", "rollback", level=2, line_start=3, line_end=5),
                      heading("Rollback", "rollback", level=2, line_start=7, line_end=9)],
        )
        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"],
                                  [make_index(docs, topics=base_topics())])
        self.assertEqual(code, 1)
        payload = self.json_report(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "anchor_collision")
        self.assertEqual(len(payload["candidates"]), 2)

    def test_russian_and_space_paths(self):
        path = "docs/док с пробелом.md"
        docs = base_documents() + [
            document(path, title="Документ", text="# Документ\n\n## Раздел\n\nТекст.\n",
                     headings=[heading("Раздел", "раздел", level=2, line_start=3, line_end=5)]),
        ]
        index = make_index(docs, topics=base_topics())
        code, out, err = self.cli(["--outline", path, "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.json_report(out)["headings"][0]["anchor"], "раздел")

        code, out, err = self.cli(["--section", path + "#раздел", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertTrue(self.json_report(out)["ok"])

    # -- incomplete parses ----------------------------------------------

    def _incomplete_index(self, *, issues, incomplete_path="docs/deploy.md"):
        docs = base_documents()
        for entry in docs:
            if entry["path"] == incomplete_path:
                entry["parse_complete"] = False
        return docs, make_index(docs, topics=base_topics(), issues=issues,
                                scan_complete=False)

    def test_outline_refuses_a_document_with_an_incomplete_parse(self):
        issues = [{"code": "document_too_large", "severity": "warning",
                   "file": "docs/deploy.md", "line": None, "section": None, "target": None,
                   "message": "Document is larger than 2097152 bytes and was capped"}]
        docs, index = self._incomplete_index(issues=issues)

        code, out, err = self.cli(["--outline", "docs/deploy.md", "--json"], [index])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "document_parse_incomplete")
        self.assertEqual(payload["headings"], [])
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["document_too_large"])

        # The human-readable form explains the failure and claims no anchor.
        code, out, err = self.cli(["--outline", "docs/deploy.md"], [index])
        self.assertEqual(code, 1)
        self.assertIn("document_parse_incomplete", err)
        self.assertIn("document_too_large", err)
        self.assertNotIn("rollback", out)

    def test_section_refuses_a_document_with_an_incomplete_parse(self):
        issues = [{"code": "unsupported_markdown", "severity": "warning",
                   "file": "docs/deploy.md", "line": 3, "section": None, "target": None,
                   "message": "MDX/JSX content is outside the supported Markdown subset"}]
        docs, index = self._incomplete_index(issues=issues)

        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "document_parse_incomplete")
        # No exact range and no substitute text are claimed.
        self.assertIsNone(payload["line_start"])
        self.assertIsNone(payload["line_end"])
        self.assertEqual(payload["text"], "")
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["unsupported_markdown"])

        code, out, err = self.cli(["--section", "docs/deploy.md#rollback"], [index])
        self.assertEqual(code, 1)
        self.assertIn("document_parse_incomplete", err)
        self.assertIn("unsupported_markdown", err)

    def test_unknown_parse_blocker_code_is_still_explained(self):
        # The shared index owns the parse decision; a blocker code this module
        # does not recognize must still be surfaced rather than dropped.
        issues = [{"code": "unsupported_html", "severity": "warning",
                   "file": "docs/deploy.md", "line": 2, "section": None, "target": None,
                   "message": "Raw HTML is outside the supported Markdown subset"}]
        docs, index = self._incomplete_index(issues=issues)
        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 1, err)
        self.assertEqual([d["code"] for d in self.json_report(out)["diagnostics"]],
                         ["unsupported_html"])

    def test_parse_blocking_issue_alone_still_fails_closed(self):
        # Even if an index update records the blocker without flipping
        # parse_complete, an unreliable address must not be served.
        issues = [{"code": "unsupported_markdown", "severity": "warning",
                   "file": "docs/deploy.md", "line": 2, "section": None, "target": None,
                   "message": "MDX/JSX content is outside the supported Markdown subset"}]
        index = make_index(base_documents(), topics=base_topics(), issues=issues)
        self.assertTrue(index["documents"][2]["parse_complete"])
        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 1, err)
        self.assertEqual(self.json_report(out)["code"], "document_parse_incomplete")

    def test_unrelated_issue_does_not_block_a_complete_document(self):
        issues = [{"code": "anchor_collision", "severity": "error",
                   "file": "docs/deploy.md", "line": 3, "section": None, "target": "rollback",
                   "message": "Anchor 'rollback' names more than one section"}]
        index = make_index(base_documents(), topics=base_topics(), issues=issues)
        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertTrue(self.json_report(out)["ok"])

    def test_incomplete_parse_without_a_recorded_issue_still_fails_closed(self):
        docs = base_documents()
        docs[2]["parse_complete"] = False
        index = make_index(docs, topics=base_topics(), scan_complete=False)
        code, out, err = self.cli(["--outline", "docs/deploy.md", "--json"], [index])
        self.assertEqual(code, 1, err)
        payload = self.json_report(out)
        self.assertEqual(payload["code"], "document_parse_incomplete")
        self.assertTrue(payload["diagnostics"])

    def test_complete_document_stays_addressable_in_an_incomplete_index(self):
        # Unrelated problems elsewhere must not block an exact read of a document
        # the index parsed completely.
        issues = [{"code": "document_unreadable", "severity": "error",
                   "file": "docs/architecture.md", "line": None, "section": None, "target": None,
                   "message": "Document could not be read"}]
        docs, index = self._incomplete_index(issues=issues,
                                             incomplete_path="docs/architecture.md")
        self.assertFalse(index["scan_complete"])

        code, out, err = self.cli(["--section", "docs/deploy.md#rollback", "--json"], [index])
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertTrue(payload["ok"])
        self.assertIn("Restore", payload["text"])

        code, out, err = self.cli(["--outline", "docs/deploy.md", "--json"], [index])
        self.assertEqual(code, 0, err)
        self.assertEqual([h["anchor"] for h in self.json_report(out)["headings"]], ["rollback"])

    # -- failures and CLI surface ---------------------------------------

    def test_missing_map_is_clean_usage_error(self):
        (self.root / "docs" / "architecture.md").unlink()
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        payload = self.json_report(out)
        self.assertEqual(payload["status"], "fail")
        self.assertIn("map_missing", self.codes(payload, "errors"))
        self.assertNotIn("Traceback", err)

    def test_missing_mode_is_usage_error(self):
        code, out, err = self.cli([], [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        self.assertIn("invalid_arguments", err)

    def test_unknown_argument_with_json_stays_json(self):
        code, out, err = self.cli(["--check", "--json", "--nope"],
                                  [make_index(base_documents(), topics=base_topics())])
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertIn("invalid_arguments", {entry["code"] for entry in payload["errors"]})
        self.assertNotIn("Traceback", out)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("usage:", err.lower())

    def test_alternate_map_path_is_passed_to_the_index(self):
        (self.root / "docs" / "private").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "private" / "map.md").write_text("# Private\n", encoding="utf-8")
        seen = {}
        payload = make_index(base_documents(), topics=base_topics())

        class RecordingIndex(FakeIndex):
            def build_index(self, root, map_path="docs/architecture.md", scope=None):
                seen["map_path"] = map_path
                return super().build_index(root, map_path=map_path, scope=scope)

        code, out, err = self.cli(["--check", "--map", "docs/private/map.md", "--json"],
                                  [payload], index_module=RecordingIndex([payload]))
        self.assertEqual(code, 0, err)
        self.assertEqual(seen["map_path"], "docs/private/map.md")

    def test_index_helper_unavailable_is_clean_error(self):
        code, out, err = run_cli(["--root", str(self.root), "--check", "--json"],
                                 index_module=None, render_module=self.renderer)
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertIn("helper_unavailable", {entry["code"] for entry in payload["errors"]})
        self.assertNotIn("Traceback", err)

    def test_check_runs_without_renderer(self):
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())],
                                  renderer=None)
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "missing")
        self.assertIn("renderer_unavailable", self.codes(payload, "info"))

    def test_check_without_renderer_but_with_artifact_is_not_pass(self):
        self.cli(["--write"], [make_index(base_documents(), topics=base_topics())])
        code, out, err = self.cli(["--check", "--json"],
                                  [make_index(base_documents(), topics=base_topics())],
                                  renderer=None)
        self.assertEqual(code, 0, err)
        payload = self.json_report(out)
        self.assertEqual(payload["graph_status"], "unverified")
        self.assertIn("graph_unverified", self.codes(payload, "warnings"))


# --------------------------------------------------------------------------
# End-to-end tests against the real index and renderer
# --------------------------------------------------------------------------


def run_script(script, root, *args, cwd="/"):
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        capture_output=True, text=True, cwd=str(cwd), check=False,
    )


def write_minimal_project(root: Path, *, map_rel="docs/architecture.md"):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text(
        "# Agents\n\nRead [the map](docs/architecture.md).\n", encoding="utf-8"
    )
    (root / map_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / map_rel).write_text(
        "<!-- context-cartographer: format_version=1 -->\n\n"
        "# Architecture Map\n\n"
        "| Kind | Path | Notes |\n"
        "| --- | --- | --- |\n"
        "| root | `AGENTS.md` | router |\n"
        "| include | `docs/` | documentation area |\n\n"
        "| Topic ID | Purpose | Owner | Read when |\n"
        "| --- | --- | --- | --- |\n"
        "| deployment.rollback | Restore the previous release "
        "| [Rollback](deploy.md#rollback) | Changing recovery |\n",
        encoding="utf-8",
    )
    (root / "docs" / "deploy.md").write_text(
        "# Deploy\n\nRelease notes.\n\n## Rollback\n\nRestore the previous release.\n",
        encoding="utf-8",
    )


@unittest.skipUnless(
    REAL_HELPERS_READY,
    "real documentation_index.py and documentation_html.py are not finished yet",
)
class GraphEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cc-e2e-root-"))
        write_minimal_project(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def check(self, *args):
        return run_script(GRAPH_PATH, self.root, "--check", "--json", *args)

    def test_check_write_noop_and_freshness(self):
        self.assertFalse((self.root / ".context-cartographer").exists())
        first = self.check()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout)["status"], "pass")
        self.assertFalse((self.root / ".context-cartographer").exists())

        written = run_script(GRAPH_PATH, self.root, "--write", "--json")
        self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
        report = json.loads(written.stdout)
        self.assertEqual(report["graph_status"], "fresh")

        artifact = self.root / GRAPH_RELPATH
        self.assertTrue(artifact.is_file())
        stamp = artifact.stat().st_mtime_ns

        again = run_script(GRAPH_PATH, self.root, "--write", "--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(artifact.stat().st_mtime_ns, stamp)

        fresh = self.check("--require-graph")
        self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)
        self.assertEqual(json.loads(fresh.stdout)["graph_status"], "fresh")

    def test_body_only_edit_makes_graph_stale(self):
        self.assertEqual(run_script(GRAPH_PATH, self.root, "--write").returncode, 0)
        deploy = self.root / "docs" / "deploy.md"
        deploy.write_text(deploy.read_text(encoding="utf-8") + "\nExtra sentence.\n",
                          encoding="utf-8")
        stale = self.check()
        self.assertEqual(stale.returncode, 0, stale.stdout + stale.stderr)
        self.assertEqual(json.loads(stale.stdout)["graph_status"], "stale")
        self.assertEqual(run_script(GRAPH_PATH, self.root, "--write").returncode, 0)
        self.assertEqual(
            json.loads(self.check("--require-graph").stdout)["graph_status"], "fresh"
        )

    def test_broken_link_is_reported_and_graph_still_written(self):
        (self.root / "docs" / "deploy.md").write_text(
            "# Deploy\n\nSee [gone](missing.md).\n\n## Rollback\n\nRestore.\n",
            encoding="utf-8",
        )
        checked = self.check()
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        report = json.loads(checked.stdout)
        self.assertEqual(report["status"], "fail")
        self.assertIn("link_target_missing", {entry["code"] for entry in report["errors"]})

        written = run_script(GRAPH_PATH, self.root, "--write", "--json")
        self.assertEqual(written.returncode, 1, written.stdout + written.stderr)
        self.assertTrue((self.root / GRAPH_RELPATH).is_file())

    def test_legacy_map_is_unknown_not_pass(self):
        (self.root / "docs" / "architecture.md").write_text(
            "# Legacy Map\n\nNo format marker, no scope table, no topics.\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["owner_coverage"], "not_evaluated")

    def test_outline_and_section_use_the_real_index(self):
        outline = run_script(GRAPH_PATH, self.root, "--outline", "docs/deploy.md", "--json")
        self.assertEqual(outline.returncode, 0, outline.stdout + outline.stderr)
        anchors = [h["anchor"] for h in json.loads(outline.stdout)["headings"]]
        self.assertIn("rollback", anchors)

        section = run_script(GRAPH_PATH, self.root, "--section", "docs/deploy.md#rollback",
                             "--json")
        self.assertEqual(section.returncode, 0, section.stdout + section.stderr)
        payload = json.loads(section.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("Restore", payload["text"])

        missing = run_script(GRAPH_PATH, self.root, "--section", "docs/deploy.md#nope", "--json")
        self.assertEqual(missing.returncode, 1)
        self.assertFalse(json.loads(missing.stdout)["ok"])

    def test_incomplete_parse_is_refused_a_complete_one_is_still_read(self):
        docs = self.root / "docs"
        (docs / "mdx.md").write_text(
            "# Mdx Page\n\nimport Card from \"./Card\"\n\n<Card />\n\n## Inner\n\nBody.\n",
            encoding="utf-8",
        )
        # Lowercase raw HTML that hides Markdown structure is outside the
        # supported subset and must be flagged incomplete by the shared index
        # (owner: the index module). The heading inside the block is still
        # indexed, so only the read guard - not a missing anchor - can refuse it.
        (docs / "raw-html.md").write_text(
            "# Raw Html\n\n<div class=\"row\">\n## Inner\n</div>\n\nBody.\n",
            encoding="utf-8",
        )
        index_module = load_real_index_module()
        # "## Inner" stays inside the cap, so its anchor is real; the document is
        # still incomplete because it exceeds the size limit.
        (docs / "huge.md").write_text(
            "# Huge\n\n## Inner\n\nBody.\n\n"
            + ("x" * (index_module.MAX_DOCUMENT_BYTES + 64))
            + "\n",
            encoding="utf-8",
        )

        index = index_module.build_index(str(self.root))
        by_path = {document["path"]: document for document in index["documents"]}
        expected_incomplete = ("docs/mdx.md", "docs/raw-html.md", "docs/huge.md")
        for path in expected_incomplete:
            self.assertFalse(by_path[path]["parse_complete"], path)
        self.assertTrue(by_path["docs/deploy.md"]["parse_complete"])
        self.assertFalse(index["scan_complete"])

        for path in expected_incomplete:
            outline = run_script(GRAPH_PATH, self.root, "--outline", path, "--json")
            self.assertEqual(outline.returncode, 1, outline.stdout + outline.stderr)
            payload = json.loads(outline.stdout)
            self.assertFalse(payload["ok"], path)
            self.assertEqual(payload["code"], "document_parse_incomplete", path)
            self.assertEqual(payload["headings"], [], path)
            self.assertTrue(payload["diagnostics"], path)

            # "inner" is a real anchor in all three documents, so the guard - not
            # a missing anchor - is what must refuse the read.
            target = f"{path}#inner"
            section = run_script(GRAPH_PATH, self.root, "--section", target, "--json")
            self.assertEqual(section.returncode, 1, section.stdout + section.stderr)
            section_payload = json.loads(section.stdout)
            self.assertFalse(section_payload["ok"], target)
            self.assertEqual(section_payload["code"], "document_parse_incomplete", target)
            self.assertIsNone(section_payload["line_start"], target)
            self.assertIsNone(section_payload["line_end"], target)
            self.assertEqual(section_payload["text"], "", target)

        # A fully parsed document stays addressable inside the same incomplete
        # scan; unrelated problems never block an exact read.
        section = run_script(GRAPH_PATH, self.root, "--section",
                             "docs/deploy.md#rollback", "--json")
        self.assertEqual(section.returncode, 0, section.stdout + section.stderr)
        section_payload = json.loads(section.stdout)
        self.assertTrue(section_payload["ok"])
        self.assertIn("Restore", section_payload["text"])

    def test_rename_keeps_links_valid(self):
        (self.root / "docs" / "deploy.md").rename(self.root / "docs" / "release.md")
        map_path = self.root / "docs" / "architecture.md"
        map_path.write_text(
            map_path.read_text(encoding="utf-8").replace("deploy.md#rollback",
                                                         "release.md#rollback"),
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_alternate_private_map(self):
        private = self.root / "docs" / "private"
        private.mkdir(parents=True, exist_ok=True)
        (private / "map.md").write_text(
            "<!-- context-cartographer: format_version=1 -->\n\n"
            "# Private Map\n\n"
            "| Kind | Path | Notes |\n| --- | --- | --- |\n"
            "| root | `AGENTS.md` | router |\n"
            "| include | `docs/private/` | private notes |\n",
            encoding="utf-8",
        )
        (private / "notes.md").write_text("# Notes\n", encoding="utf-8")
        result = run_script(GRAPH_PATH, self.root, "--check", "--json",
                            "--map", "docs/private/map.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["owner_coverage"], "not_evaluated")

    def test_output_symlink_is_refused(self):
        directory = self.root / ".context-cartographer"
        directory.mkdir()
        victim = self.root / "keep.txt"
        victim.write_text("keep", encoding="utf-8")
        (directory / "documentation-graph.html").symlink_to(victim)
        result = run_script(GRAPH_PATH, self.root, "--write", "--json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    def test_concurrent_writes_leave_a_fresh_artifact(self):
        procs = [
            subprocess.Popen(
                [sys.executable, str(GRAPH_PATH), "--root", str(self.root), "--write"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd="/",
            )
            for _ in range(4)
        ]
        for proc in procs:
            _, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
        final = self.check("--require-graph")
        self.assertEqual(final.returncode, 0, final.stdout + final.stderr)
        self.assertEqual(json.loads(final.stdout)["graph_status"], "fresh")

    def test_installed_package_copy_runs_from_another_directory(self):
        workdir = Path(tempfile.mkdtemp(prefix="cc-e2e-package-"))
        elsewhere = Path(tempfile.mkdtemp(prefix="cc-e2e-cwd-"))
        try:
            installed = workdir / "context-cartographer"
            shutil.copytree(REPO, installed,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            self.assertFalse((workdir / "README.md").exists())
            self.assertFalse((workdir / "adapters").exists())
            script = installed / "scripts" / "documentation_graph.py"
            written = run_script(script, self.root, "--write", "--json", cwd=elsewhere)
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            checked = run_script(script, self.root, "--check", "--json",
                                 "--require-graph", cwd=elsewhere)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["graph_status"], "fresh")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            shutil.rmtree(elsewhere, ignore_errors=True)

    def test_renderer_asset_change_invalidates_the_graph(self):
        self.assertEqual(run_script(GRAPH_PATH, self.root, "--write").returncode, 0)
        workdir = Path(tempfile.mkdtemp(prefix="cc-e2e-asset-"))
        try:
            installed = workdir / "context-cartographer"
            shutil.copytree(REPO, installed,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            template = installed / "assets" / "documentation-graph.html"
            template.write_text(
                template.read_text(encoding="utf-8") + "\n<!-- renderer tweak -->\n",
                encoding="utf-8",
            )
            result = run_script(installed / "scripts" / "documentation_graph.py", self.root,
                                "--check", "--json", "--require-graph")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["graph_status"], "stale")
            self.assertIn("graph_stale", {entry["code"] for entry in report["errors"]})
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_corrupted_artifact_is_repaired_by_the_real_renderer(self):
        self.assertEqual(run_script(GRAPH_PATH, self.root, "--write").returncode, 0)
        artifact = self.root / GRAPH_RELPATH
        good = artifact.read_bytes()
        artifact.write_bytes(good + b"<!-- tampered -->\n")
        self.assertNotEqual(good, artifact.read_bytes())

        again = run_script(GRAPH_PATH, self.root, "--write")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("written", again.stdout)
        self.assertEqual(artifact.read_bytes(), good)

    def test_artifact_records_renderer_identity(self):
        self.assertEqual(run_script(GRAPH_PATH, self.root, "--write").returncode, 0)
        text = (self.root / GRAPH_RELPATH).read_text(encoding="utf-8")
        self.assertIn('name="context-cartographer-renderer" content="sha256:', text)
        self.assertIn('id="documentation-graph-data"', text)

    def test_unicode_and_space_paths(self):
        unicode_doc = self.root / "docs" / "док с пробелом.md"
        unicode_doc.write_text("# Документ\n\n## Раздел\n\nТекст раздела.\n", encoding="utf-8")
        map_path = self.root / "docs" / "architecture.md"
        map_path.write_text(
            map_path.read_text(encoding="utf-8").replace(
                "| deployment.rollback | Restore the previous release "
                "| [Rollback](deploy.md#rollback) | Changing recovery |",
                "| deployment.rollback | Restore the previous release "
                "| [Rollback](deploy.md#rollback) | Changing recovery |\n"
                "| doc.unicode | Unicode section "
                "| [Раздел](док%20с%20пробелом.md#раздел) | Reading |",
            ),
            encoding="utf-8",
        )
        checked = self.check()
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

        outline = run_script(GRAPH_PATH, self.root, "--outline", "docs/док с пробелом.md", "--json")
        self.assertEqual(outline.returncode, 0, outline.stdout + outline.stderr)
        self.assertIn("раздел", [h["anchor"] for h in json.loads(outline.stdout)["headings"]])

        section = run_script(GRAPH_PATH, self.root, "--section",
                             "docs/док с пробелом.md#раздел", "--json")
        self.assertEqual(section.returncode, 0, section.stdout + section.stderr)
        self.assertTrue(json.loads(section.stdout)["ok"])

    def test_filled_fixture_with_declared_dependency_passes(self):
        (self.root / "docs" / "deploy.md").write_text(
            "# Deploy\n\n## Rollback\n\nRestore the previous release.\n\n"
            "## Storage\n\nLayout.\n",
            encoding="utf-8",
        )
        map_path = self.root / "docs" / "architecture.md"
        map_path.write_text(
            map_path.read_text(encoding="utf-8").replace(
                "| deployment.rollback | Restore the previous release "
                "| [Rollback](deploy.md#rollback) | Changing recovery |",
                "| deployment.rollback | Restore the previous release "
                "| [Rollback](deploy.md#rollback) | Changing recovery |\n"
                "| deployment.storage | Storage layout "
                "| [Storage](deploy.md#storage) | Changing storage |\n\n"
                "| Topic ID | Depends on | Reason |\n| --- | --- | --- |\n"
                "| deployment.rollback | deployment.storage | Needs a restore point |",
            ),
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])

    def test_broken_root_route_is_an_error(self):
        (self.root / "AGENTS.md").write_text(
            "# Agents\n\nRead the [map](docs/ghost.md).\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "fail")
        codes = {entry["code"] for entry in report["errors"]}
        self.assertTrue(codes & {"link_target_missing", "route_unreachable"}, codes)
        self.assertIn("owner_unreachable", codes)

    def test_unreachable_map_owner_is_an_error(self):
        (self.root / "AGENTS.md").write_text(
            "# Agents\n\nNo route to the map here.\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("owner_unreachable", {entry["code"] for entry in report["errors"]})
        self.assertIn("orphan_document", {entry["code"] for entry in report["warnings"]})

    def test_image_links_do_not_count_as_routes(self):
        (self.root / "AGENTS.md").write_text(
            "# Agents\n\n![map](docs/architecture.md)\n", encoding="utf-8"
        )
        result = self.check()
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("owner_unreachable", {entry["code"] for entry in report["errors"]})


if __name__ == "__main__":
    unittest.main()
