#!/usr/bin/env python3
"""Contract tests for the offline documentation graph renderer.

``scripts/documentation_html.py`` is imported directly from the package so the
tests pin the 03-04 contract without going through the CLI:

* ``render_graph(index, report) -> str`` is a pure, deterministic function;
* the packaged template is filled in one pass, so document text containing a
  renderer placeholder token survives ``JSON.parse`` byte for byte;
* embedded document text, paths and problem messages stay inert inside the
  ``application/json`` script element and round-trip through JSON unchanged;
* the packaged template stays offline and keeps the controls 03-04 requires.

The JSON round-trip is asserted twice: with the standard library, and, when a
``node`` binary is available, with a real ``JSON.parse``.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
PACKAGE = HERE.parents[1]
RENDERER_PATH = PACKAGE / "scripts" / "documentation_html.py"
TEMPLATE_PATH = PACKAGE / "assets" / "documentation-graph.html"

PAYLOAD_RE = re.compile(
    r'<script type="application/json" id="documentation-graph-data">(.*?)</script>',
    re.S,
)
PLAIN_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)
META_FINGERPRINT_RE = re.compile(
    r'<meta name="context-cartographer-renderer" content="([^"]*)">'
)
META_VERSION_RE = re.compile(
    r'<meta name="context-cartographer-renderer-version" content="([^"]*)">'
)


def load_renderer():
    spec = importlib.util.spec_from_file_location(
        "context_cartographer_documentation_html_under_test", RENDERER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RENDERER = load_renderer()

VERSION_TOKEN = RENDERER.RENDERER_VERSION_PLACEHOLDER
FINGERPRINT_TOKEN = RENDERER.RENDERER_FINGERPRINT_PLACEHOLDER
PAYLOAD_TOKEN = RENDERER.PAYLOAD_PLACEHOLDER

# Text that used to be corrupted: both placeholder tokens a reader would embed,
# the payload token, script-closing markup and non-ASCII text.
NASTY_TEXT = "\n".join([
    "Русский текст with spaces and ünïcode",
    VERSION_TOKEN,
    FINGERPRINT_TOKEN,
    PAYLOAD_TOKEN,
    "</script><script>alert('x')</script>",
    "<img src=x onerror=alert(1)>",
    "line with \u2028 and \u2029 separators",
    "ampersand & angle < brackets > and slash / end",
])


def make_document(path="docs/architecture.md", text="", **extra):
    document = {"path": path, "text": text}
    document.update(extra)
    return document


def make_index(documents=None, topics=None, dependencies=None, **extra):
    index = {"documents": documents if documents is not None else [make_document()]}
    if topics is not None:
        index["topics"] = topics
    if dependencies is not None:
        index["dependencies"] = dependencies
    index.update(extra)
    return index


def make_report(errors=None, warnings=None, info=None, **extra):
    report = {}
    if errors is not None:
        report["errors"] = errors
    if warnings is not None:
        report["warnings"] = warnings
    if info is not None:
        report["info"] = info
    report.update(extra)
    return report


def embedded_payload(html):
    match = PAYLOAD_RE.search(html)
    if match is None:
        raise AssertionError("the rendered HTML has no documentation-graph-data script")
    return match.group(0), match.group(1), json.loads(match.group(1))


class PlaceholderIsolationTests(unittest.TestCase):
    """The renderer must never rewrite text that came from a document."""

    def test_placeholder_tokens_in_document_text_survive_json_parse(self):
        index = make_index([make_document(text=NASTY_TEXT)])
        html = RENDERER.render_graph(index, make_report())

        _block, raw_json, payload = embedded_payload(html)
        self.assertEqual(payload["index"]["documents"][0]["text"], NASTY_TEXT)

        # Each placeholder token reaches the artifact exactly once, from the
        # document text; the template's own occurrences were filled instead.
        for token in (VERSION_TOKEN, FINGERPRINT_TOKEN, PAYLOAD_TOKEN):
            self.assertEqual(
                html.count(token),
                1,
                "token %r should survive only inside the embedded document" % token,
            )
        # The one surviving occurrence is the document's own copy: the JSON
        # parses back to the untouched text.
        self.assertIn(VERSION_TOKEN, raw_json)
        self.assertIn(FINGERPRINT_TOKEN, raw_json)

    def test_minimal_document_containing_both_tokens_round_trips(self):
        text = VERSION_TOKEN + " " + FINGERPRINT_TOKEN
        html = RENDERER.render_graph(make_index([make_document(text=text)]), make_report())
        payload = embedded_payload(html)[2]
        self.assertEqual(payload["index"]["documents"][0]["text"], text)

    def test_placeholder_tokens_in_topics_and_problems_survive(self):
        topics = [{
            "id": "docs.topic",
            "purpose": "Keeps " + VERSION_TOKEN + " as text",
            "owner": "docs/architecture.md#" + FINGERPRINT_TOKEN,
            "read_when": PAYLOAD_TOKEN,
        }]
        problems = [{
            "code": "anchor_missing",
            "message": FINGERPRINT_TOKEN + " is missing",
            "file": "docs/architecture.md",
            "line": 3,
            "target": VERSION_TOKEN,
        }]
        index = make_index([make_document(text="body " + PAYLOAD_TOKEN)], topics=topics)

        payload = embedded_payload(RENDERER.render_graph(index, make_report(errors=problems)))[2]
        self.assertEqual(payload["index"]["topics"][0]["read_when"], PAYLOAD_TOKEN)
        self.assertEqual(
            payload["index"]["topics"][0]["purpose"],
            "Keeps " + VERSION_TOKEN + " as text",
        )
        self.assertEqual(
            payload["report"]["errors"][0]["message"],
            FINGERPRINT_TOKEN + " is missing",
        )

    def test_meta_tags_are_not_left_as_placeholders(self):
        html = RENDERER.render_graph(make_index([make_document(text=NASTY_TEXT)]), make_report())
        fingerprint = META_FINGERPRINT_RE.search(html)
        version = META_VERSION_RE.search(html)
        self.assertIsNotNone(fingerprint)
        self.assertIsNotNone(version)
        self.assertEqual(fingerprint.group(1), RENDERER.renderer_fingerprint())
        self.assertEqual(version.group(1), RENDERER.RENDERER_VERSION)
        self.assertNotIn(VERSION_TOKEN, fingerprint.group(0))
        self.assertNotIn(FINGERPRINT_TOKEN, version.group(0))


class EscapeSafetyTests(unittest.TestCase):
    def test_document_text_cannot_close_the_script_element(self):
        html = RENDERER.render_graph(make_index([make_document(text=NASTY_TEXT)]), make_report())
        block, raw_json, _payload = embedded_payload(html)
        self.assertNotIn("<", raw_json)
        self.assertNotIn(">", raw_json)
        self.assertNotIn("</script>", block[: -len("</script>")])
        self.assertEqual(html.count("</script>"), 2)
        self.assertNotIn("<script>alert('x')</script>", html)
        self.assertNotIn("<img src=x onerror", html)

    def test_version_and_fingerprint_values_are_real(self):
        html = RENDERER.render_graph(make_index(), make_report())
        _block, _raw, payload = embedded_payload(html)
        self.assertEqual(payload["renderer_version"], RENDERER.RENDERER_VERSION)
        fingerprint = payload["renderer_fingerprint"]
        self.assertTrue(fingerprint.startswith("sha256:"))
        self.assertEqual(len(fingerprint), len("sha256:") + 64)
        self.assertEqual(fingerprint, RENDERER.renderer_fingerprint())

    def test_escape_helper_is_reversible(self):
        payload = json.dumps({"note": "a/b&c<d>e"}, ensure_ascii=False)
        escaped = RENDERER._escape_payload_json(payload)
        self.assertNotIn("<", escaped)
        self.assertNotIn(">", escaped)
        self.assertNotIn("&", escaped)
        self.assertEqual(json.loads(escaped), {"note": "a/b&c<d>e"})


class PayloadShapeTests(unittest.TestCase):
    def test_render_is_deterministic(self):
        index = make_index([make_document(text="body")])
        report = make_report(info=[{"code": "section_unlinked", "message": "n/a"}])
        self.assertEqual(RENDERER.render_graph(index, report), RENDERER.render_graph(index, report))

    def test_payload_carries_index_report_and_renderer_identity(self):
        index = make_index([make_document(text="body")])
        payload = embedded_payload(RENDERER.render_graph(index, make_report()))[2]
        self.assertEqual(
            sorted(payload),
            ["index", "renderer_fingerprint", "renderer_version", "report"],
        )
        self.assertEqual(payload["index"], index)
        self.assertEqual(payload["report"], make_report())

    def test_public_api_matches_the_plan(self):
        for name in (
            "render_graph",
            "validate_payload",
            "renderer_fingerprint",
            "fingerprint_sources",
            "load_template",
        ):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(RENDERER, name)))
        self.assertEqual(RENDERER.SCRIPT_ID, "documentation-graph-data")
        self.assertEqual(RENDERER.TEMPLATE_PATH, TEMPLATE_PATH)


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, index, report=None):
        with self.assertRaises(ValueError):
            RENDERER.render_graph(index, make_report() if report is None else report)

    def test_index_and_report_must_be_mappings(self):
        self.assert_invalid([], {})
        self.assert_invalid({}, [])

    def test_documents_are_required_and_must_be_a_list(self):
        self.assert_invalid({}, {})
        self.assert_invalid({"documents": {}}, {})

    def test_every_document_needs_path_and_text(self):
        self.assert_invalid({"documents": [{"path": "docs/a.md"}]}, {})
        self.assert_invalid({"documents": [{"text": "body"}]}, {})
        self.assert_invalid({"documents": [{"path": "docs/a.md", "text": 5}]}, {})
        self.assert_invalid({"documents": ["docs/a.md"]}, {})

    def test_paths_must_stay_inside_the_project_root(self):
        for bad in (
            "/etc/passwd",
            "../outside.md",
            "docs/../outside.md",
            "docs\\a.md",
            "docs//a.md",
            "C:/drive.md",
            5,
        ):
            with self.subTest(path=bad):
                self.assert_invalid({"documents": [{"path": bad, "text": "body"}]}, {})

    def test_empty_documents_list_is_valid(self):
        self.assertIn(RENDERER.SCRIPT_ID, RENDERER.render_graph({"documents": []}, {}))

    def test_headings_and_links_must_be_lists(self):
        self.assert_invalid({"documents": [make_document(headings={})]}, {})
        self.assert_invalid({"documents": [make_document(links="nope")]}, {})

    def test_topics_need_ids(self):
        self.assert_invalid({"documents": [make_document()], "topics": [{"purpose": "x"}]}, {})
        self.assert_invalid({"documents": [make_document()], "topics": "nope"}, {})

    def test_dependencies_need_topics_and_list_targets(self):
        base = {"documents": [make_document()]}
        self.assert_invalid(dict(base, dependencies=[{"depends_on": ["a"]}]), {})
        self.assert_invalid(dict(base, dependencies=[{"topic": "a", "depends_on": "b"}]), {})
        self.assert_invalid(dict(base, dependencies=[{"topic": "a", "depends_on": [""]}]), {})

    def test_problem_entries_need_a_code(self):
        base = {"documents": [make_document()]}
        self.assert_invalid(base, make_report(errors=[{"message": "x"}]))
        self.assert_invalid(base, make_report(warnings="nope"))
        self.assert_invalid(base, make_report(info=[1]))

    def test_fingerprint_sources_is_pure_and_sensitive(self):
        first = RENDERER.fingerprint_sources(b"module", b"template")
        self.assertEqual(first, RENDERER.fingerprint_sources(b"module", b"template"))
        self.assertNotEqual(first, RENDERER.fingerprint_sources(b"module2", b"template"))
        self.assertNotEqual(first, RENDERER.fingerprint_sources(b"module", b"template2"))
        with self.assertRaises(TypeError):
            RENDERER.fingerprint_sources("module", b"template")


class TemplateContractTests(unittest.TestCase):
    def setUp(self):
        self.template = RENDERER.load_template()

    def test_template_has_exactly_one_of_each_placeholder(self):
        for placeholder in (PAYLOAD_TOKEN, VERSION_TOKEN, FINGERPRINT_TOKEN):
            with self.subTest(placeholder=placeholder):
                self.assertEqual(self.template.count(placeholder), 1)

    def test_template_declares_the_payload_script(self):
        self.assertIn('id="' + RENDERER.SCRIPT_ID + '"', self.template)
        self.assertEqual(RENDERER.TEMPLATE_PATH, TEMPLATE_PATH)
        self.assertTrue(TEMPLATE_PATH.is_file())

    def test_required_controls_are_present(self):
        for control in (
            'id="search"',
            'id="area-filter"',
            'id="tree"',
            'id="graph"',
            'id="problems"',
            'id="details"',
            'id="problems-only"',
            'id="show-connections"',
            'id="zoom-in"',
            'id="zoom-out"',
            'id="zoom-fit"',
            'id="zoom-reset"',
            'id="layout-reset"',
            'id="rel-routes_to"',
            'id="rel-owns_topic"',
            'id="rel-references"',
            'id="rel-depends_on"',
            'role="tree"',
            'aria-expanded',
            'aria-selected',
        ):
            with self.subTest(control=control):
                self.assertIn(control, self.template)

    def test_key_behaviours_are_implemented(self):
        for behaviour in (
            "function computeLayout",
            "function renderGraph",
            "function fitView",
            "function zoomBy",
            "function centerOn",
            "function beginNodeDrag",
            "function restoreSavedLayout",
            "function saveLayout",
            "function resetLayout",
            "function applyGraphFilters",
            "function applyLabelDetail",
            "function buildTree",
            "function treeKeydown",
            "function sourceBlock",
            "function appendAddressTools",
            "function jumpToProblem",
            "function problemButton",
            "function relationList",
            "function safeRelativePath",
            "function shellQuote",
            "function shellPath",
            "function readCommand",
            "function headingAliases",
            "function headingMatches",
            "function preambleHeading",
            "function resolveSection",
            "function appendResolutionNotice",
            "createElementNS",
            "pointerdown",
            "pointermove",
            "wheel",
            "localStorage",
        ):
            with self.subTest(behaviour=behaviour):
                self.assertIn(behaviour, self.template)

    def test_no_second_slug_algorithm_in_the_template(self):
        # Anchor resolution must come from the index, never from a local slug
        # mimic that silently picks the first similar heading.
        self.assertNotIn("function slug(", self.template)
        self.assertNotIn("anchor_aliases", self.template)
        self.assertIn("aliases", self.template)

    def test_template_is_offline_and_escaping_is_text_only(self):
        self.assertIsNone(re.search(r'(?:src|href)\s*=\s*["\']https?://', self.template))
        self.assertNotIn("@import", self.template)
        self.assertNotIn("fetch(", self.template)
        self.assertNotIn("XMLHttpRequest", self.template)
        self.assertNotIn("innerHTML", self.template)
        self.assertNotIn("document.write", self.template)
        self.assertIn("textContent", self.template)
        self.assertEqual(self.template.count("http://"), 1)  # SVG namespace only

    def test_layout_is_responsive_and_keyboard_reachable(self):
        self.assertIn("@media (max-width: 1080px)", self.template)
        self.assertIn("prefers-color-scheme", self.template)
        self.assertIn("tabindex", self.template)
        self.assertIn(":focus-visible", self.template)


class NodeRoundTripTests(unittest.TestCase):
    """The same round-trip through a real JavaScript engine, when available."""

    def setUp(self):
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("node is not installed")

    def test_json_parse_returns_the_original_document_text(self):
        html = RENDERER.render_graph(make_index([make_document(text=NASTY_TEXT)]), make_report())
        with tempfile.TemporaryDirectory() as temp_name:
            page = Path(temp_name) / "documentation-graph.html"
            page.write_text(html, encoding="utf-8")
            script = Path(temp_name) / "roundtrip.js"
            script.write_text(ROUNDTRIP_JS, encoding="utf-8")
            proc = subprocess.run(
                [self.node, str(script), str(page)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        decoded = base64.b64decode(proc.stdout.strip()).decode("utf-8")
        self.assertEqual(decoded, NASTY_TEXT)

    def test_packaged_script_parses_as_javascript(self):
        html = RENDERER.render_graph(make_index([make_document(text="body")]), make_report())
        match = PLAIN_SCRIPT_RE.search(html)
        self.assertIsNotNone(match, "the template must keep its main script element")
        with tempfile.TemporaryDirectory() as temp_name:
            script = Path(temp_name) / "graph.js"
            script.write_text(match.group(1), encoding="utf-8")
            proc = subprocess.run(
                [self.node, "--check", str(script)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)


def extract_function(source, name):
    """Return the source text of ``function name(...) {...}`` from the template.

    The template keeps its helpers as plain top-level functions inside one IIFE.
    Extracting them lets the tests execute the shipped source instead of a copy,
    and the assertions below fail loudly if the template is refactored.
    """
    marker = "function " + name + "("
    start = source.find(marker)
    if start == -1:
        raise AssertionError("template no longer defines function %s" % name)
    opening = source.find("{", start)
    if opening == -1:
        raise AssertionError("function %s has no body" % name)
    depth = 0
    for position in range(opening, len(source)):
        char = source[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise AssertionError("unbalanced function %s" % name)


# Spaces, Unicode outside the Cyrillic block, shell metacharacters, quoting,
# option injection and a newline: every one of these must stay one literal argv
# word and must never run as a command.
NASTY_PATHS = [
    "docs/architecture.md",
    "docs/a b.md",
    "docs/Мои документы/Схема.md",
    "docs/日本/読む.md",
    "docs/it's.md",
    "docs/x;touch pwned.md",
    "docs/$(touch pwned).md",
    "docs/`touch pwned`.md",
    "docs/two\nlines.md",
    "docs/tab\tname.md",
    "docs/quote'and$(x)`y`.md",
    "-n.md",
]

FILE_BODY = "line one\nline two\nline three\n"


class SourceFunctionTests(unittest.TestCase):
    """Execute the template's own pure helpers with node."""

    def setUp(self):
        self.template = RENDERER.load_template()
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("node is not installed")

    def run_harness(self, function_names, body, argument):
        source = "\n".join(extract_function(self.template, name) for name in function_names)
        with tempfile.TemporaryDirectory() as temp_name:
            script = Path(temp_name) / "harness.js"
            script.write_text(source + "\n" + body, encoding="utf-8")
            proc = subprocess.run(
                [self.node, str(script), json.dumps(argument)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def read_commands(self, start, end):
        return self.run_harness(
            ["asText", "shellQuote", "shellPath", "lineNumber", "readCommand"],
            "const paths = JSON.parse(process.argv[2]);\n"
            "process.stdout.write(JSON.stringify(paths.map(function (p) {"
            " return readCommand(p, %s, %s); })));\n" % (json.dumps(start), json.dumps(end)),
            NASTY_PATHS,
        )

    def test_read_command_keeps_every_path_a_single_literal_argument(self):
        for command_kind, commands, expected in (
            ("sed", self.read_commands(1, 2), "line one\nline two\n"),
            ("cat", self.read_commands(None, None), FILE_BODY),
        ):
            self.assertEqual(len(commands), len(NASTY_PATHS))
            for path, command in zip(NASTY_PATHS, commands):
                with self.subTest(kind=command_kind, path=path):
                    self.assertIn(" './", command)
                    with tempfile.TemporaryDirectory() as temp_name:
                        workdir = Path(temp_name)
                        target = workdir / path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(FILE_BODY, encoding="utf-8")
                        before = sorted(str(item.relative_to(workdir)) for item in workdir.rglob("*"))
                        proc = subprocess.run(
                            ["sh", "-c", command],
                            cwd=str(workdir),
                            capture_output=True,
                            text=True,
                        )
                        after = sorted(str(item.relative_to(workdir)) for item in workdir.rglob("*"))
                        injected = (workdir / "pwned").exists()
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout, expected)
                    self.assertEqual(before, after)
                    self.assertFalse(injected)

    def test_read_command_neutralises_option_injection(self):
        commands = self.read_commands(1, 2)
        self.assertIn("'./-n.md'", commands[NASTY_PATHS.index("-n.md")])
        self.assertEqual(commands[-1].count("./"), 1)

    def test_safe_relative_path_accepts_normal_unicode_and_space_paths(self):
        accepted = [
            "docs/architecture.md",
            "docs/a b.md",
            "docs/Мои документы/Схема.md",
            "docs/日本/読む.md",
            "docs/it's.md",
            "docs/$(x).md",
            "docs/`x`.md",
            "-n.md",
            "./docs/x.md",
        ]
        rejected = [
            "/abs/x.md",
            "../x.md",
            "docs/../x.md",
            "docs\\x.md",
            "C:/x.md",
            "js:alert(1)",
            "docs//x.md",
            "",
        ]
        results = self.run_harness(
            ["asText", "safeRelativePath"],
            "const paths = JSON.parse(process.argv[2]);\n"
            "process.stdout.write(JSON.stringify(paths.map(safeRelativePath)));\n",
            accepted + rejected,
        )
        self.assertEqual(results[:len(accepted)], [True] * len(accepted))
        self.assertEqual(results[len(accepted):], [False] * len(rejected))

    def test_document_relation_accepts_links_and_rejects_images(self):
        results = self.run_harness(
            ["linkCarriesDocumentRelation"],
            "const links = JSON.parse(process.argv[2]);\n"
            "process.stdout.write(JSON.stringify(links.map(linkCarriesDocumentRelation)));\n",
            [
                {"kind": "link", "resolved": True},
                {"kind": "document", "resolved": True},
                {"resolved": True},
                {"kind": "image", "resolved": True},
                {"kind": "link", "resolved": False},
                {"kind": "link", "resolved": True, "can_own": False},
            ],
        )
        self.assertEqual(results, [True, True, True, False, False, False])

    def test_problem_lookup_uses_topic_id_from_section(self):
        result = self.run_harness(
            ["asText", "splitAddress", "lookupNode"],
            "const model = {docsByPath: {}, topicsById: {'topic.without-owner': {}}};\n"
            "const problem = JSON.parse(process.argv[2]);\n"
            "process.stdout.write(JSON.stringify(lookupNode("
            " problem.file, problem.target, problem.section)));\n",
            {"file": None, "target": None, "section": "topic.without-owner"},
        )
        self.assertEqual(result, "topic:topic.without-owner")

    def resolve(self, doc, problems):
        return self.run_harness(
            ["asText", "lineNumber", "headingAliases", "headingMatches",
             "documentLineCount", "preambleHeading", "resolveSection"],
            "const payload = JSON.parse(process.argv[2]);\n"
            "const out = payload.problems.map(function (problem) {"
            " return resolveSection(payload.doc, problem); });\n"
            "process.stdout.write(JSON.stringify(out.map(function (r) {"
            " return {reason: r.reason, heading: r.heading, candidates: r.candidates}; })));\n",
            {"doc": doc, "problems": problems},
        )

    def setUpResolverDoc(self):
        return {
            "path": "docs/architecture.md",
            "text": "preamble\n# One\nbody\n## Two\nmore\n### Three\nrest\n",
            "preambleAnchors": ["intro"],
            "headings": [
                {"text": "One", "anchor": "one", "level": 1, "line_start": 2, "line_end": 4,
                 "aliases": ["first"]},
                {"text": "Two", "anchor": "two", "level": 2, "line_start": 4, "line_end": 6,
                 "aliases": ["second"]},
                {"text": "Three", "anchor": "three", "level": 3, "line_start": 6, "line_end": 8,
                 "aliases": ["two"]},
            ],
        }

    def test_resolve_section_uses_anchor_alias_and_text_without_guessing(self):
        doc = self.setUpResolverDoc()
        results = self.resolve(doc, [
            {"section": "one"},
            {"section": "first"},
            {"section": "One"},
            {"section": "two"},
            {"section": "missing", "line": 5},
            {"section": "missing", "line": 100},
            {"section": "intro"},
            {"section": ""},
        ])
        self.assertEqual(results[0]["heading"]["anchor"], "one")
        self.assertEqual(results[1]["heading"]["anchor"], "one")
        self.assertEqual(results[2]["heading"]["anchor"], "one")
        # "two" is heading 2's anchor and heading 3's alias: a collision, not a
        # silent first match.
        self.assertIsNone(results[3]["heading"])
        self.assertEqual(results[3]["reason"], "ambiguous")
        self.assertEqual(len(results[3]["candidates"]), 2)
        # The index's own line range is authoritative for a line-only report.
        self.assertEqual(results[4]["heading"]["anchor"], "two")
        self.assertEqual(results[4]["reason"], "line")
        self.assertIsNone(results[5]["heading"])
        self.assertEqual(results[5]["reason"], "not_found")
        # An explicit anchor before the first heading belongs to the preamble.
        self.assertEqual(results[6]["heading"]["anchor"], "intro")
        self.assertEqual(results[6]["heading"]["line_start"], 1)
        self.assertEqual(results[6]["heading"]["line_end"], 1)
        self.assertEqual(results[7]["reason"], "no_section_name")

    def test_resolve_section_reports_repeated_heading_text_as_ambiguous(self):
        doc = self.setUpResolverDoc()
        doc["headings"].append(
            {"text": "Two", "anchor": "two-1", "level": 2, "line_start": 9, "line_end": 10,
             "aliases": []}
        )
        results = self.resolve(doc, [{"section": "Two"}])
        self.assertIsNone(results[0]["heading"])
        self.assertEqual(results[0]["reason"], "ambiguous")
        self.assertEqual(len(results[0]["candidates"]), 2)

    def test_preamble_anchors_are_read_from_the_index_key(self):
        doc = self.setUpResolverDoc()
        doc.pop("preambleAnchors")
        doc["preamble_anchors"] = ["intro"]
        results = self.resolve(doc, [{"section": "intro"}])
        self.assertEqual(results[0]["heading"]["anchor"], "intro")


ROUNDTRIP_JS = r"""
'use strict';
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const match = html.match(
  /<script type="application\/json" id="documentation-graph-data">([\s\S]*?)<\/script>/
);
if (!match) {
  console.error('no embedded graph payload found');
  process.exit(2);
}
let data;
try {
  data = JSON.parse(match[1]);
} catch (err) {
  console.error('JSON.parse failed: ' + err.message);
  process.exit(3);
}
process.stdout.write(Buffer.from(data.index.documents[0].text, 'utf8').toString('base64'));
"""


if __name__ == "__main__":
    unittest.main()
