#!/usr/bin/env python3
"""Documentation graph CLI: check, write, outline, and read exact sections.

The command is a thin orchestration layer over exactly two sibling modules:

* ``documentation_index.py`` builds the shared documentation index and owns the
  single anchor/slug algorithm and the section ranges.
* ``documentation_html.py`` exposes ``render_graph(index, report) -> str`` and
  ``renderer_fingerprint()``; it is a pure renderer and never writes files.

Both are resolved next to this file, so a packaged copy works from any working
directory. A missing or contract-broken helper produces a clean error instead
of an import traceback.

Standard library only. Every path is resolved from ``--root``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path


SCHEMA_VERSION = 1
DEFAULT_MAP_PATH = "docs/architecture.md"
GRAPH_REL_PATH = Path(".context-cartographer") / "documentation-graph.html"
GRAPH_DATA_ID = "documentation-graph-data"

EXIT_OK = 0
EXIT_DOCS = 1
EXIT_USAGE = 2

INDEX_MODULE_FILENAME = "documentation_index.py"
RENDER_MODULE_FILENAME = "documentation_html.py"
REQUIRED_INDEX_API = ("build_index", "fingerprint", "owner_coverage")
REQUIRED_RENDER_API = ("render_graph", "renderer_fingerprint")

# Index issues that already describe a broken link. The report must not repeat
# them as an unresolved root route.
REPORTED_LINK_CODES = {
    "link_target_missing",
    "anchor_missing",
    "anchor_collision",
    "link_outside_root",
    "link_out_of_scope",
    "link_target_directory",
}

# Graph freshness results that are never reported as a healthy graph.
GRAPH_STATUS_ISSUES = {
    "stale": ("graph_stale", f"Graph artifact is not current: {GRAPH_REL_PATH}"),
    "unreadable": ("graph_unreadable", f"Graph artifact could not be read: {GRAPH_REL_PATH}"),
    "unverified": (
        "graph_unverified",
        f"Graph artifact freshness could not be verified: {GRAPH_REL_PATH}",
    ),
}

# Index issue codes that mean a document's structural parse is incomplete. The
# graph CLI never re-parses a document to decide this; it reads the index's
# ``document['parse_complete']`` flag and uses these codes only to explain the
# decision in the failure payload.
PARSE_BLOCKING_ISSUE_CODES = frozenset({
    "document_outside_root",
    "document_unreadable",
    "document_too_large",
    "unsupported_markdown",
})


class GraphError(Exception):
    """A failure that maps to a clean message and an exit code."""

    def __init__(self, code: str, message: str, exit_code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


# --------------------------------------------------------------------------
# Helper resolution
# --------------------------------------------------------------------------


def _load_module_from_path(path: Path, name: str):
    if not path.is_file():
        raise GraphError(
            "helper_unavailable",
            f"Helper module not found: {path}",
            EXIT_USAGE,
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GraphError(
            "helper_unavailable",
            f"Helper module could not be loaded: {path}",
            EXIT_USAGE,
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - defensive
        raise GraphError(
            "helper_load_failed",
            f"Helper module failed to load: {path}: {exc}",
            EXIT_USAGE,
        ) from exc
    return module


def _require_api(module, names, path: Path, label: str) -> None:
    missing = [name for name in names if not callable(getattr(module, name, None))]
    if missing:
        raise GraphError(
            f"{label}_contract_mismatch",
            f"{label} helper {path} is missing: {', '.join(missing)}",
            EXIT_USAGE,
        )


def load_index_module():
    path = Path(__file__).resolve().with_name(INDEX_MODULE_FILENAME)
    module = _load_module_from_path(path, "context_cartographer_documentation_index")
    _require_api(module, REQUIRED_INDEX_API, path, "index")
    return module


def load_render_module():
    path = Path(__file__).resolve().with_name(RENDER_MODULE_FILENAME)
    if not path.is_file():
        raise GraphError(
            "renderer_unavailable",
            f"Graph renderer not found: {path}",
            EXIT_USAGE,
        )
    module = _load_module_from_path(path, "context_cartographer_graph_renderer")
    _require_api(module, REQUIRED_RENDER_API, path, "renderer")
    return module


def renderer_identity(module) -> str:
    """Return the renderer fingerprint over its module and packaged asset.

    A renderer that cannot report a fingerprint cannot be verified. The caller
    must treat that as an error instead of falling back to a version string or
    reporting the artifact as fresh.
    """

    fingerprint_fn = getattr(module, "renderer_fingerprint", None)
    if not callable(fingerprint_fn):
        raise GraphError(
            "renderer_contract_mismatch",
            "Graph renderer has no renderer_fingerprint()",
            EXIT_USAGE,
        )
    try:
        fingerprint = fingerprint_fn()
    except Exception as exc:
        raise GraphError(
            "renderer_fingerprint_failed",
            f"Graph renderer could not fingerprint itself: {exc}",
            EXIT_USAGE,
        ) from exc
    if not isinstance(fingerprint, str) or not fingerprint:
        raise GraphError(
            "renderer_fingerprint_failed",
            "Graph renderer returned an empty fingerprint",
            EXIT_USAGE,
        )
    return fingerprint


# --------------------------------------------------------------------------
# Index helpers
# --------------------------------------------------------------------------


def build_index(index_module, root: Path, map_path: str, scope=None) -> dict:
    try:
        index = index_module.build_index(str(root), map_path=map_path, scope=scope)
    except GraphError:
        raise
    except FileNotFoundError as exc:
        raise GraphError(
            "map_missing",
            f"Documentation map not found: {exc}",
            EXIT_USAGE,
        ) from exc
    except Exception as exc:
        raise GraphError(
            "index_failed",
            f"Documentation index failed: {exc}",
            EXIT_USAGE,
        ) from exc
    if not isinstance(index, dict):
        raise GraphError(
            "index_failed",
            "Documentation index did not return a mapping",
            EXIT_USAGE,
        )
    return index


def index_fingerprint(index: dict, index_module) -> str:
    """Return the index fingerprint over document text, scope, and inventory."""

    value = index_module.fingerprint(index)
    if not isinstance(value, str) or not value:
        raise GraphError(
            "index_contract_mismatch",
            "documentation index fingerprint() returned no value",
            EXIT_USAGE,
        )
    return value


def owner_coverage(index: dict, index_module) -> str:
    """Return 'evaluated' or 'not_evaluated' for topic ownership coverage.

    Anything other than an explicit 'evaluated' becomes 'not_evaluated', so the
    report can never claim full topic coverage by accident.
    """

    value = index_module.owner_coverage(index)
    return value if value == "evaluated" else "not_evaluated"


def document_by_path(index: dict, rel_path: str) -> dict | None:
    wanted = rel_path.replace("\\", "/").strip()
    for document in index.get("documents", []) or []:
        if str(document.get("path", "")).replace("\\", "/") == wanted:
            return document
    return None


def _rel_key(value) -> str:
    """Normalize a relative path the same way ``document_by_path`` does."""

    return str(value if value is not None else "").replace("\\", "/").strip()


def parse_blockers(index: dict, rel_path: str) -> list[dict]:
    """Return the recorded reasons one document's parse is incomplete.

    The index owns the parse decision through ``document['parse_complete']``;
    this helper only explains it. Known parse-blocking codes are preferred. When
    the index flagged a document incomplete with a code this module does not
    know, every recorded issue for that file is surfaced so the failure is not
    unexplained. When nothing was recorded, a synthetic entry is returned so a
    caller can never fail closed without a reason.
    """

    wanted = _rel_key(rel_path)
    recorded: list[dict] = []
    for entry in index.get("format_issues", []) or []:
        if not isinstance(entry, dict):
            continue
        if _rel_key(entry.get("file")) != wanted:
            continue
        recorded.append({
            "code": str(entry.get("code") or "format_issue"),
            "severity": str(entry.get("severity") or "warning"),
            "line": entry.get("line") if isinstance(entry.get("line"), int) else None,
            "message": str(entry.get("message") or ""),
        })
    blocking = [entry for entry in recorded if entry["code"] in PARSE_BLOCKING_ISSUE_CODES]
    if blocking:
        return blocking
    if recorded:
        return recorded
    return [{
        "code": "parse_incomplete_unreported",
        "severity": "warning",
        "line": None,
        "message": "The index marked this document's parse incomplete without a recorded cause",
    }]


def document_has_parse_blocker(index: dict, rel_path: str) -> bool:
    """Return whether the index recorded a parse-blocking issue for one file."""

    wanted = _rel_key(rel_path)
    for entry in index.get("format_issues", []) or []:
        if not isinstance(entry, dict):
            continue
        if _rel_key(entry.get("file")) != wanted:
            continue
        if str(entry.get("code") or "") in PARSE_BLOCKING_ISSUE_CODES:
            return True
    return False


def document_parse_complete(index: dict, document: dict) -> bool:
    """Return whether the index fully parsed the document.

    A document the index did not fully parse cannot back a reliable outline or
    exact line range. The index's ``parse_complete`` flag is authoritative; a
    known parse-blocking issue recorded for the same file is also treated as
    incomplete, so a partially updated index can never let an unreliable
    address through.
    """

    if not bool(document.get("parse_complete", True)):
        return False
    return not document_has_parse_blocker(index, document.get("path"))


def _parse_incomplete_message(index: dict, document: dict, mode: str) -> tuple[str, list[dict]]:
    path = str(document.get("path") or "")
    blockers = parse_blockers(index, path)
    detail = "; ".join(
        f"{entry['code']}" + (f" line {entry['line']}" if entry["line"] else "")
        for entry in blockers[:3]
    )
    message = f"Document parse is incomplete; {mode} for {path} cannot be trusted"
    if detail:
        message = f"{message} ({detail})"
    return message, blockers


# --------------------------------------------------------------------------
# Issue plumbing
# --------------------------------------------------------------------------


def issue(code: str, message: str, *, severity: str, file=None, line=None,
          section=None, target=None) -> dict:
    return {
        "code": code,
        "severity": severity,
        "file": file,
        "line": line,
        "section": section,
        "target": target,
        "message": message,
    }


def _sort_key(entry: dict):
    return (
        str(entry.get("file") or ""),
        entry.get("line") if isinstance(entry.get("line"), int) else -1,
        str(entry.get("code") or ""),
    )


def _dedupe(entries: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for entry in sorted(entries, key=_sort_key):
        key = (
            entry.get("code"),
            entry.get("file"),
            entry.get("line"),
            entry.get("target"),
            entry.get("message"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def _document_links(document: dict) -> list[dict]:
    """Return only the links that express documentation relations.

    Images are resources: they never route to a document, own a topic, or count
    as an incoming reference, so they are excluded from graph edges.
    """

    return [
        link for link in (document.get("links") or [])
        if str(link.get("kind") or "link") != "image"
    ]


def _resolved_documents(index: dict) -> dict[str, set[str]]:
    """Map each document path to the set of document paths it points at."""

    edges: dict[str, set[str]] = {}
    known = {str(d.get("path", "")) for d in index.get("documents", []) or []}
    for document in index.get("documents", []) or []:
        source = str(document.get("path", ""))
        targets = edges.setdefault(source, set())
        for link in _document_links(document):
            if not link.get("resolved"):
                continue
            target = str(link.get("target") or "")
            if target and target in known and target != source:
                targets.add(target)
    return edges


def _reachable(index: dict) -> set[str]:
    edges = _resolved_documents(index)
    roots = [str(r) for r in (index.get("scope", {}) or {}).get("roots", []) or []]
    seen: set[str] = set()
    stack = [root for root in roots if root in edges or any(
        str(d.get("path", "")) == root for d in index.get("documents", []) or []
    )]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for nxt in edges.get(current, set()):
            if nxt not in seen:
                stack.append(nxt)
    return seen


def _self_edges(edges: dict[str, set[str]]) -> list[str]:
    """Return the nodes that point at themselves in this edge set."""

    return sorted(node for node, targets in edges.items() if node in targets)


def _cycle_groups(edges: dict[str, set[str]]) -> list[list[str]]:
    """Return strongly connected groups of size > 1.

    Iterative Tarjan: a documentation scope can hold thousands of files, and a
    recursive walk overflows on an ordinary long chain of documents. A node that
    points at itself is not a group here; callers decide whether a self
    reference is a prerequisite cycle or an ordinary in-document link.
    """

    index_counter = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    groups: list[list[str]] = []
    # Each frame is (node, iterator over the node's successors).
    work: list[tuple[str, object]] = []

    for start in sorted(edges):
        if start in indices:
            continue
        indices[start] = index_counter
        low[start] = index_counter
        index_counter += 1
        stack.append(start)
        on_stack.add(start)
        work.append((start, iter(sorted(edges.get(start, ())))))
        while work:
            node, successors = work[-1]
            descended = False
            for nxt in successors:
                if nxt not in indices:
                    indices[nxt] = index_counter
                    low[nxt] = index_counter
                    index_counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(edges.get(nxt, ())))))
                    descended = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], indices[nxt])
            if descended:
                continue
            if low[node] == indices[node]:
                group = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    group.append(member)
                    if member == node:
                        break
                if len(group) > 1:
                    groups.append(sorted(group))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return groups


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def build_report(index: dict, *, graph_status: str, require_graph: bool,
                 index_module=None, renderer_available: bool = True) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    info: list[dict] = []
    reported_links: set[tuple[str, object]] = set()
    index_reports_external = False

    for entry in index.get("format_issues", []) or []:
        severity = str(entry.get("severity", "warning"))
        code = str(entry.get("code", "format_issue"))
        normalized = issue(
            code,
            str(entry.get("message", "")),
            severity=severity,
            file=entry.get("file"),
            line=entry.get("line"),
            section=entry.get("section"),
            target=entry.get("target"),
        )
        if code == "external_link_not_fetched":
            index_reports_external = True
        if code in REPORTED_LINK_CODES:
            reported_links.add((str(entry.get("file") or ""), entry.get("line")))
        if severity == "error":
            errors.append(normalized)
        elif severity == "info":
            info.append(normalized)
        else:
            warnings.append(normalized)

    documents = index.get("documents", []) or []
    known_paths = {str(d.get("path", "")) for d in documents}
    reachable = _reachable(index)
    has_incoming: set[str] = set()
    for document in documents:
        for link in _document_links(document):
            if link.get("resolved"):
                has_incoming.add(str(link.get("target") or ""))

    # Topics: identity, owner presence, owner resolution.
    owner_counts: dict[str, int] = {}
    owner_paths: set[str] = set()
    for topic in index.get("topics", []) or []:
        topic_id = str(topic.get("id") or "")
        if topic_id:
            owner_counts[topic_id] = owner_counts.get(topic_id, 0) + 1
        owner_ref = str(topic.get("owner") or "")
        if owner_ref:
            owner_paths.add(owner_ref.split("#", 1)[0])
    for topic in index.get("topics", []) or []:
        topic_id = str(topic.get("id") or "")
        owner = str(topic.get("owner") or "")
        if not topic_id:
            errors.append(issue("topic_without_id", "A topic has no Topic ID", severity="error"))
            continue
        if owner_counts.get(topic_id, 0) > 1:
            errors.append(issue(
                "duplicate_topic_owner",
                f"Topic ID '{topic_id}' is declared more than once",
                severity="error", section=topic_id, target=owner or None,
            ))
        if not owner:
            errors.append(issue(
                "topic_without_owner",
                f"Topic '{topic_id}' has no owner",
                severity="error", section=topic_id,
            ))
            continue
        target_path = owner.split("#", 1)[0]
        if target_path and target_path not in known_paths:
            errors.append(issue(
                "topic_owner_unresolved",
                f"Owner of topic '{topic_id}' is not an in-scope document: {owner}",
                severity="error", section=topic_id, target=owner,
            ))
        elif target_path and target_path not in reachable:
            errors.append(issue(
                "owner_unreachable",
                f"Owner document of topic '{topic_id}' is not reachable from a root: {target_path}",
                severity="error", file=target_path, section=topic_id, target=owner,
            ))

    # Explicit dependencies: unknown targets and prerequisite cycles.
    topic_ids = {str(t.get("id") or "") for t in index.get("topics", []) or []}
    dependency_edges: dict[str, set[str]] = {}
    for dependency in index.get("dependencies", []) or []:
        source = str(dependency.get("topic") or "")
        targets = dependency.get("depends_on") or []
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            target = str(target)
            if source and source not in topic_ids:
                errors.append(issue(
                    "dependency_unknown_topic",
                    f"Dependency source '{source}' is not a declared topic",
                    severity="error", section=source or None, target=target or None,
                ))
            if target and target not in topic_ids:
                errors.append(issue(
                    "dependency_unknown_topic",
                    f"Dependency target '{target}' is not a declared topic",
                    severity="error", section=source or None, target=target,
                ))
            if source and target:
                dependency_edges.setdefault(source, set()).add(target)
    for node in _self_edges(dependency_edges):
        warnings.append(issue(
            "prerequisite_cycle",
            f"Explicit prerequisite cycle: {node} -> {node}",
            severity="warning", section=node,
        ))
    for group in _cycle_groups(dependency_edges):
        warnings.append(issue(
            "prerequisite_cycle",
            "Explicit prerequisite cycle: " + " -> ".join(group),
            severity="warning", section=", ".join(group),
        ))

    # Required routes: a root that points at an unresolved local target.
    roots = [str(r) for r in (index.get("scope", {}) or {}).get("roots", []) or []]
    for document in documents:
        path = str(document.get("path", ""))
        if path not in roots:
            continue
        for link in _document_links(document):
            if link.get("resolved"):
                continue
            if (path, link.get("line")) in reported_links:
                continue
            target = str(link.get("target") or link.get("raw") or "")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            errors.append(issue(
                "route_unreachable",
                f"Root route does not resolve: {target}",
                severity="error", file=path, line=link.get("line"),
                target=target or None,
            ))

    # Orphans and cross-reference cycles.
    for document in documents:
        path = str(document.get("path", ""))
        if path in roots or path in has_incoming:
            continue
        if path in owner_paths:
            # Covered by owner_unreachable; do not also report it as an orphan.
            continue
        warnings.append(issue(
            "orphan_document",
            f"In-scope document has no incoming link: {path}",
            severity="warning", file=path,
        ))
    for group in _cycle_groups(_resolved_documents(index)):
        info.append(issue(
            "link_cycle",
            "Allowed cross-reference cycle: " + " -> ".join(group),
            severity="info", section=", ".join(group),
        ))

    # Foreign URLs are recorded but never fetched. The index owns this class
    # when it reports it; only fill the gap if it did not.
    if not index_reports_external:
        for document in documents:
            for link in _document_links(document):
                raw = str(link.get("raw") or "")
                if raw.startswith(("http://", "https://")):
                    info.append(issue(
                        "foreign_url",
                        f"External URL was not fetched: {raw}",
                        severity="info", file=str(document.get("path", "")),
                        line=link.get("line"), target=raw,
                    ))

    coverage = owner_coverage(index, index_module)
    scan_complete = index.get("scan_complete") is True
    if index.get("traversal_complete") is False:
        scan_complete = False

    if not renderer_available and graph_status == "missing":
        info.append(issue(
            "renderer_unavailable",
            "Graph renderer is unavailable; artifact freshness could not be checked",
            severity="info",
        ))

    if graph_status == "missing":
        if require_graph:
            errors.append(issue(
                "graph_missing",
                f"Required graph artifact is missing: {GRAPH_REL_PATH}",
                severity="error", target=str(GRAPH_REL_PATH),
            ))
    elif graph_status in GRAPH_STATUS_ISSUES:
        code, message = GRAPH_STATUS_ISSUES[graph_status]
        level = "error" if require_graph else "warning"
        (errors if require_graph else warnings).append(issue(
            code, message, severity=level, target=str(GRAPH_REL_PATH),
        ))

    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    info = _dedupe(info)

    if errors:
        status = "fail"
    elif not scan_complete or coverage != "evaluated":
        status = "unknown"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "scan_complete": scan_complete,
        "owner_coverage": coverage,
        "files_checked": len(documents),
        "source_fingerprint": index_fingerprint(index, index_module),
        "graph_status": graph_status,
        "map_path": str(index.get("map_path", DEFAULT_MAP_PATH)),
        "root": str(index.get("root", "")),
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


# --------------------------------------------------------------------------
# Graph artifact: freshness, boundary checks, atomic write
# --------------------------------------------------------------------------


def _resolved_within_root(root: Path, path: Path, code: str) -> Path:
    """Return the real path of ``path`` after proving it stays inside ``root``."""

    root_real = root.resolve()
    try:
        path_real = path.resolve()
    except OSError as exc:
        raise GraphError(code, f"Path could not be resolved: {path}: {exc}", EXIT_USAGE) from exc
    if path_real != root_real and root_real not in path_real.parents:
        raise GraphError(
            code,
            f"Refusing to touch a path outside the project root: {path}",
            EXIT_USAGE,
        )
    return path_real


def graph_artifact_path(root: Path) -> Path:
    return root / GRAPH_REL_PATH


def guard_artifact_path(root: Path) -> Path:
    """Return the artifact path after proving it cannot leave the project root.

    The guard runs before any stat or read of the artifact, so neither
    ``--check`` nor ``--write`` can follow a directory symlink or an HTML
    symlink out of the project, and neither can overwrite an unrelated file
    through one.
    """

    target = graph_artifact_path(root)
    directory = target.parent

    if directory.is_symlink():
        _resolved_within_root(root, directory, "graph_dir_escape")
    if directory.exists() and not directory.is_dir():
        raise GraphError(
            "graph_dir_conflict",
            f"Graph directory is not a directory: {directory}",
            EXIT_USAGE,
        )
    _resolved_within_root(root, directory if directory.exists() else root, "graph_dir_escape")
    if target.is_symlink():
        raise GraphError(
            "graph_path_symlink",
            f"Refusing to follow a graph symlink: {target}",
            EXIT_USAGE,
        )
    return target


def parse_graph_meta(text: str) -> dict | None:
    """Return the recorded identity of a graph artifact, or None if it is not one."""

    match = re.search(
        r'<script[^>]*id="' + re.escape(GRAPH_DATA_ID) + r'"[^>]*>(.*?)</script>',
        text,
        re.S,
    )
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    inner = data.get("index") if isinstance(data.get("index"), dict) else {}
    source = inner.get("source_fingerprint")
    if not isinstance(source, str) or not source:
        source = data.get("source_fingerprint")
    renderer = data.get("renderer_fingerprint")
    return {
        "source_fingerprint": source if isinstance(source, str) and source else None,
        "renderer_fingerprint": renderer if isinstance(renderer, str) and renderer else None,
    }


def graph_status_for(root: Path, fingerprint: str, renderer_fp: str) -> str:
    """Return missing, unreadable, unverified, stale, or fresh for the artifact.

    An absent or incomplete recorded identity is never fresh: an artifact this
    process cannot verify is reported as unverified, not as up to date.
    """

    target = guard_artifact_path(root)
    if not target.exists():
        return "missing"
    if not target.is_file():
        return "unreadable"
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "unreadable"
    meta = parse_graph_meta(text)
    if meta is None:
        return "unreadable"
    if not meta.get("source_fingerprint") or not meta.get("renderer_fingerprint"):
        return "unverified"
    if not fingerprint or not renderer_fp:
        return "unverified"
    if meta["source_fingerprint"] != fingerprint:
        return "stale"
    if meta["renderer_fingerprint"] != renderer_fp:
        return "stale"
    return "fresh"


def write_graph(root: Path, html: str) -> str:
    """Write the artifact atomically. Returns 'written', 'unchanged', or raises.

    The no-op path compares the real bytes, so a hand-edited or corrupted
    artifact is restored instead of being kept because its header still parses.
    """

    target = guard_artifact_path(root)
    directory = target.parent
    data = html.encode("utf-8")

    if target.is_file():
        try:
            if target.read_bytes() == data:
                return "unchanged"
        except OSError as exc:
            raise GraphError(
                "graph_write_failed",
                f"Could not read the current graph: {exc}",
                EXIT_USAGE,
            ) from exc
    elif target.exists():
        raise GraphError(
            "graph_dir_conflict",
            f"Graph path is not a regular file: {target}",
            EXIT_USAGE,
        )

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GraphError("graph_write_failed", f"Could not create graph directory: {exc}", EXIT_USAGE) from exc
    _resolved_within_root(root, directory, "graph_dir_escape")

    handle = None
    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=".documentation-graph-", suffix=".html.tmp", dir=str(directory)
        )
        temp_path = Path(temp_name)
        handle = os.fdopen(fd, "wb")
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temp_path, target)
        temp_path = None
    except OSError as exc:
        raise GraphError("graph_write_failed", f"Could not write graph artifact: {exc}", EXIT_USAGE) from exc
    finally:
        if handle is not None:
            handle.close()
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
    try:
        dir_fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:  # pragma: no cover - best effort on platforms without dir fsync
        pass
    return "written"


# --------------------------------------------------------------------------
# Section and outline
# --------------------------------------------------------------------------


def document_headings(document: dict) -> list[dict]:
    """Return this document's headings from the shared index parser.

    Headings come only from the index, so the graph, the checker, and the reader
    share one anchor algorithm. A missing headings list is a contract error, not
    a reason to re-parse the Markdown with a second regex.
    """

    headings = document.get("headings")
    if not isinstance(headings, list):
        raise GraphError(
            "index_contract_mismatch",
            f"index document {document.get('path')!r} has no headings list",
            EXIT_USAGE,
        )
    return sorted(headings, key=lambda h: (h.get("line_start") or 0, h.get("level") or 0))


def outline_for(index: dict, rel_path: str) -> dict:
    document = document_by_path(index, rel_path)
    if document is None:
        raise GraphError(
            "document_not_in_scope",
            f"Document is not part of the scanned scope: {rel_path}",
            EXIT_DOCS,
        )
    if not document_parse_complete(index, document):
        # The index could not parse the whole document, so its headings are not
        # a reliable set of addresses. Fail with the recorded cause instead of
        # printing an outline that silently claims to be current.
        message, blockers = _parse_incomplete_message(index, document, "outline")
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "parse_complete": False,
            "code": "document_parse_incomplete",
            "path": str(document.get("path", rel_path)),
            "title": str(document.get("title", "")),
            "message": message,
            "diagnostics": blockers,
            "headings": [],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "parse_complete": True,
        "path": str(document.get("path", rel_path)),
        "title": str(document.get("title", "")),
        "message": None,
        "diagnostics": [],
        "headings": [
            {
                "text": str(h.get("text", "")),
                "anchor": str(h.get("anchor", "")),
                "level": h.get("level"),
                "line_start": h.get("line_start"),
                "line_end": h.get("line_end"),
            }
            for h in document_headings(document)
        ],
    }


def section_for(index: dict, target: str, index_module) -> dict:
    path_part, _, anchor = target.partition("#")
    if not anchor:
        raise GraphError(
            "target_missing",
            f"--section requires RELPATH#ANCHOR, got: {target}",
            EXIT_USAGE,
        )
    document = document_by_path(index, path_part)
    if document is None:
        raise GraphError(
            "document_not_in_scope",
            f"Document is not part of the scanned scope: {path_part}",
            EXIT_DOCS,
        )
    if not document_parse_complete(index, document):
        # An exact line range from a partially parsed document would be a guess.
        # Return an explicit failure before the shared index computes any range.
        message, blockers = _parse_incomplete_message(index, document, "section lookup")
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "parse_complete": False,
            "code": "document_parse_incomplete",
            "path": str(document.get("path", path_part)),
            "anchor": str(anchor),
            "title": None,
            "level": None,
            "line_start": None,
            "line_end": None,
            "parents": [],
            "intro": [],
            "preamble": None,
            "candidates": [],
            "text": "",
            "message": message,
            "diagnostics": blockers,
        }
    section_range = getattr(index_module, "section_range", None)
    if not callable(section_range):
        raise GraphError(
            "index_contract_mismatch",
            "documentation index helper has no section_range()",
            EXIT_USAGE,
        )
    try:
        result = section_range(document, anchor)
    except GraphError:
        raise
    except Exception as exc:
        raise GraphError(
            "section_failed",
            f"Section lookup failed: {exc}",
            EXIT_USAGE,
        ) from exc
    if not isinstance(result, dict):
        raise GraphError(
            "index_contract_mismatch",
            f"section_range() for {target} did not return a mapping",
            EXIT_USAGE,
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(result.get("ok")),
        "code": result.get("code"),
        "path": str(result.get("path") or document.get("path", path_part)),
        "anchor": str(result.get("anchor") or anchor),
        "title": result.get("title"),
        "level": result.get("level"),
        "line_start": result.get("line_start", result.get("start")),
        "line_end": result.get("line_end", result.get("end")),
        "parents": list(result.get("parents") or result.get("ancestors") or []),
        "intro": list(result.get("intro") or []),
        "preamble": result.get("preamble"),
        "candidates": list(result.get("candidates") or []),
        "text": str(result.get("text") or ""),
    }
    message = result.get("message")
    if not payload["ok"] and not message:
        code = str(payload["code"] or "anchor_missing")
        if code == "anchor_collision":
            message = f"Anchor '{anchor}' is ambiguous in {path_part}"
        elif code == "anchor_missing":
            message = f"Anchor '{anchor}' was not found in {path_part}"
        else:
            message = f"Section lookup for '{target}' failed: {code}"
    payload["message"] = str(message) if message else None
    return payload


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def report_exit_code(report: dict) -> int:
    return EXIT_DOCS if report.get("errors") else EXIT_OK


def print_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False))
        return
    print(f"status: {report.get('status')}")
    print(f"owner coverage: {report.get('owner_coverage')}")
    print(f"files checked: {report.get('files_checked')}")
    print(f"graph: {report.get('graph_status')}")
    for level in ("errors", "warnings", "info"):
        for entry in report.get(level, []) or []:
            location = entry.get("file") or ""
            if entry.get("line"):
                location = f"{location}:{entry['line']}"
            if entry.get("section"):
                location = f"{location}#{entry['section']}" if location else str(entry['section'])
            prefix = f"{location} " if location else ""
            print(f"{level[:-1]}: {prefix}{entry.get('code')}: {entry.get('message')}")


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _ArgumentParser(argparse.ArgumentParser):
    """Argparse variant that reports usage errors through GraphError.

    This keeps ``--json`` output machine-readable: an argument error becomes a
    clean report instead of a usage block, and stdin never sees a traceback.
    """

    def error(self, message):
        raise GraphError("invalid_arguments", message, EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="documentation_graph.py",
        description="Check, build, outline, or read a project documentation graph.",
    )
    parser.add_argument("--root", required=True, help="Project root directory.")
    parser.add_argument(
        "--map",
        default=DEFAULT_MAP_PATH,
        help=f"Map path relative to the root (default: {DEFAULT_MAP_PATH}).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="Check documentation and graph freshness without writing anything.")
    mode.add_argument("--write", action="store_true", help="Check and write the offline HTML graph.")
    mode.add_argument("--outline", metavar="RELPATH", help="Print headings for one in-scope document.")
    mode.add_argument("--section", metavar="RELPATH#ANCHOR",
                      help="Print one exact section from an in-scope document.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--require-graph", action="store_true",
                        help="Require a present and current graph artifact (--check only).")
    return parser


def _empty_report() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail",
        "scan_complete": False,
        "owner_coverage": "not_evaluated",
        "files_checked": 0,
        "source_fingerprint": None,
        "graph_status": "unknown",
        "errors": [],
        "warnings": [],
        "info": [],
    }


def _fail(json_mode: bool, code: str, message: str, exit_code: int) -> int:
    if json_mode:
        payload = _empty_report()
        payload["errors"] = [issue(code, message, severity="error")]
        print_json(payload)
    else:
        print(f"error: {code}: {message}", file=sys.stderr)
    return exit_code


def print_section(payload: dict) -> None:
    if not payload.get("ok"):
        print(f"error: {payload.get('code')}: {payload.get('message')}", file=sys.stderr)
        for diagnostic in payload.get("diagnostics") or []:
            location = str(diagnostic.get("code") or "")
            if diagnostic.get("line"):
                location = f"{location} line {diagnostic['line']}"
            print(f"diagnostic: {location}: {diagnostic.get('message') or ''}", file=sys.stderr)
        for candidate in payload.get("candidates") or []:
            print(
                f"candidate: #{candidate.get('anchor')} {candidate.get('title')} "
                f"(line {candidate.get('line_start')})",
                file=sys.stderr,
            )
        return
    print(f"{payload['path']}#{payload['anchor']} (lines {payload['line_start']}-{payload['line_end']})")
    preamble = payload.get("preamble") or {}
    if payload.get("level") and preamble.get("text"):
        print(preamble["text"])
    for parent in payload.get("parents") or []:
        level = max(1, int(parent.get("level") or 1))
        print(f"{'#' * level} {parent.get('text') or ''}")
    print(payload.get("text", ""))


def print_outline(payload: dict) -> None:
    if not payload.get("ok", True):
        print(f"error: {payload.get('code')}: {payload.get('message')}", file=sys.stderr)
        for diagnostic in payload.get("diagnostics") or []:
            location = str(diagnostic.get("code") or "")
            if diagnostic.get("line"):
                location = f"{location} line {diagnostic['line']}"
            print(f"diagnostic: {location}: {diagnostic.get('message') or ''}", file=sys.stderr)
        return
    print(f"{payload['path']}: {payload['title']}")
    for heading in payload["headings"]:
        indent = "  " * max(0, int(heading.get("level") or 1) - 1)
        print(f"{indent}- {heading['text']} (#{heading['anchor']}, line {heading['line_start']})")


def run(argv: list[str]) -> int:
    parser = build_parser()
    json_mode = "--json" in argv
    try:
        args = parser.parse_args(argv)
    except GraphError as exc:
        return _fail(json_mode, exc.code, exc.message, exc.exit_code)

    if args.require_graph and not args.check:
        return _fail(args.json, "invalid_arguments", "--require-graph is only valid with --check", EXIT_USAGE)

    root = Path(args.root).expanduser()

    try:
        if not root.is_dir():
            raise GraphError("root_missing", f"Project root is not a directory: {root}", EXIT_USAGE)

        map_path = args.map
        if not (root / map_path).is_file():
            raise GraphError("map_missing", f"Documentation map not found: {root / map_path}", EXIT_USAGE)

        index_module = load_index_module()
        index = build_index(index_module, root, map_path)

        if args.outline is not None:
            payload = outline_for(index, args.outline)
            if args.json:
                print_json(payload)
            else:
                print_outline(payload)
            return EXIT_OK if payload.get("ok", True) else EXIT_DOCS

        if args.section is not None:
            payload = section_for(index, args.section.strip(), index_module)
            if args.json:
                print_json(payload)
            else:
                print_section(payload)
            return EXIT_OK if payload.get("ok") else EXIT_DOCS

        fingerprint = index_fingerprint(index, index_module)

        if args.write:
            renderer = load_render_module()
            renderer_fp = renderer_identity(renderer)
            # The artifact records the fingerprint the CLI later verifies, so
            # keep the embedded value identical to the computed fingerprint.
            index = {**index, "source_fingerprint": fingerprint}
            report = build_report(index, graph_status="fresh", require_graph=False,
                                  index_module=index_module, renderer_available=True)
            try:
                html = renderer.render_graph(index, report)
            except Exception as exc:
                raise GraphError("render_failed", f"Graph renderer failed: {exc}", EXIT_USAGE) from exc
            if not isinstance(html, str) or not html.strip():
                raise GraphError("render_failed", "Graph renderer returned no HTML", EXIT_USAGE)

            # Re-read immediately before the atomic replace; never publish a
            # mixed snapshot when a file was added, removed, or edited.
            confirm = build_index(index_module, root, map_path)
            if index_fingerprint(confirm, index_module) != fingerprint:
                raise GraphError(
                    "source_changed_during_write",
                    "Sources changed while the graph was being built; previous artifact preserved",
                    EXIT_USAGE,
                )

            outcome = write_graph(root, html)
            report["graph_status"] = "fresh"
            print_report(report, as_json=args.json)
            if not args.json:
                print(f"graph: {outcome} ({GRAPH_REL_PATH})")
            return report_exit_code(report)

        try:
            renderer = load_render_module()
            renderer_fp = renderer_identity(renderer)
        except GraphError:
            # A missing or unverifiable renderer must not block link and owner
            # checks. It only blocks --write and a required-graph verification.
            if args.require_graph:
                raise
            renderer = None
            renderer_fp = ""
        status = graph_status_for(root, fingerprint, renderer_fp)
        report = build_report(index, graph_status=status, require_graph=args.require_graph,
                              index_module=index_module, renderer_available=renderer is not None)
        print_report(report, as_json=args.json)
        return report_exit_code(report)

    except GraphError as exc:
        return _fail(args.json, exc.code, exc.message, exc.exit_code)
    except KeyboardInterrupt:  # pragma: no cover - defensive
        return EXIT_USAGE


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
