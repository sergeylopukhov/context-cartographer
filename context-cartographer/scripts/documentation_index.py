#!/usr/bin/env python3
"""Documentation index: the shared Markdown model for context-cartographer.

This is the single place where the documentation graph, the link checker and the
exact-section reader build their structural model, so anchors, link resolution
and section ranges never disagree (implementation plan 03-02,
``references/documentation-format.md``).

Design rules:

* Python standard library only; never touches the network.
* Every public function returns plain dicts and lists that serialize as JSON.
* Each document is parsed once per snapshot; nothing re-reads a file to build a
  section range.
* Content that can hide structure (code blocks, HTML comments) is skipped
  instead of guessed, and unsupported constructs are reported rather than
  silently dropped.
* Nothing from a document is executed or interpreted as an instruction.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote


__all__ = [
    "DEFAULT_MAP_PATH",
    "MAX_DOCUMENT_BYTES",
    "SCHEMA_VERSION",
    "anchor_for",
    "build_index",
    "fingerprint",
    "owner_coverage",
    "parse_document",
    "resolve_link",
    "resolve_scope",
    "scan_scope",
    "section_range",
    "to_json",
]

SCHEMA_VERSION = 1
SUPPORTED_FORMAT_VERSION = 1
DEFAULT_MAP_PATH = "docs/architecture.md"

# A single document larger than this is capped, marked incomplete, and never
# claims a complete parse.
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024

MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdc")

# Service directories, dependencies, build output and secrets are never scanned
# unless the map lists them in an explicit include entry.
DEFAULT_EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".bzr",
    "node_modules", "bower_components", "jspm_packages",
    ".venv", "venv", "env", ".tox", ".nox", ".eggs",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".cache", ".parcel-cache", ".next", ".nuxt", ".svelte-kit", ".turbo",
    "dist", "build", "out", "target", "vendor",
    ".terraform", ".serverless", ".context-cartographer",
    ".idea", ".vscode", ".direnv",
    ".ssh", ".aws", ".gnupg", ".gcloud", ".kube",
    "secrets", ".secrets", ".private", "credentials",
})

# Root instruction routers used by a bounded bootstrap scan.
BOOTSTRAP_ROOT_FILES = ("AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md", ".cursorrules")
BOOTSTRAP_ROOT_GLOBS = ((".cursor/rules", "*.mdc"),)

FORMAT_MARKER_RE = re.compile(r"^\s*<!--\s*context-cartographer:\s*format_version=(\d+)\s*-->\s*$")
FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
ATX_RE = re.compile(r"^( {0,3})(#{1,6})(.*)$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
ANCHOR_RE = re.compile(
    r"<a\s+[^>]*?\b(?:id|name)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))[^>]*>",
    re.IGNORECASE,
)
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(.*)$")
JSX_RE = re.compile(r"<[A-Z][A-Za-z0-9_]*[\s/>]")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

# Block-level element names that start an HTML block in CommonMark (spec 4.6,
# start conditions 1 and 6). Such a block keeps swallowing input until a blank
# line, so any Markdown on those lines would be guessed rather than parsed.
HTML_BLOCK_TAGS = frozenset({
    "address", "article", "aside", "base", "basefont", "blockquote", "body",
    "caption", "center", "col", "colgroup", "dd", "details", "dialog", "dir",
    "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
    "frame", "frameset", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header",
    "hr", "html", "iframe", "legend", "li", "link", "main", "menu", "menuitem",
    "nav", "noframes", "ol", "optgroup", "option", "p", "param", "search",
    "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead",
    "title", "tr", "track", "ul",
})
# Raw-text elements swallow everything up to their own closing tag.
HTML_RAW_TEXT_TAGS = frozenset({"pre", "script", "style", "textarea"})
HTML_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})
HTML_BLOCK_START_RE = re.compile(r"^ {0,3}<\s*(/?)\s*([A-Za-z][A-Za-z0-9-]*)\b")

UNSAFE_SCHEMES = frozenset({"javascript", "data", "vbscript", "file"})

ISSUE_SEVERITY = {
    "external_link_not_fetched": "info",
    "unsafe_link_scheme": "warning",
    "link_target_missing": "error",
    "link_target_directory": "error",
    "link_outside_root": "error",
    "link_out_of_scope": "warning",
    "anchor_missing": "error",
    "anchor_collision": "error",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _issue(code, message, severity, *, file=None, line=None, section=None,
           target=None, candidates=None):
    entry = {
        "severity": severity,
        "code": code,
        "file": file,
        "line": line,
        "section": section,
        "target": target,
        "message": message,
    }
    if candidates:
        entry["candidates"] = candidates
    return entry


def _norm_rel(value):
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _join_rel(base, name):
    return f"{base}/{name}" if base else name


def _suffix(name):
    return os.path.splitext(name)[1].lower()


def _strip_ticks(text):
    return str(text or "").replace("`", "")


def _normalize_inside(base_dir, target):
    """Return a normalized root-relative path, or None when it escapes the root."""
    text = _norm_rel(target)
    if text.startswith("/"):
        text = text.lstrip("/")
        base_dir = ""
    joined = posixpath.normpath(posixpath.join(base_dir, text)) if base_dir else posixpath.normpath(text)
    if joined in (".", ""):
        return ""
    if joined == ".." or joined.startswith("../") or joined.startswith("/"):
        return None
    return joined


def _real_inside(root_real, rel):
    """Resolve ``rel`` under the root; return None when a symlink leaves the root."""
    try:
        real = Path(os.path.realpath(str(root_real / rel)))
    except OSError:
        return None
    if real == root_real or root_real in real.parents:
        return real
    return None


def _rel_from_root(root_real, path_like):
    text = str(path_like or "")
    if not text:
        return ""
    try:
        return Path(text).resolve().relative_to(root_real).as_posix()
    except (ValueError, OSError):
        return os.path.relpath(text, str(root_real)).replace(os.sep, "/")


def _is_excluded(rel, excludes):
    if not rel:
        return False
    if any(segment in DEFAULT_EXCLUDED_DIRS for segment in rel.split("/")):
        return True
    return any(rel == entry or rel.startswith(entry + "/") for entry in excludes)


def _normalize_header(name):
    return re.sub(r"\s+", " ", _strip_ticks(name).strip().lower())


def _column_index(header):
    index = {}
    for position, name in enumerate(header):
        key = _normalize_header(name)
        if key and key not in index:
            index[key] = position
    return index


def _unescape(text):
    return re.sub(r"\\(.)", r"\1", text)


def _norm_label(label):
    return re.sub(r"\s+", " ", _unescape(label or "").strip()).lower()


def _plain_inline(text):
    """Best-effort plain text for a heading or table cell."""
    out = re.sub(r"`+([^`]*)`+", r"\1", text or "")
    out = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", out)
    out = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", out)
    out = re.sub(r"!\[([^\]]*)\]\[[^\]]*\]", r"\1", out)
    out = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def anchor_for(heading_text):
    """The single slug algorithm shared by the index, the graph and the reader."""
    text = re.sub(r"<[^>]*>", "", str(heading_text or ""))
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text or "section"


def _unique_slug(base, used):
    if base not in used:
        used.add(base)
        return base
    counter = 1
    while f"{base}-{counter}" in used:
        counter += 1
    slug = f"{base}-{counter}"
    used.add(slug)
    return slug


# ---------------------------------------------------------------------------
# Markdown structure scan
# ---------------------------------------------------------------------------


def _indent_width(line):
    width = 0
    for char in line:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 4 - (width % 4)
        else:
            break
    return width


def _line_count(text):
    """Number of source lines, not counting the final newline as an empty line."""
    if not text:
        return 0
    count = text.count("\n")
    if not text.endswith("\n"):
        count += 1
    return count


def _closing_fence_re(fence):
    return re.compile(r"^ {0,3}(" + re.escape(fence[0]) + r"{" + str(fence[1]) + r",})[ \t]*$")


def _structural_lines(text):
    """Return (line_number, line) pairs outside fenced/indented code and comments.

    Line numbers always refer to the original file, including front matter and
    skipped code blocks.
    """
    lines = text.split("\n")
    out = []
    fence = None
    in_comment = False
    indented = False

    start = 0
    if lines and lines[0].strip() in ("---", "+++") and len(lines) > 1:
        marker = lines[0].strip()
        for position in range(1, len(lines)):
            if lines[position].strip() == marker:
                start = position + 1
                break

    position = start
    while position < len(lines):
        line = lines[position].rstrip("\r")
        number = position + 1
        if in_comment:
            if "-->" in line:
                in_comment = False
            position += 1
            continue
        if fence is not None:
            if _closing_fence_re(fence).match(line):
                fence = None
            position += 1
            continue
        if indented:
            if line.strip() == "":
                position += 1
                continue
            if _indent_width(line) >= 4:
                position += 1
                continue
            indented = False
        elif (line.strip() and _indent_width(line) >= 4
              and (position == 0 or lines[position - 1].strip() == "")):
            indented = True
            position += 1
            continue

        match = FENCE_RE.match(line)
        if match:
            fence = (match.group(2)[0], len(match.group(2)))
            position += 1
            continue
        if "<!--" in line:
            _, _, remainder = line.partition("<!--")
            if "-->" not in remainder:
                in_comment = True
            position += 1
            continue
        out.append((number, line))
        position += 1
    return out


def _format_marker_version(text):
    lines = text.split("\n")
    fence = None
    for raw in lines:
        line = raw.rstrip("\r")
        if fence is not None:
            if _closing_fence_re(fence).match(line):
                fence = None
            continue
        match = FENCE_RE.match(line)
        if match:
            fence = (match.group(2)[0], len(match.group(2)))
            continue
        marker = FORMAT_MARKER_RE.match(line)
        if marker:
            return int(marker.group(1))
    return None


def _strip_inline_code(text):
    out = []
    position = 0
    length = len(text)
    while position < length:
        if text[position] == "`":
            end = position
            while end < length and text[end] == "`":
                end += 1
            run = end - position
            close = text.find("`" * run, end)
            if close == -1:
                out.append(text[position:])
                break
            out.append(" ")
            position = close + run
            continue
        out.append(text[position])
        position += 1
    return "".join(out)


def _parse_atx(line):
    match = ATX_RE.match(line)
    if not match:
        return None
    rest = match.group(3)
    if rest and rest[0] not in " \t":
        return None
    text = re.sub(r"[ \t]+#+[ \t]*$", "", rest.strip()).strip()
    return len(match.group(2)), text


def _setext_level(line):
    match = SETEXT_RE.match(line)
    if not match:
        return None
    return 1 if match.group(1)[0] == "=" else 2


def _starts_block(text):
    stripped = text.strip()
    if not stripped:
        return True
    if ATX_RE.match(text):
        return True
    if stripped.startswith("|"):
        return True
    if REF_DEF_RE.match(text):
        return True
    return bool(FENCE_RE.match(text))


def _find_bracket(line, start):
    depth = 0
    position = start
    while position < len(line):
        char = line[position]
        if char == "\\":
            position += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return position
        position += 1
    return -1


def _read_paren_target(line, start):
    """Parse ``(...)`` starting at ``start``; return (raw_target, end) or (None, end)."""
    length = len(line)
    position = start + 1
    while position < length and line[position] in " \t":
        position += 1

    if position < length and line[position] == "<":
        cursor = position + 1
        buffer = []
        while cursor < length and line[cursor] != ">":
            if line[cursor] == "\\" and cursor + 1 < length:
                buffer.append(line[cursor + 1])
                cursor += 2
                continue
            buffer.append(line[cursor])
            cursor += 1
        if cursor >= length:
            return None, length
        raw = "".join(buffer)
        cursor += 1
    else:
        depth = 1
        buffer = []
        cursor = position
        while cursor < length:
            char = line[cursor]
            if char == "\\" and cursor + 1 < length:
                buffer.append(line[cursor + 1])
                cursor += 2
                continue
            if char == "(":
                depth += 1
                buffer.append(char)
                cursor += 1
                continue
            if char == ")":
                depth -= 1
                if depth == 0:
                    break
                buffer.append(char)
                cursor += 1
                continue
            if char in " \t":
                break
            buffer.append(char)
            cursor += 1
        raw = "".join(buffer)

    cursor_end = cursor
    while cursor_end < length and line[cursor_end] in " \t":
        cursor_end += 1
    if cursor_end < length and line[cursor_end] in "\"'(":
        closer = {"\"": "\"", "'": "'", "(": ")"}[line[cursor_end]]
        scan = cursor_end + 1
        while scan < length:
            if line[scan] == "\\" and scan + 1 < length:
                scan += 2
                continue
            if line[scan] == closer:
                break
            scan += 1
        if scan >= length:
            return None, length
        cursor_end = scan + 1
        while cursor_end < length and line[cursor_end] in " \t":
            cursor_end += 1
    if cursor_end >= length or line[cursor_end] != ")":
        return None, length
    return raw, cursor_end + 1


def _extract_inline_links(line):
    """Return inline, reference and shortcut links found in one line."""
    results = []
    position = 0
    length = len(line)
    while position < length:
        char = line[position]
        if char == "\\":
            position += 2
            continue
        if char == "[" or (char == "!" and position + 1 < length and line[position + 1] == "["):
            image = char == "!"
            open_at = position + 1 if image else position
            close_at = _find_bracket(line, open_at)
            if close_at == -1:
                position += 1
                continue
            text = line[open_at + 1:close_at]
            after = close_at + 1
            if after < length and line[after] == "(":
                raw, end = _read_paren_target(line, after)
                if raw is None:
                    position = close_at + 1
                    continue
                results.append({"image": image, "text": text, "raw": raw})
                position = end
                continue
            if after < length and line[after] == "[":
                close_label = _find_bracket(line, after)
                if close_label != -1:
                    label = line[after + 1:close_label] or text
                    results.append({"image": image, "text": text, "label": _norm_label(label)})
                    position = close_label + 1
                    continue
            results.append({"image": image, "text": text, "label": _norm_label(text)})
            position = close_at + 1
            continue
        position += 1
    return results


def _parse_reference_definition(rest):
    rest = rest.strip()
    if not rest:
        return None
    if rest.startswith("<"):
        end = rest.find(">")
        if end == -1:
            return None
        return _unescape(rest[1:end])
    return rest.split()[0]


# ---------------------------------------------------------------------------
# Headings, explicit anchors and tables
# ---------------------------------------------------------------------------


def _heading(text, level, line_start):
    return {
        "text": text,
        "anchor": "",
        "level": level,
        "line_start": line_start,
        "line_end": None,
        "aliases": [],
    }


def _headings_and_anchors(structural, total_lines):
    headings = []
    raw_anchors = []
    previous = None

    for line_number, line in structural:
        matches = list(ANCHOR_RE.finditer(line))
        # ``<a id="x"></a>`` on its own line is still a standalone anchor, so the
        # closing tag must not make the line look like ordinary prose.
        remainder = re.sub(r"<a\b[^>]*>|</a\s*>", "", line, flags=re.IGNORECASE)
        for match in matches:
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                raw_anchors.append({
                    "name": name,
                    "line": line_number,
                    "standalone": remainder.strip() == "",
                })

        if previous is not None and previous[0] == line_number - 1:
            level = _setext_level(line)
            if level is not None and not _starts_block(previous[1]):
                headings.append(_heading(_plain_inline(previous[1]), level, previous[0]))
                previous = None
                continue

        atx = _parse_atx(line)
        if atx is not None:
            level, text = atx
            headings.append(_heading(text, level, line_number))
            previous = None
            continue

        if matches and remainder.strip() == "":
            previous = None
            continue
        previous = (line_number, line)

    used = set()
    for heading in headings:
        heading["anchor"] = _unique_slug(anchor_for(_plain_inline(heading["text"])), used)

    for index, heading in enumerate(headings):
        end = total_lines
        for other in headings[index + 1:]:
            if other["level"] <= heading["level"]:
                end = other["line_start"] - 1
                break
        heading["line_end"] = max(end, heading["line_start"])

    for anchor in raw_anchors:
        target = None
        if anchor["standalone"]:
            for index, heading in enumerate(headings):
                if heading["line_start"] == anchor["line"] + 1:
                    target = index
                    break
        if target is None:
            target = -1
            for index, heading in enumerate(headings):
                if heading["line_start"] <= anchor["line"]:
                    target = index
                else:
                    break
        anchor["heading"] = target

    preamble_anchors = []
    for anchor in raw_anchors:
        if anchor["heading"] == -1:
            if anchor["name"] not in preamble_anchors:
                preamble_anchors.append(anchor["name"])
            continue
        heading = headings[anchor["heading"]]
        if anchor["name"] == heading["anchor"]:
            continue
        if anchor["name"] not in heading["aliases"]:
            heading["aliases"].append(anchor["name"])

    return headings, preamble_anchors


def _is_table_row(line):
    return line.strip().startswith("|")


def _is_table_separator(line):
    cells = _split_cells(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-+:?", cell or "") for cell in cells)


def _split_cells(line):
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells = []
    buffer = []
    position = 0
    while position < len(text):
        char = text[position]
        if char == "\\" and position + 1 < len(text) and text[position + 1] in "|\\":
            buffer.append(text[position + 1])
            position += 2
            continue
        if char == "|":
            cells.append("".join(buffer))
            buffer = []
            position += 1
            continue
        buffer.append(char)
        position += 1
    cells.append("".join(buffer))
    return [cell.strip() for cell in cells]


def _tables(structural):
    tables = []
    position = 0
    while position < len(structural) - 1:
        line_number, text = structural[position]
        next_number, next_text = structural[position + 1]
        if (_is_table_row(text) and next_number == line_number + 1
                and _is_table_separator(next_text)):
            header = _split_cells(text)
            rows = []
            cursor = position + 2
            while (cursor < len(structural)
                   and _is_table_row(structural[cursor][1])
                   and structural[cursor][0] == structural[cursor - 1][0] + 1):
                rows.append((structural[cursor][0], _split_cells(structural[cursor][1])))
                cursor += 1
            tables.append({"line": line_number, "header": header, "rows": rows})
            position = cursor
            continue
        position += 1
    return tables


def _find_table(tables, required, forbidden=()):
    for table in tables:
        names = {_normalize_header(name) for name in table["header"]}
        if table["header"] and required <= names and not (set(forbidden) & names):
            return table
    return None


# ---------------------------------------------------------------------------
# Raw HTML block diagnostics
# ---------------------------------------------------------------------------


def _html_hidden_structure(line, previous, line_number):
    """Name the Markdown construct a raw HTML block would be hiding, or None."""
    if _parse_atx(line) is not None:
        return "a heading"
    if REF_DEF_RE.match(line):
        return "a reference definition"
    if (previous is not None and previous[0] == line_number - 1
            and _setext_level(line) is not None
            and not _starts_block(previous[1])):
        return "a setext heading"
    if _is_table_row(line):
        return "a table row"
    stripped = _strip_inline_code(line)
    for item in _extract_inline_links(stripped):
        if "raw" in item:
            return "an image" if item.get("image") else "a link"
        if "label" in item and re.search(r"\]\[", stripped):
            return "a reference link"
    return None


def _is_html_block_start(line):
    """Return ``(name, self_closing)`` when ``line`` starts a raw HTML block."""
    start = HTML_BLOCK_START_RE.match(line)
    if start is None or start.group(1) == "/":
        return None
    name = start.group(2).lower()
    if name not in HTML_BLOCK_TAGS and name not in HTML_RAW_TEXT_TAGS:
        return None
    return name, bool(re.search(r"/\s*>$", line))


def _html_block_detail(structural, start, raw_text_tag):
    """Best-effort name of the Markdown hidden inside one raw HTML block."""
    previous = None
    for line_number, line in structural[start:]:
        if raw_text_tag is not None:
            if re.search(r"</\s*" + re.escape(raw_text_tag) + r"\b", line, re.IGNORECASE):
                break
            previous = None
            continue
        if not line.strip():
            break
        detail = _html_hidden_structure(line, previous, line_number)
        if detail is not None:
            return detail
        if _is_html_block_start(line) is not None:
            return "a nested raw HTML block"
        previous = (line_number, line)
    return None


def _html_block_structure(structural):
    """Return ``(line_number, detail)`` for the first raw HTML block, or None.

    A conservative heuristic, not a full HTML or GFM parser. A line that starts
    a CommonMark HTML block (a block-level element, or ``pre``/``script``/
    ``style``/``textarea``) makes the surrounding Markdown untrustworthy: the
    block swallows input until a blank line or its closing tag, so headings,
    links and tables written inside it would be guessed rather than parsed and
    must not be reported as unconditional success. ``detail`` names the hidden
    construct when one is visible inside the block.

    A container element is reported even when nothing hidden is visible, so a
    single ``<div>raw</div>`` line is still flagged. A void or self-closing tag
    such as ``<hr>`` is reported only when the rest of its block really hides
    Markdown, so an ordinary horizontal rule stays supported.

    Only lines that ``_structural_lines`` kept are inspected, so fenced and
    indented code blocks and HTML comments are never false positives here.
    Explicit ``<a id>``/``<a name>`` anchors and inline formatting are not block
    starts, so they stay supported too.
    """
    for offset, (line_number, line) in enumerate(structural):
        opening = _is_html_block_start(line)
        if opening is None:
            continue
        name, self_closing = opening
        if name in HTML_RAW_TEXT_TAGS:
            if self_closing:
                continue
            return line_number, _html_block_detail(structural, offset + 1, name)
        detail = _html_block_detail(structural, offset + 1, None)
        if name in HTML_VOID_TAGS or self_closing:
            if detail is None:
                continue
            return line_number, detail
        return line_number, detail
    return None


# ---------------------------------------------------------------------------
# Document analysis
# ---------------------------------------------------------------------------


def _analyze(path, root=None, rel_path=None, want_tables=False):
    root_real = Path(root).resolve() if root is not None else None
    target = Path(path)
    if root_real is not None and not target.is_absolute():
        target = root_real / target

    if rel_path is None:
        if root_real is not None:
            try:
                rel_path = target.resolve().relative_to(root_real).as_posix()
            except (ValueError, OSError):
                rel_path = target.name
        else:
            rel_path = target.name
    rel = _norm_rel(rel_path)

    issues = []
    parse_complete = True
    text = ""

    outside = root_real is not None and _real_inside(root_real, rel) is None
    if outside:
        issues.append(_issue(
            "document_outside_root",
            f"Document path escapes the project root: {rel}",
            "error", file=rel,
        ))
        parse_complete = False
        data = None
    else:
        try:
            with open(target, "rb") as handle:
                data = handle.read(MAX_DOCUMENT_BYTES + 1)
        except OSError as exc:
            issues.append(_issue(
                "document_unreadable",
                f"Document could not be read: {rel}: {exc}",
                "error", file=rel,
            ))
            parse_complete = False
            data = None

    if data is not None and len(data) > MAX_DOCUMENT_BYTES:
        data = data[:MAX_DOCUMENT_BYTES]
        issues.append(_issue(
            "document_too_large",
            f"Document is larger than {MAX_DOCUMENT_BYTES} bytes and was capped: {rel}",
            "warning", file=rel,
        ))
        parse_complete = False
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
    elif data is not None:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            text = data.decode("utf-8", errors="replace")
            issues.append(_issue(
                "document_unreadable",
                f"Document is not valid UTF-8: {rel}: {exc}",
                "error", file=rel,
            ))
            parse_complete = False

    structural = _structural_lines(text)
    headings, preamble_anchors = _headings_and_anchors(structural, _line_count(text))

    definitions = {}
    for line_number, line in structural:
        match = REF_DEF_RE.match(line)
        if match:
            definition = _parse_reference_definition(match.group(2))
            if definition:
                definitions[_norm_label(match.group(1))] = definition

    links = []
    for line_number, line in structural:
        if REF_DEF_RE.match(line):
            continue
        for item in _extract_inline_links(_strip_inline_code(line)):
            if "raw" in item:
                raw = item["raw"]
            else:
                raw = definitions.get(item.get("label", ""))
                if raw is None:
                    continue
            links.append({
                "text": _plain_inline(item["text"]),
                "raw": raw,
                "target": None,
                "anchor": None,
                "resolved": False,
                "line": line_number,
                "kind": "image" if item["image"] else "link",
            })

    unsupported = False
    for line_number, line in structural:
        if re.match(r"^ {0,3}(import|export)\s+\S", line) or JSX_RE.search(line):
            issues.append(_issue(
                "unsupported_markdown",
                "MDX/JSX content is outside the supported Markdown subset",
                "warning", file=rel, line=line_number,
            ))
            parse_complete = False
            unsupported = True
            break

    if not unsupported:
        # A raw HTML block is outside the supported Markdown subset and can hide
        # headings, links and tables; report it so an incomplete parse never
        # reports unconditional success.
        html = _html_block_structure(structural)
        if html is not None:
            line_number, detail = html
            if detail is None:
                message = "Raw HTML block is outside the supported Markdown subset"
            else:
                message = (
                    f"Raw HTML block hides Markdown structure ({detail}); raw "
                    "HTML blocks are outside the supported Markdown subset"
                )
            issues.append(_issue(
                "unsupported_markdown", message,
                "warning", file=rel, line=line_number,
            ))
            parse_complete = False

    anchor_map = {}
    for index, heading in enumerate(headings):
        anchor_map.setdefault(heading["anchor"], []).append(index)
        for alias in heading["aliases"]:
            anchor_map.setdefault(alias, []).append(index)
    for alias in preamble_anchors:
        anchor_map.setdefault(alias, []).append(-1)

    for name, targets in anchor_map.items():
        distinct = sorted(set(targets))
        if len(distinct) > 1:
            first_line = None
            for heading_index in distinct:
                if heading_index >= 0:
                    first_line = headings[heading_index]["line_start"]
                    break
            issues.append(_issue(
                "anchor_collision",
                f"Anchor '{name}' names more than one section",
                "error", file=rel, line=first_line, target=name,
                candidates=[_candidate(headings, index) for index in distinct],
            ))

    title = headings[0]["text"] if headings else ""
    area = rel.split("/", 1)[0] if "/" in rel else ""

    document = {
        "path": rel,
        "title": title,
        "area": area,
        "text": text,
        "fingerprint": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "parse_complete": parse_complete,
        "headings": headings,
        "links": links,
        "preamble_anchors": preamble_anchors,
    }

    tables = _tables(structural) if want_tables else []
    return {
        "document": document,
        "tables": tables,
        "issues": issues,
        "format_version": _format_marker_version(text),
    }


def _candidate(headings, index):
    heading = headings[index] if 0 <= index < len(headings) else None
    if heading is None:
        return {"anchor": "", "title": "", "level": None, "line_start": None}
    return {
        "anchor": heading["anchor"],
        "title": heading["text"],
        "level": heading["level"],
        "line_start": heading["line_start"],
    }


def _candidates(document):
    results = []
    seen = set()
    for heading in document.get("headings") or []:
        for name in [heading.get("anchor", "")] + list(heading.get("aliases") or []):
            if not name or name in seen:
                continue
            seen.add(name)
            results.append({
                "anchor": name,
                "title": heading.get("text", ""),
                "level": heading.get("level"),
                "line_start": heading.get("line_start"),
            })
    for name in document.get("preamble_anchors") or []:
        if not name or name in seen:
            continue
        seen.add(name)
        results.append({"anchor": name, "title": "", "level": None, "line_start": None})
    return results


def parse_document(path, root=None, rel_path=None):
    """Parse one Markdown file into the public document dict.

    The returned dict carries an extra ``issues`` list with per-document
    diagnostics; :func:`build_index` hoists those into ``format_issues`` and
    drops the key so the index keeps its documented shape.
    """
    analysis = _analyze(path, root=root, rel_path=rel_path, want_tables=False)
    document = analysis["document"]
    document["issues"] = analysis["issues"]
    return document


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def _root_path(root):
    candidate = Path(root).expanduser()
    if not candidate.exists():
        raise FileNotFoundError(f"Project root not found: {candidate}")
    if not candidate.is_dir():
        raise NotADirectoryError(f"Project root is not a directory: {candidate}")
    return candidate.resolve()


def _bootstrap_scope(root_real, map_rel):
    if "/" in map_rel:
        include = [posixpath.dirname(map_rel) + "/"]
    else:
        include = [map_rel]
    roots = [name for name in BOOTSTRAP_ROOT_FILES if (root_real / name).is_file()]
    for base, pattern in BOOTSTRAP_ROOT_GLOBS:
        directory = root_real / base
        if directory.is_dir():
            for found in sorted(directory.glob(pattern)):
                if found.is_file():
                    roots.append(f"{base}/{found.name}")
    deduped = []
    for name in roots:
        if name not in deduped:
            deduped.append(name)
    return include, deduped


def _parse_scope_table(table, map_rel):
    index = _column_index(table["header"])
    kind_at = index.get("kind")
    path_at = index.get("path")
    roots, include, exclude = [], [], []
    issues = []
    if kind_at is None or path_at is None:
        return roots, include, exclude, issues
    for line_number, cells in table["rows"]:
        kind = _normalize_header(cells[kind_at]) if kind_at < len(cells) else ""
        path = _strip_ticks(cells[path_at]).strip() if path_at < len(cells) else ""
        if not path:
            continue
        if kind == "root":
            roots.append(path)
        elif kind == "include":
            include.append(path)
        elif kind == "exclude":
            exclude.append(path)
        else:
            issues.append(_issue(
                "scope_kind_unknown",
                f"Scope row kind '{kind}' is not root, include or exclude",
                "warning", file=map_rel, line=line_number, target=path,
            ))
    return roots, include, exclude, issues


def _resolve_owner_cell(cell, map_rel):
    links = _extract_inline_links(cell)
    if links and "raw" in links[0]:
        raw = links[0]["raw"]
        path_part, _, anchor = raw.partition("#")
        joined = _normalize_inside(posixpath.dirname(map_rel), unquote(path_part))
        if joined:
            return joined + ("#" + anchor if anchor else "")
        return raw
    return _plain_inline(cell)


def _parse_topic_tables(topic_table, dependency_table, map_rel):
    topics = []
    if topic_table is not None:
        index = _column_index(topic_table["header"])
        id_at = index.get("topic id", index.get("topicid", index.get("topic")))
        purpose_at = index.get("purpose")
        owner_at = index.get("owner")
        read_at = index.get("read when", index.get("readwhen"))

        def cell(cells, position):
            if position is None or position >= len(cells):
                return ""
            return cells[position]

        for line_number, cells in topic_table["rows"]:
            topics.append({
                "id": _strip_ticks(cell(cells, id_at)).strip(),
                "purpose": _plain_inline(cell(cells, purpose_at)),
                "owner": _resolve_owner_cell(cell(cells, owner_at), map_rel).strip(),
                "read_when": _plain_inline(cell(cells, read_at)),
                "file": map_rel,
                "line": line_number,
            })

    dependencies = []
    if dependency_table is not None:
        index = _column_index(dependency_table["header"])
        id_at = index.get("topic id", index.get("topicid", index.get("topic")))
        depends_at = index.get("depends on", index.get("dependson"))
        reason_at = index.get("reason")
        for line_number, cells in dependency_table["rows"]:
            topic = _strip_ticks(cells[id_at]).strip() if id_at is not None and id_at < len(cells) else ""
            raw = cells[depends_at] if depends_at is not None and depends_at < len(cells) else ""
            targets = [part.strip() for part in _strip_ticks(raw).split(",") if part.strip()]
            reason = _plain_inline(cells[reason_at]) if reason_at is not None and reason_at < len(cells) else ""
            dependencies.append({
                "topic": topic,
                "depends_on": targets,
                "reason": reason,
                "file": map_rel,
                "line": line_number,
            })
    return topics, dependencies


def resolve_scope(root, map_path=DEFAULT_MAP_PATH):
    """Read the map and return the scope dict (plus parsed map tables).

    Raises FileNotFoundError when the map is missing, and ValueError when the
    map path escapes the project root. The boundary check happens before any
    read.
    """
    root_real = _root_path(root)
    map_rel = _normalize_inside("", map_path)
    if not map_rel:
        raise ValueError(f"Invalid map path: {map_path}")
    if _real_inside(root_real, map_rel) is None:
        raise ValueError(f"Map path escapes the project root: {map_path}")
    map_file = root_real / map_rel
    if not map_file.is_file():
        raise FileNotFoundError(f"Documentation map not found: {map_file}")

    analysis = _analyze(map_file, root=root_real, rel_path=map_rel, want_tables=True)
    document = analysis["document"]
    issues = list(analysis["issues"])
    marker = analysis["format_version"]
    tables = analysis["tables"]

    supported = True
    if marker is None:
        issues.append(_issue(
            "old_format_map",
            "The map has no format marker; coverage is not evaluated",
            "warning", file=map_rel, line=1,
        ))
    elif marker != SUPPORTED_FORMAT_VERSION:
        supported = False
        issues.append(_issue(
            "unknown_format_version",
            f"Map format version {marker} is newer than the supported version {SUPPORTED_FORMAT_VERSION}",
            "error", file=map_rel, line=1,
        ))

    scope_table = _find_table(tables, {"kind", "path"})
    topic_table = _find_table(tables, {"topic id", "purpose", "owner"})
    dependency_table = _find_table(tables, {"topic id", "depends on"})

    if scope_table is None:
        include, roots = _bootstrap_scope(root_real, map_rel)
        exclude = []
        mode = "bootstrap"
        issues.append(_issue(
            "scope_table_missing",
            "The map has no scope table; a bounded bootstrap scope was used",
            "warning", file=map_rel,
        ))
    else:
        roots, include, exclude, scope_issues = _parse_scope_table(scope_table, map_rel)
        issues.extend(scope_issues)
        mode = "declared"

    topics, dependencies = _parse_topic_tables(topic_table, dependency_table, map_rel)

    return {
        "mode": mode,
        "map_path": map_rel,
        "format_version": marker,
        "map_format_supported": supported,
        "has_topic_table": topic_table is not None,
        "roots": roots,
        "include": include,
        "exclude": exclude,
        "topics": topics,
        "dependencies": dependencies,
        "map_document": document,
        "issues": issues,
    }


def _normalize_scope_path(entry):
    """Classify one scope entry as ``(rel, problem)``.

    ``./docs/x``, ``/docs/x``, ``docs/`` and ``docs/../docs/x`` all collapse to
    the same key so include and exclude entries compare consistently. ``rel`` is
    None when the entry is not usable, and ``problem`` then names the reason:
    an entry that escapes the root (``../docs``) or that is root-wide (``.``,
    ``/``) is never dropped silently, because a dropped rule would leave the
    caller believing an unbounded or invalid declaration had been applied.
    """
    text = _norm_rel(entry)
    if not text:
        return None, "scope_entry_root_wide"
    rel = _normalize_inside("", text)
    if rel is None:
        return None, "scope_entry_outside_root"
    if not rel:
        return None, "scope_entry_root_wide"
    return rel, None


def _covered(rel, include, roots, excludes):
    """True when ``rel`` is inside the declared scope and not excluded."""
    if not rel or _is_excluded(rel, excludes):
        return False
    return any(
        rel == entry or rel.startswith(entry + "/")
        for entry in list(include) + list(roots)
    )


def _scan_scope(root_real, scope):
    include = []
    roots = []
    excludes = []
    found = set()
    issues = []
    complete = True

    def scope_entry_issue(kind, raw, problem):
        """Report a declared scope entry that cannot be applied as written."""
        if problem == "scope_entry_root_wide":
            detail = (
                f"Scope {kind} entry is not a project-root-relative path and "
                f"was not applied: {raw}"
            )
        else:
            detail = (
                f"Scope {kind} entry escapes the project root and was not "
                f"applied: {raw}"
            )
        issues.append(_issue(problem, detail, "error", target=str(raw)))

    for raw in scope.get("include") or []:
        rel, problem = _normalize_scope_path(raw)
        if problem is not None:
            scope_entry_issue("include", raw, problem)
            complete = False
        elif rel:
            include.append(rel)
    for raw in scope.get("roots") or []:
        rel, problem = _normalize_scope_path(raw)
        if problem is not None:
            scope_entry_issue("root", raw, problem)
            complete = False
        elif rel:
            roots.append(rel)
    for raw in scope.get("exclude") or []:
        rel, problem = _normalize_scope_path(raw)
        if problem is not None:
            # An exclusion that cannot be applied must never disappear quietly.
            scope_entry_issue("exclude", raw, problem)
            complete = False
        elif rel:
            excludes.append(rel)

    def on_walk_error(error):
        nonlocal complete
        complete = False
        issues.append(_issue(
            "scan_incomplete",
            f"Directory could not be read: {getattr(error, 'filename', '')}: {error}",
            "warning", file=_rel_from_root(root_real, getattr(error, "filename", "")) or None,
        ))

    def symlink_target_allowed(rel):
        """A symlink is read only when its real target is itself in declared scope."""
        real = _real_inside(root_real, rel)
        if real is None:
            issues.append(_issue(
                "symlink_outside_root",
                f"Skipped a symlink that leaves the project root: {rel}",
                "warning", target=rel,
            ))
            return False
        canonical = real.relative_to(root_real).as_posix()
        if not _covered(canonical, include, roots, excludes):
            issues.append(_issue(
                "symlink_not_in_scope",
                f"Skipped a symlink whose target is outside the declared scope: {rel}",
                "warning", target=rel,
            ))
            return False
        return True

    entries = [(rel, "include") for rel in include] + [(rel, "root") for rel in roots]
    for rel, kind in entries:
        # Exclusion wins over an explicit include or root, including the default
        # service and secret directories.
        if _is_excluded(rel, excludes):
            issues.append(_issue(
                "scope_entry_excluded",
                f"Scope {kind} entry is excluded and was not read: {rel}",
                "warning", target=rel,
            ))
            continue
        if _real_inside(root_real, rel) is None:
            issues.append(_issue(
                "scope_entry_outside_root",
                f"Scope {kind} entry resolves outside the project root: {rel}",
                "error", target=rel,
            ))
            complete = False
            continue
        target = root_real / rel
        if not target.exists():
            # A root instruction router is "when present"; a missing include is
            # a diagnosable gap in the declared scope.
            if kind == "include":
                issues.append(_issue(
                    "scope_entry_missing",
                    f"Declared scope entry does not exist: {rel}",
                    "warning", target=rel,
                ))
            continue
        if target.is_dir():
            if kind == "root":
                issues.append(_issue(
                    "scope_entry_unsupported",
                    f"Scope root entry is not a file: {rel}",
                    "warning", target=rel,
                ))
                continue
            for dirpath, dirnames, filenames in os.walk(str(target), followlinks=False, onerror=on_walk_error):
                rel_dir = _rel_from_root(root_real, dirpath)
                kept = []
                for name in dirnames:
                    child = _join_rel(rel_dir, name)
                    if _is_excluded(child, excludes):
                        continue
                    if (Path(dirpath) / name).is_symlink():
                        # A symlinked directory is never followed; its files are
                        # already reachable through their real location.
                        real = _real_inside(root_real, child)
                        if real is None:
                            issues.append(_issue(
                                "symlink_outside_root",
                                f"Skipped a symlink that leaves the project root: {child}",
                                "warning", target=child,
                            ))
                        elif not _covered(real.relative_to(root_real).as_posix(),
                                          include, roots, excludes):
                            issues.append(_issue(
                                "symlink_not_in_scope",
                                f"Skipped a symlinked directory outside the declared scope: {child}",
                                "warning", target=child,
                            ))
                        continue
                    kept.append(name)
                dirnames[:] = sorted(kept)
                for name in sorted(filenames):
                    child = _join_rel(rel_dir, name)
                    if _is_excluded(child, excludes) or _suffix(name) not in MARKDOWN_SUFFIXES:
                        continue
                    path = Path(dirpath) / name
                    if path.is_symlink() and not symlink_target_allowed(child):
                        continue
                    if path.is_file():
                        found.add(child)
            continue
        if _suffix(target.name) not in MARKDOWN_SUFFIXES:
            if kind == "include":
                issues.append(_issue(
                    "scope_entry_unsupported",
                    f"Declared scope file is not Markdown: {rel}",
                    "warning", target=rel,
                ))
            continue
        if target.is_symlink() and not symlink_target_allowed(rel):
            continue
        found.add(rel)

    return sorted(found), complete, issues


def scan_scope(root, scope):
    """Return sorted project-root-relative Markdown paths inside ``scope``."""
    root_real = _root_path(root)
    paths, _, _ = _scan_scope(root_real, scope)
    return paths


# ---------------------------------------------------------------------------
# Link resolution
# ---------------------------------------------------------------------------


def _anchor_lookup(document, anchor):
    mapping = {}
    for index, heading in enumerate(document.get("headings") or []):
        name = heading.get("anchor")
        if name:
            mapping.setdefault(name, []).append(index)
        for alias in heading.get("aliases") or []:
            mapping.setdefault(alias, []).append(index)
    for alias in document.get("preamble_anchors") or []:
        mapping.setdefault(alias, []).append(-1)

    targets = mapping.get(anchor)
    if not targets:
        return None, "anchor_missing"
    distinct = sorted(set(targets))
    if len(distinct) > 1:
        return None, "anchor_collision"
    return distinct[0], None


def resolve_link(source_document, raw_target, index=None, root=None):
    """Resolve one link target relative to its source document.

    Returns a dict with ``target``, ``anchor``, ``resolved``, ``code``,
    ``severity``, ``message`` and ``candidates``. Never reads a file.
    """
    if root is None and isinstance(index, dict):
        root = index.get("root")
    if root is None and index is None:
        raise ValueError("resolve_link requires root or index context")
    root_real = Path(root).resolve() if root is not None else None

    source_rel = _norm_rel((source_document or {}).get("path", ""))
    raw = _strip_ticks(raw_target or "").strip()
    result = {
        "target": None,
        "anchor": None,
        "resolved": False,
        "code": None,
        "severity": None,
        "message": "",
        "candidates": [],
    }
    if raw.startswith("<") and raw.endswith(">") and len(raw) > 1:
        raw = raw[1:-1]

    scheme_match = SCHEME_RE.match(raw)
    if scheme_match:
        scheme = scheme_match.group(0)[:-1].lower()
        result["target"] = raw
        if scheme in UNSAFE_SCHEMES:
            result["code"] = "unsafe_link_scheme"
            result["message"] = f"Unsafe link scheme is not followed: {raw}"
        else:
            result["code"] = "external_link_not_fetched"
            result["message"] = f"External URL was not fetched: {raw}"
        result["severity"] = ISSUE_SEVERITY.get(result["code"], "info")
        return result
    if raw.startswith("//"):
        result["target"] = raw
        result["code"] = "external_link_not_fetched"
        result["message"] = f"External URL was not fetched: {raw}"
        result["severity"] = "info"
        return result

    path_part, _, anchor = raw.partition("#")
    anchor = unquote(anchor) if anchor else None
    path_part = unquote(path_part)
    result["anchor"] = anchor

    if path_part == "":
        target = source_rel
    else:
        base = posixpath.dirname(source_rel)
        target = _normalize_inside(base, path_part)
    if target is None:
        result["code"] = "link_outside_root"
        result["message"] = f"Link leaves the project root: {raw}"
        result["severity"] = "error"
        return result
    result["target"] = target

    known = {}
    if isinstance(index, dict):
        for document in index.get("documents") or []:
            known[str(document.get("path"))] = document

    is_markdown = _suffix(target) in MARKDOWN_SUFFIXES
    if root_real is not None and _real_inside(root_real, target) is None:
        result["code"] = "link_outside_root"
        result["message"] = f"Link resolves through a symlink leaving the project root: {raw}"
        result["severity"] = "error"
        return result

    exists = False
    is_dir = False
    if root_real is not None:
        candidate = root_real / target
        is_dir = candidate.is_dir()
        exists = candidate.exists()

    if is_markdown and target in known:
        target_document = known[target]
        if anchor:
            heading_index, code = _anchor_lookup(target_document, anchor)
            if code == "anchor_missing":
                result["code"] = "anchor_missing"
                result["severity"] = "error"
                result["message"] = f"Anchor {anchor} does not exist in {target}"
                result["candidates"] = _candidates(target_document)
                return result
            if code == "anchor_collision":
                result["code"] = "anchor_collision"
                result["severity"] = "error"
                result["message"] = f"Anchor {anchor} is ambiguous in {target}"
                result["candidates"] = _candidates(target_document)
                return result
            result["resolved"] = True
            result["heading"] = heading_index
            return result
        result["resolved"] = True
        return result

    if not exists:
        result["code"] = "link_target_missing"
        result["severity"] = "error"
        result["message"] = f"Link target does not exist: {target}"
        return result
    if is_dir:
        result["code"] = "link_target_directory"
        result["severity"] = "error"
        result["message"] = f"Link target is a directory, not a document: {target}"
        return result
    if is_markdown:
        result["code"] = "link_out_of_scope"
        result["severity"] = "warning"
        result["message"] = f"Document link is outside the scanned scope: {target}"
        return result
    # A non-Markdown resource inside the root may be stat-checked but not read.
    result["resolved"] = True
    return result


def _link_issue(resolution, document, link):
    return _issue(
        resolution["code"],
        resolution["message"],
        ISSUE_SEVERITY.get(resolution["code"], "warning"),
        file=document.get("path"),
        line=link.get("line"),
        section=_section_title(document, link.get("line")),
        target=resolution.get("target") or link.get("raw"),
        candidates=resolution.get("candidates") or None,
    )


def _section_title(document, line):
    if not isinstance(line, int):
        return None
    current = None
    for heading in document.get("headings") or []:
        if heading.get("line_start") is not None and heading["line_start"] <= line:
            current = heading.get("text")
        else:
            break
    return current


# ---------------------------------------------------------------------------
# Build index
# ---------------------------------------------------------------------------


def build_index(root, map_path=DEFAULT_MAP_PATH, scope=None):
    """Build the derived documentation index for ``root``.

    Raises FileNotFoundError when the map is missing. When no scope is passed it
    is resolved from the map; a pre-resolved scope is reused as-is.
    """
    root_real = _root_path(root)
    if scope is None:
        scope = resolve_scope(root_real, map_path)

    map_rel = _norm_rel(scope.get("map_path") or map_path)
    issues = list(scope.get("issues") or [])
    excluded_entries = []
    for raw in scope.get("exclude") or []:
        rel, _problem = _normalize_scope_path(raw)
        if rel:
            excluded_entries.append(rel)
    if map_rel and _is_excluded(map_rel, excluded_entries):
        # The map is canonical and always read, but a scope table that excludes
        # its own map must say so instead of silently disagreeing.
        issues.append(_issue(
            "map_excluded_by_scope",
            f"The canonical map matches a scope exclude entry and is still read as the map: {map_rel}",
            "warning", file=map_rel,
        ))
    scope_paths, traversal_complete, scan_issues = _scan_scope(root_real, scope)
    issues.extend(scan_issues)

    paths = set(scope_paths)
    if map_rel and (root_real / map_rel).is_file():
        paths.add(map_rel)

    map_document = scope.get("map_document")
    documents = []
    for rel in sorted(paths):
        if (rel == map_rel and isinstance(map_document, dict)
                and str(map_document.get("path")) == map_rel):
            documents.append(copy.deepcopy(map_document))
            continue
        document = parse_document(root_real / rel, root=root_real, rel_path=rel)
        issues.extend(document.pop("issues", []))
        documents.append(document)

    index = {
        "schema_version": SCHEMA_VERSION,
        "format_version": scope.get("format_version"),
        "map_path": map_rel,
        "scope_mode": scope.get("mode", "declared"),
        "scan_complete": True,
        "traversal_complete": bool(traversal_complete),
        "source_fingerprint": "",
        "root": str(root_real),
        "map_format_supported": bool(scope.get("map_format_supported", True)),
        "has_topic_table": bool(scope.get("has_topic_table", False)),
        "scope": {
            "roots": list(scope.get("roots") or []),
            "include": list(scope.get("include") or []),
            "exclude": list(scope.get("exclude") or []),
        },
        "documents": documents,
        "topics": list(scope.get("topics") or []),
        "dependencies": list(scope.get("dependencies") or []),
        "format_issues": [],
    }

    for document in documents:
        for link in document.get("links") or []:
            resolution = resolve_link(document, link.get("raw", ""), index=index, root=root_real)
            link["target"] = resolution.get("target")
            link["anchor"] = resolution.get("anchor")
            link["resolved"] = bool(resolution.get("resolved"))
            if resolution.get("code"):
                issues.append(_link_issue(resolution, document, link))

    index["scan_complete"] = bool(traversal_complete) and all(
        bool(document.get("parse_complete")) for document in documents
    )
    index["format_issues"] = _sort_issues(issues)
    index["source_fingerprint"] = fingerprint(index)
    return index


def _sort_issues(entries):
    seen = set()
    result = []
    for entry in sorted(
        entries,
        key=lambda item: (
            str(item.get("file") or ""),
            item.get("line") if isinstance(item.get("line"), int) else -1,
            str(item.get("code") or ""),
            str(item.get("target") or ""),
            str(item.get("message") or ""),
        ),
    ):
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


# ---------------------------------------------------------------------------
# Section ranges
# ---------------------------------------------------------------------------


def _document_by_path(index, rel_path):
    wanted = _norm_rel(rel_path)
    for document in (index or {}).get("documents") or []:
        if _norm_rel(document.get("path")) == wanted:
            return document
    return None


def _section_failure(path, anchor, code, message, candidates=None, preamble=None):
    return {
        "ok": False,
        "code": code,
        "path": path,
        "anchor": anchor,
        "title": None,
        "level": None,
        "start": None,
        "end": None,
        "line_start": None,
        "line_end": None,
        "parents": [],
        "ancestors": [],
        "intro": [],
        "preamble": preamble,
        "candidates": candidates or [],
        "text": "",
        "truncated": False,
        "message": message,
    }


def _preamble_of(document):
    headings = document.get("headings") or []
    if not headings or headings[0].get("line_start") is None or headings[0]["line_start"] <= 1:
        return None
    end = headings[0]["line_start"] - 1
    lines = str(document.get("text", "")).split("\n")
    return {
        "text": "\n".join(lines[:end]),
        "line_start": 1,
        "line_end": end,
    }


def section_range(document, anchor, target=None):
    """Return the range of one section.

    Two call shapes are accepted, with identical behaviour:

    * ``section_range(document, anchor)`` - canonical, per
      ``references/documentation-format.md``;
    * ``section_range(index, document_path, anchor)`` - kept so an existing CLI
      call site keeps working until it moves to the canonical shape.

    A missing or ambiguous anchor returns ``ok: False`` with candidates; the
    first similar section is never substituted.
    """
    if target is not None:
        index, rel_path, anchor = document, anchor, target
        resolved_document = _document_by_path(index, rel_path)
        if resolved_document is None:
            return _section_failure(
                _norm_rel(rel_path), anchor, "document_missing",
                f"Document is not part of the scanned scope: {rel_path}",
            )
        document = resolved_document

    path = _norm_rel((document or {}).get("path", ""))
    anchor = "" if anchor is None else str(anchor)
    preamble = _preamble_of(document or {})
    headings = (document or {}).get("headings") or []

    if not anchor:
        return _section_failure(path, anchor, "anchor_missing",
                                f"Anchor is empty in {path}", _candidates(document or {}), preamble)

    heading_index, code = _anchor_lookup(document or {}, anchor)
    if code == "anchor_missing":
        return _section_failure(path, anchor, "anchor_missing",
                                f"Anchor '{anchor}' was not found in {path}",
                                _candidates(document or {}), preamble)
    if code == "anchor_collision":
        return _section_failure(path, anchor, "anchor_collision",
                                f"Anchor '{anchor}' names more than one section in {path}",
                                _candidates(document or {}), preamble)

    text = str(document.get("text", ""))
    lines = text.split("\n")
    total_lines = _line_count(text)

    if heading_index == -1:
        end = (headings[0]["line_start"] - 1) if headings else total_lines
        end = max(end, 0)
        text = "\n".join(lines[:end])
        return {
            "ok": True,
            "code": None,
            "path": path,
            "anchor": anchor,
            "title": None,
            "level": 0,
            "start": 1,
            "end": end,
            "line_start": 1,
            "line_end": end,
            "parents": [],
            "ancestors": [],
            "intro": [],
            "preamble": {"text": text, "line_start": 1, "line_end": end},
            "candidates": [],
            "text": text,
            "truncated": False,
        }

    heading = headings[heading_index]
    level = int(heading.get("level") or 1)
    start = int(heading.get("line_start") or 1)
    end = total_lines
    for other in headings[heading_index + 1:]:
        if int(other.get("level") or 1) <= level:
            end = int(other.get("line_start") or 1) - 1
            break
    end = max(end, start)

    stack = []
    for candidate in headings[:heading_index + 1]:
        candidate_level = int(candidate.get("level") or 1)
        while stack and int(stack[-1].get("level") or 1) >= candidate_level:
            stack.pop()
        if candidate is not heading:
            stack.append(candidate)
    ancestors = [
        {
            "text": item.get("text", ""),
            "anchor": item.get("anchor", ""),
            "level": item.get("level"),
            "line_start": item.get("line_start"),
        }
        for item in stack
    ]

    intro_end = end
    for other in headings[heading_index + 1:]:
        if int(other.get("level") or 1) > level:
            intro_end = int(other.get("line_start") or 1) - 1
            break
    intro_end = max(intro_end, start)
    intro = [line for line in lines[start:intro_end]]

    return {
        "ok": True,
        "code": None,
        "path": path,
        "anchor": anchor,
        "title": heading.get("text", ""),
        "level": level,
        "start": start,
        "end": end,
        "line_start": start,
        "line_end": end,
        "parents": ancestors,
        "ancestors": ancestors,
        "intro": intro,
        "preamble": preamble,
        "candidates": [],
        "text": "\n".join(lines[start - 1:end]),
        "truncated": False,
    }


# ---------------------------------------------------------------------------
# Coverage, fingerprints, serialization
# ---------------------------------------------------------------------------


def owner_coverage(index):
    if not (index or {}).get("map_format_supported", True):
        return "not_evaluated"
    if (index or {}).get("scope_mode") == "bootstrap":
        return "not_evaluated"
    if not (index or {}).get("has_topic_table"):
        return "not_evaluated"
    return "evaluated"


def fingerprint(index):
    """Return the sha256 source fingerprint over text, scope, inventory and map tables."""
    digest = hashlib.sha256()
    digest.update(b"context-cartographer/documentation-index/v1\n")
    digest.update(str((index or {}).get("map_path", "")).encode("utf-8"))
    digest.update(b"\n")
    digest.update(str((index or {}).get("scope_mode", "")).encode("utf-8"))
    digest.update(b"\n")
    scope = (index or {}).get("scope") or {}
    for key in ("roots", "include", "exclude"):
        digest.update(key.encode("ascii"))
        digest.update(b"\n")
        for value in scope.get(key) or []:
            digest.update(str(value).encode("utf-8"))
            digest.update(b"\0")
    for document in sorted((index or {}).get("documents") or [], key=lambda item: str(item.get("path", ""))):
        digest.update(str(document.get("path", "")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(document.get("fingerprint", "")).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(str(document.get("text", "")).encode("utf-8")).hexdigest().encode("ascii"))
        digest.update(b"\0")
    for topic in (index or {}).get("topics") or []:
        digest.update(json.dumps(topic, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
    for dependency in (index or {}).get("dependencies") or []:
        digest.update(json.dumps(dependency, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def to_json(index):
    """Return a JSON-ready copy with stable ordering."""
    documents = []
    for document in sorted((index or {}).get("documents") or [], key=lambda item: str(item.get("path", ""))):
        headings = [
            {
                "text": heading.get("text", ""),
                "anchor": heading.get("anchor", ""),
                "level": heading.get("level"),
                "line_start": heading.get("line_start"),
                "line_end": heading.get("line_end"),
                "aliases": list(heading.get("aliases") or []),
            }
            for heading in sorted(
                document.get("headings") or [],
                key=lambda item: (item.get("line_start") or 0, item.get("level") or 0),
            )
        ]
        links = [
            {
                "text": link.get("text", ""),
                "raw": link.get("raw", ""),
                "target": link.get("target"),
                "anchor": link.get("anchor"),
                "resolved": bool(link.get("resolved")),
                "line": link.get("line"),
                "kind": link.get("kind", "link"),
            }
            for link in sorted(document.get("links") or [], key=lambda item: item.get("line") or 0)
        ]
        documents.append({
            "path": document.get("path"),
            "title": document.get("title", ""),
            "area": document.get("area", ""),
            "text": document.get("text", ""),
            "fingerprint": document.get("fingerprint", ""),
            "parse_complete": bool(document.get("parse_complete", True)),
            "headings": headings,
            "links": links,
            "preamble_anchors": list(document.get("preamble_anchors") or []),
        })

    topics = [
        {
            "id": topic.get("id", ""),
            "purpose": topic.get("purpose", ""),
            "owner": topic.get("owner", ""),
            "read_when": topic.get("read_when", ""),
            "file": topic.get("file"),
            "line": topic.get("line"),
        }
        for topic in (index or {}).get("topics") or []
    ]
    dependencies = [
        {
            "topic": dependency.get("topic", ""),
            "depends_on": list(dependency.get("depends_on") or []),
            "reason": dependency.get("reason", ""),
            "file": dependency.get("file"),
            "line": dependency.get("line"),
        }
        for dependency in (index or {}).get("dependencies") or []
    ]
    issues = []
    for entry in _sort_issues((index or {}).get("format_issues") or []):
        item = {
            "severity": entry.get("severity", "warning"),
            "code": entry.get("code", "format_issue"),
            "file": entry.get("file"),
            "line": entry.get("line"),
            "section": entry.get("section"),
            "target": entry.get("target"),
            "message": entry.get("message", ""),
        }
        if entry.get("candidates"):
            item["candidates"] = list(entry["candidates"])
        issues.append(item)

    scope = (index or {}).get("scope") or {}
    return {
        "schema_version": (index or {}).get("schema_version", SCHEMA_VERSION),
        "format_version": (index or {}).get("format_version"),
        "map_path": (index or {}).get("map_path", DEFAULT_MAP_PATH),
        "scope_mode": (index or {}).get("scope_mode", "declared"),
        "scan_complete": bool((index or {}).get("scan_complete", False)),
        "traversal_complete": bool((index or {}).get("traversal_complete", False)),
        "source_fingerprint": (index or {}).get("source_fingerprint", ""),
        "root": (index or {}).get("root", ""),
        "map_format_supported": bool((index or {}).get("map_format_supported", True)),
        "has_topic_table": bool((index or {}).get("has_topic_table", False)),
        "scope": {
            "roots": list(scope.get("roots") or []),
            "include": list(scope.get("include") or []),
            "exclude": list(scope.get("exclude") or []),
        },
        "documents": documents,
        "topics": topics,
        "dependencies": dependencies,
        "format_issues": issues,
    }
