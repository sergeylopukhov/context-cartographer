#!/usr/bin/env python3
"""Render the self-contained offline documentation graph HTML.

Contract (implementation plan 03-04, references/documentation-format.md):

    render_graph(index: dict, report: dict) -> str

Pure function. It validates the payload, loads the packaged template from
``assets/documentation-graph.html`` next to this module (never from the working
directory), embeds the graph data in one escaped JSON script element, and
returns the complete HTML document as a ``str``. It never writes files, never
reads the working directory, never touches the network and never prints.

Writing the file belongs to the caller. This module deliberately contains no
file writing, no document fingerprinting and no re-read logic, so a CLI can
implement atomic writes and no-op detection without fighting a second writer
here. Write the returned string as UTF-8.

Freshness
---------
Two independent things make an existing HTML stale:

* the documents changed - detected with the index/report ``source_fingerprint``,
  which is data-owned and produced elsewhere;
* the renderer changed - detected with :func:`renderer_fingerprint`, a
  ``sha256:`` digest over this module's source plus the packaged template, and
  with :data:`RENDERER_VERSION` for a human-readable comparison.

Both values are written into the artifact, so a writer can read the previous
file instead of keeping sidecar state. The stable, parseable locations are:

* ``<meta name="context-cartographer-renderer" content="<fingerprint>">``
* ``<meta name="context-cartographer-renderer-version" content="<version>">``
* ``renderer_version`` and ``renderer_fingerprint`` next to ``index`` and
  ``report`` inside the ``documentation-graph-data`` JSON payload.

The payload extension is additive: ``index`` and ``report`` keep the shape from
``references/documentation-format.md``, and the module owns the two added keys.

Example
-------
>>> html = render_graph(index_dict, report_dict)                 # doctest: +SKIP
>>> Path(output_path).write_text(html, encoding="utf-8")         # doctest: +SKIP

Validation raises :class:`ValueError` with a precise message instead of
producing HTML that silently loses data:

* ``index`` and ``report`` must be mappings;
* ``index["documents"]`` must be a list of mappings (empty is valid);
* every document needs a project-root-relative ``path`` and a ``text`` string,
  because the renderer never reads files itself;
* ``path`` must not be absolute and must not escape the project root.

Untrusted text is escaped for the ``application/json`` script context
(``<``, ``>``, ``&``, ``/``, U+2028, U+2029), and the template renders every
label, path and source line with ``textContent``, never ``innerHTML``.

Placeholders are filled in one pass over the packaged template, and the graph
JSON is inserted last. A document whose text happens to contain a placeholder
token therefore survives verbatim inside the embedded JSON instead of being
rewritten by a later ``str.replace`` over the whole document. The template and
the recorded fingerprint come from one byte snapshot, so the artifact can never
record a fingerprint that does not describe the HTML next to it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


__all__ = [
    "PAYLOAD_PLACEHOLDER",
    "RENDERER_FINGERPRINT_PLACEHOLDER",
    "RENDERER_VERSION",
    "RENDERER_VERSION_PLACEHOLDER",
    "SCRIPT_ID",
    "TEMPLATE_PATH",
    "fingerprint_sources",
    "load_template",
    "render_graph",
    "renderer_fingerprint",
    "validate_payload",
]

SCRIPT_ID = "documentation-graph-data"
TEMPLATE_NAME = "documentation-graph.html"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / TEMPLATE_NAME
MODULE_PATH = Path(__file__).resolve()
PAYLOAD_PLACEHOLDER = "__CONTEXT_CARTOGRAPHER_PAYLOAD__"
RENDERER_VERSION_PLACEHOLDER = "__CONTEXT_CARTOGRAPHER_RENDERER_VERSION__"
RENDERER_FINGERPRINT_PLACEHOLDER = "__CONTEXT_CARTOGRAPHER_RENDERER_FINGERPRINT__"
RENDERER_VERSION = "2"
FINGERPRINT_PREFIX = "sha256:"
FINGERPRINT_DOMAIN = b"context-cartographer/documentation-html/v1\n"
MAX_PATH_SEGMENT = 255

_PLACEHOLDER_PATTERN = re.compile(
    "|".join(
        re.escape(placeholder)
        for placeholder in (
            PAYLOAD_PLACEHOLDER,
            RENDERER_VERSION_PLACEHOLDER,
            RENDERER_FINGERPRINT_PLACEHOLDER,
        )
    )
)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:  # pragma: no cover - depends on the installed package
        raise ValueError(f"{label} {path} could not be read: {exc}") from exc


def fingerprint_sources(module_bytes: bytes, template_bytes: bytes) -> str:
    """Return the stable renderer fingerprint for the given source bytes.

    Pure and deterministic. Callers can use it to prove what a renderer build
    depends on without touching the filesystem.
    """
    if not isinstance(module_bytes, bytes) or not isinstance(template_bytes, bytes):
        raise TypeError("fingerprint_sources expects bytes for both arguments")
    digest = hashlib.sha256()
    digest.update(FINGERPRINT_DOMAIN)
    digest.update(b"module\n")
    digest.update(module_bytes)
    digest.update(b"\ntemplate\n")
    digest.update(template_bytes)
    return FINGERPRINT_PREFIX + digest.hexdigest()


def renderer_fingerprint() -> str:
    """Return the fingerprint of the packaged renderer (module plus template)."""
    return fingerprint_sources(
        _read_bytes(MODULE_PATH, "renderer module"),
        _read_bytes(TEMPLATE_PATH, "renderer template"),
    )


def _clean_path(raw: object, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{where}: path must be a non-empty string")
    path = raw.strip()
    if "\\" in path:
        raise ValueError(f"{where}: path must use forward slashes, got {path!r}")
    if path.startswith("/"):
        raise ValueError(
            f"{where}: path must be project-root-relative, got absolute path {path!r}"
        )
    parts = path.split("/")
    if any(part == ".." for part in parts):
        raise ValueError(f"{where}: path must stay inside the project root, got {path!r}")
    if any(part == "" for part in parts):
        raise ValueError(f"{where}: path must be normalized, got {path!r}")
    if any(len(part) > MAX_PATH_SEGMENT for part in parts):
        raise ValueError(f"{where}: path segment is longer than {MAX_PATH_SEGMENT} characters")
    if ":" in parts[0]:
        raise ValueError(f"{where}: path must not name a drive or scheme, got {path!r}")
    return path


def _check_problem_list(items: object, label: str) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise ValueError(f"report.{label} must be a list")
    for index, item in enumerate(items):
        where = f"report.{label}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be an object")
        code = item.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"{where}: code must be a non-empty string")


def _check_topics(raw_topics: object) -> None:
    if raw_topics is None:
        return
    if not isinstance(raw_topics, list):
        raise ValueError("index.topics must be a list")
    for index, topic in enumerate(raw_topics):
        where = f"index.topics[{index}]"
        if not isinstance(topic, dict):
            raise ValueError(f"{where} must be an object")
        topic_id = topic.get("id")
        if not isinstance(topic_id, str) or not topic_id.strip():
            raise ValueError(f"{where}: id must be a non-empty string")


def _check_dependencies(raw_dependencies: object) -> None:
    if raw_dependencies is None:
        return
    if not isinstance(raw_dependencies, list):
        raise ValueError("index.dependencies must be a list")
    for index, dependency in enumerate(raw_dependencies):
        where = f"index.dependencies[{index}]"
        if not isinstance(dependency, dict):
            raise ValueError(f"{where} must be an object")
        topic = dependency.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"{where}: topic must be a non-empty string")
        depends_on = dependency.get("depends_on")
        if depends_on is None:
            continue
        if not isinstance(depends_on, list):
            raise ValueError(f"{where}: depends_on must be a list")
        for position, target in enumerate(depends_on):
            if not isinstance(target, str) or not target.strip():
                raise ValueError(
                    f"{where}.depends_on[{position}]: must be a non-empty topic id string"
                )


def validate_payload(index: object, report: object) -> None:
    """Raise :class:`ValueError` unless the graph payload is renderable.

    Exporting the check keeps the CLI and the tests on one definition of a valid
    payload. It never reads files and never rewrites the payload.
    """
    if not isinstance(index, dict):
        raise ValueError(f"index must be a mapping, got {type(index).__name__}")
    if not isinstance(report, dict):
        raise ValueError(f"report must be a mapping, got {type(report).__name__}")

    if "documents" not in index:
        raise ValueError("index.documents is required")
    documents = index["documents"]
    if not isinstance(documents, list):
        raise ValueError(f"index.documents must be a list, got {type(documents).__name__}")
    for position, document in enumerate(documents):
        where = f"index.documents[{position}]"
        if not isinstance(document, dict):
            raise ValueError(f"{where} must be a mapping, got {type(document).__name__}")
        path = _clean_path(document.get("path"), where)
        if "text" not in document:
            raise ValueError(
                f"{where} ({path}): text is required; the renderer never reads files"
            )
        text = document["text"]
        if not isinstance(text, str):
            raise ValueError(
                f"{where} ({path}): text must be a string, got {type(text).__name__}"
            )
        headings = document.get("headings")
        if headings is not None and not isinstance(headings, list):
            raise ValueError(f"{where} ({path}): headings must be a list")
        links = document.get("links")
        if links is not None and not isinstance(links, list):
            raise ValueError(f"{where} ({path}): links must be a list")

    _check_topics(index.get("topics"))
    _check_dependencies(index.get("dependencies"))
    _check_problem_list(report.get("errors"), "errors")
    _check_problem_list(report.get("warnings"), "warnings")
    _check_problem_list(report.get("info"), "info")


def _escape_payload_json(payload: str) -> str:
    """Escape a JSON string so it is inert inside an HTML script element.

    ``<``, ``>``, ``&`` and ``/`` become JSON ``\\u`` escapes, which keeps the
    value identical after ``JSON.parse`` while removing any chance of closing
    the script element or opening a tag. U+2028 and U+2029 are escaped too.
    """
    replacements = (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("/", "\\u002f"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    )
    for needle, escape in replacements:
        payload = payload.replace(needle, escape)
    return payload


def _fill_template(template: str, replacements: dict[str, str]) -> str:
    """Fill every renderer placeholder in ``template`` in a single pass.

    ``re.sub`` scans the original template and never re-scans replacement text,
    so a document whose text contains one of the placeholder tokens is copied
    into the artifact unchanged. The template is the only input that can carry
    placeholders; embedded user data never is.
    """
    def substitute(match: re.Match[str]) -> str:
        return replacements[match.group(0)]

    return _PLACEHOLDER_PATTERN.sub(substitute, template)


def _decode_template(template_bytes: bytes) -> str:
    try:
        return template_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - packaged asset
        raise ValueError(
            f"renderer template {TEMPLATE_PATH} is not valid UTF-8: {exc}"
        ) from exc


def load_template() -> str:
    """Return the packaged HTML template as text."""
    return _decode_template(_read_bytes(TEMPLATE_PATH, "renderer template"))


def _renderer_snapshot() -> tuple[str, str]:
    """Return ``(template_text, fingerprint)`` from one consistent read.

    Reading the template and hashing it in separate steps would let a file edit
    during rendering produce an artifact whose recorded fingerprint does not
    describe the HTML next to it. Both values come from the same byte snapshot.
    """
    module_bytes = _read_bytes(MODULE_PATH, "renderer module")
    template_bytes = _read_bytes(TEMPLATE_PATH, "renderer template")
    return _decode_template(template_bytes), fingerprint_sources(module_bytes, template_bytes)


def render_graph(index: dict, report: dict) -> str:
    """Return the complete offline HTML graph for ``index`` and ``report``.

    ``index`` must carry ``documents`` with ``path`` and ``text`` per document;
    the caller has already done every file read. The returned string is
    byte-identical for equal inputs, so a writer can skip rewriting an unchanged
    file by comparing content.
    """
    validate_payload(index, report)
    template, fingerprint = _renderer_snapshot()
    for placeholder, label in (
        (PAYLOAD_PLACEHOLDER, "payload"),
        (RENDERER_VERSION_PLACEHOLDER, "renderer version"),
        (RENDERER_FINGERPRINT_PLACEHOLDER, "renderer fingerprint"),
    ):
        if template.count(placeholder) != 1:
            raise ValueError(
                f"renderer template {TEMPLATE_PATH} must contain exactly one {label} placeholder"
            )
    if f'id="{SCRIPT_ID}"' not in template:
        raise ValueError(
            f"renderer template {TEMPLATE_PATH} is missing the {SCRIPT_ID} payload element"
        )

    payload = json.dumps(
        {
            "index": index,
            "renderer_fingerprint": fingerprint,
            "renderer_version": RENDERER_VERSION,
            "report": report,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _fill_template(
        template,
        {
            PAYLOAD_PLACEHOLDER: _escape_payload_json(payload),
            RENDERER_FINGERPRINT_PLACEHOLDER: fingerprint,
            RENDERER_VERSION_PLACEHOLDER: RENDERER_VERSION,
        },
    )
