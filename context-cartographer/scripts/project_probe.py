#!/usr/bin/env python3
"""Bounded folder-state probe for context-cartographer (implementation plan 04-02).

Answer one question before any idea work starts: what is already inside the
selected folder? The helper is deliberately small and honest.

Design rules:

* Python standard library only; no network, no browser, no subprocess, no
  dependency installation, no ``git`` execution.
* Read-only: nothing is created, deleted, cached or written. In particular the
  helper never runs ``git init`` just to improve a diagnosis.
* A bounded walk of the selected root. Hidden and Git-ignored entries count; no
  ignore rules and no ``rg --files`` filtering are used, so a file that Git
  hides is still seen here.
* Secret material is never read. ``.env``, secret-looking files and sensitive
  directories such as ``.ssh`` are reported by path and kind only.
* Child symlinks are never followed, not even ones that stay inside the root,
  so a link can not pull content from outside the selected scope. The selected
  root's own path is resolved once because the user chose it explicitly.
* Completion is explicit. ``scan_complete`` is true only when the whole walk
  finished and every discovered document was inspected. A cut-short walk, an
  unreadable directory or entry, an unreadable document and the document-read
  cap each leave a diagnostic and turn any non-``existing`` answer into
  ``unknown``.
* The classification is a clear, limited structural heuristic, not semantic
  understanding. When evidence is missing, contradictory or cut short by a
  limit, the result is ``unknown`` rather than a confident ``empty``.
* The selected root is the target. An enclosing Git root is reported for
  context only and never replaces the folder the user chose.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections import deque


__all__ = [
    "CLASSIFICATIONS",
    "DIAGNOSTIC_CODES",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_IDENTITY_BYTES",
    "SCHEMA_VERSION",
    "main",
    "probe_project",
]

SCHEMA_VERSION = 1

CLASSIFICATIONS = ("empty", "scaffold", "brief_only", "existing", "unknown")

DIAGNOSTIC_CODES = (
    "root_missing",
    "root_not_directory",
    "root_unreadable",
    "directory_unreadable",
    "entry_unreadable",
    "document_unreadable",
    "entry_limit_reached",
    "depth_limit_reached",
    "content_limit_reached",
    "document_read_limit_reached",
    "symlink_not_followed",
    "no_decision_evidence",
)

DEFAULT_MAX_ENTRIES = 5000
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_IDENTITY_BYTES = 8192

# Version-control and OS metadata: never descended into, never counted as user
# content. A folder that holds only this material stays "empty".
METADATA_DIRS = frozenset({".git", ".hg", ".svn", ".bzr", "_darcs", ".fossil"})
# A version-control entry is metadata whether it is a directory or a plain
# file. Git worktrees and submodule checkouts store a ``.git`` file holding
# ``gitdir: ...``; it is reported by name only and the pointer target is never
# read. ``.DS_Store`` and friends are operating-system metadata.
METADATA_FILE_NAMES = frozenset(
    {".ds_store", "thumbs.db", "desktop.ini", ".localized"}
)

# Regenerable tool caches. Named in the report, never descended into, so the
# entry budget is spent on user content rather than on bytecode and caches.
CACHE_DIR_NAMES = frozenset(
    {
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
        ".nox", ".hypothesis", ".ipynb_checkpoints", ".cache", ".sass-cache",
    }
)

# Credential stores and other sensitive areas. The folder itself is reported so
# the caller knows it exists, but its contents are never listed or read.
SENSITIVE_DIR_NAMES = frozenset(
    {
        ".ssh", ".aws", ".gnupg", ".gcloud", ".kube", ".secrets", ".private",
        ".password-store", ".pki", ".env.d", "credentials", "secrets", "keyrings",
    }
)

# Boilerplate that signals a scaffold, not a product.
SCAFFOLD_FILE_NAMES = frozenset(
    {
        "license",
        "license.txt",
        "license.md",
        "licence",
        "licence.txt",
        "licence.md",
        "copying",
        "copying.txt",
        "copyright",
        "notice",
        "notice.txt",
        "notice.md",
        "authors",
        "contributors",
        "contributing.md",
        "code_of_conduct.md",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        ".gitkeep",
        ".keep",
        ".editorconfig",
        ".npmignore",
        ".dockerignore",
        ".eslintignore",
        ".prettierignore",
        ".mailmap",
        "changelog.md",
        "changes.md",
        "codeowners",
        ".codeowners",
    }
)
SCAFFOLD_SUFFIXES = (".license", ".licence")

# Source code: real implementation.
CODE_SUFFIXES = frozenset(
    {
        ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".m", ".mm",
        ".cs", ".java", ".kt", ".kts", ".scala", ".groovy", ".go", ".rs",
        ".swift", ".dart", ".py", ".pyi", ".rb", ".rake", ".php", ".pl", ".pm",
        ".lua", ".r", ".jl", ".ex", ".exs", ".erl", ".hrl", ".hs", ".lhs",
        ".clj", ".cljs", ".fs", ".fsx", ".vb", ".pas", ".asm", ".s", ".f",
        ".f90", ".f95", ".for", ".cob", ".tcl", ".tf", ".vue", ".svelte",
        ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".coffee",
        ".sh", ".bash", ".zsh", ".fish", ".ksh", ".ps1", ".psm1", ".bat", ".cmd",
        ".sql", ".graphql", ".gql", ".proto", ".thrift", ".ipynb",
        # Static web sources and templates are implementation for a static
        # site: markup, stylesheets and the templates that build them.
        ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less", ".styl",
        ".jinja", ".jinja2", ".j2", ".twig", ".liquid", ".njk", ".hbs",
        ".handlebars", ".ejs", ".mustache", ".erb",
    }
)
CODE_FILE_NAMES = frozenset(
    {
        "makefile", "gnumakefile", "cmakelists.txt", "rakefile", "gemfile",
        "justfile", "procfile", "build.gradle", "build.gradle.kts", "pom.xml",
        "gradlew", "mvnw",
    }
)

# Config describes a product that already exists; treated conservatively.
CONFIG_SUFFIXES = frozenset(
    {
        ".toml", ".ini", ".cfg", ".conf", ".properties", ".env", ".xml",
        ".yml", ".yaml", ".json", ".json5", ".hcl", ".tfvars", ".nix",
        ".plist", ".service", ".desktop", ".cmake", ".mk", ".lock", ".npmrc",
        ".babelrc", ".eslintrc",
    }
)
CONFIG_FILE_NAMES = frozenset(
    {
        "dockerfile", "containerfile", "docker-compose.yml",
        "docker-compose.yaml", "compose.yml", "compose.yaml",
        "package.json", "pyproject.toml", "setup.py", "setup.cfg",
        "requirements.txt", "requirements-dev.txt", "composer.json",
        "tsconfig.json", "webpack.config.js", "vite.config.ts",
        "nginx.conf", "caddyfile", ".env", ".env.local", ".env.example",
        ".env.sample", ".env.template", ".envrc", "gemfile.lock",
        "poetry.lock", "uv.lock", ".tool-versions",
    }
)
CONFIG_NAME_PREFIXES = ("dockerfile.", "compose.", "docker-compose.")
# ``requirements*.txt`` and ``requirements*.in`` are Python dependency
# manifests, so they stay configuration (see ``_is_config_name``). Written
# requirements belong in ``requirements.md`` / ``requirements.rst``.
REQUIREMENTS_MANIFEST_RE = re.compile(r"^requirements[\w.-]*\.(?:txt|in)$")

# Data, key material and build output that a product owns.
DATA_SUFFIXES = frozenset(
    {
        ".csv", ".tsv", ".parquet", ".feather", ".arrow", ".orc", ".avro",
        ".sqlite", ".sqlite3", ".db", ".mdb", ".accdb", ".dump", ".bak",
        ".xlsx", ".xls", ".ods", ".sav", ".dta", ".rds", ".rdata", ".h5",
        ".hdf5", ".npz", ".npy", ".pkl", ".pickle", ".bin", ".dat", ".ndjson",
        ".jsonl", ".pem", ".key", ".crt", ".cer", ".p12", ".pfx",
    }
)
DATA_DIR_NAMES = frozenset(
    {
        "data", "dataset", "datasets", "db", "database", "databases",
        "fixtures", "samples", "sample-data", "seed", "seeds", "migrations",
        "migration", "backups", "backup", "snapshots", "excel", "tables",
    }
)
BUILD_DIR_NAMES = frozenset(
    {
        "build", "dist", "out", "output", "target", "bin", "obj", "release",
        "debug", "artifacts", "artifact", "coverage", "site-packages",
        "node_modules", "vendor", "bower_components", "wheelhouse",
        "deriveddata", ".next", ".nuxt", ".output", ".parcel-cache",
        ".turbo", ".svelte-kit", "storybook-static",
    }
)

# Files whose bounded content tells us whether a written idea already exists.
# ``requirements.md`` / ``requirements.rst`` are written documents; the
# dependency manifests ``requirements*.txt`` stay configuration, so they are
# deliberately absent here.
IDENTITY_FILE_NAMES = frozenset(
    {
        "readme", "readme.md", "readme.rst", "readme.txt", "readme.markdown",
        "readme.mdx", "agents.md", "claude.md", "codex.md", "gemini.md",
        "cursor.md", ".cursorrules", ".windsurfrules", "idea.md", "ideas.md",
        "concept.md", "vision.md", "brief.md", "spec.md", "specification.md",
        "design.md", "requirements.md", "requirements.rst",
        "plan.md", "roadmap.md", "tz.md",
    }
)
IDENTITY_NAME_PREFIXES = (
    "readme.", "idea.", "ideas.", "brief.", "spec.", "concept.", "vision.",
    "requirements.",
)
DOCUMENT_SUFFIXES = frozenset(
    {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc", ".org"}
)

# Manifests that make a subdirectory its own component.
MANIFEST_NAMES = frozenset(
    {
        "package.json", "pyproject.toml", "setup.py", "cargo.toml", "go.mod",
        "composer.json", "gemfile", "build.gradle", "build.gradle.kts",
        "pom.xml", "pubspec.yaml", "mix.exs", "requirements.txt",
    }
)

# Mockups and wireframes are design intent, not implementation.
MOCKUP_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".fig", ".xd",
     ".sketch", ".psd", ".ai", ".afdesign", ".drawio", ".excalidraw"}
)
MOCKUP_NAME_TOKENS = (
    "mockup", "mock-up", "wireframe", "wireframes", "mock", "prototype",
    "screen", "screens",
)
MOCKUP_DIR_TOKENS = (
    "mockup", "mockups", "wireframe", "wireframes", "design", "designs",
    "ui", "ux", "screens", "flows", "prototype", "assets",
)

# A document must carry this many alphanumeric characters outside headings,
# punctuation and fences before it counts as a written idea rather than a stub.
MIN_IDENTITY_ALNUM = 60

# Bounded number of document bodies inspected per probe.
MAX_DOCUMENT_READS = 256

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
MARKDOWN_NOISE_RE = re.compile(r"[#>*_`~|\-\[\]()!:+=\s]+")
ALNUM_RE = re.compile(r"[0-9A-Za-z\u0410-\u044f\u0401\u0451]")

_SECRET_NAME_RE = re.compile(
    r"(^|[._-])(secret|secrets|credential|credentials|password|passwd|"
    r"token|tokens|apikey|api[-_]key|private[-_]?key|id_rsa|id_ed25519|"
    r"keystore|htpasswd|netrc)([._-]|$)"
)

# Kinds that prove a product already exists.
EXISTING_KINDS = frozenset({"code", "config", "data", "secret"})
# Kinds that only describe structure or boilerplate.
STRUCTURE_KINDS = frozenset({"scaffold", "dir", "metadata"})

# Basis is bounded per kind so a large tree can not bloat the report.
BASIS_KIND_ORDER = (
    "code", "component", "config", "data", "secret", "mockup", "document",
    "symlink", "scaffold", "dir", "other", "metadata",
)
BASIS_PER_KIND_CAP = 6
BASIS_TOTAL_CAP = 48


class _Entry:
    """One observed filesystem entry. Not exported; only its fields are used."""

    __slots__ = (
        "rel", "name", "kind", "depth", "size", "substantive", "reason",
        "is_dir", "is_symlink",
    )

    def __init__(self, rel, name, kind, depth, size=None, substantive=False,
                 reason="", is_dir=False, is_symlink=False):
        self.rel = rel
        self.name = name
        self.kind = kind
        self.depth = depth
        self.size = size
        self.substantive = substantive
        self.reason = reason
        self.is_dir = is_dir
        self.is_symlink = is_symlink


def _diag(code, message, path=None):
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


# --------------------------------------------------------------------------
# Pure name classification helpers (no I/O).


def _suffix(lower):
    _stem, dot, suffix = lower.rpartition(".")
    return ("." + suffix) if dot else ""


def _is_secret_name(lower):
    if lower == ".env":
        return True
    if lower.startswith(".env.") and not lower.endswith(
        (".example", ".sample", ".template")
    ):
        return True
    return bool(_SECRET_NAME_RE.search(lower))


def _is_identity_name(lower):
    if lower in IDENTITY_FILE_NAMES:
        return True
    return any(lower.startswith(prefix) for prefix in IDENTITY_NAME_PREFIXES)


def _is_scaffold_name(lower):
    return lower in SCAFFOLD_FILE_NAMES or lower.endswith(SCAFFOLD_SUFFIXES)


def _is_code_name(lower):
    return lower in CODE_FILE_NAMES or _suffix(lower) in CODE_SUFFIXES


def _is_config_name(lower):
    if lower in CONFIG_FILE_NAMES:
        return True
    if REQUIREMENTS_MANIFEST_RE.match(lower):
        # A dependency manifest describes an existing product, so it counts as
        # configuration. This is the documented policy for the ambiguous name:
        # ``requirements.md``/``requirements.rst`` carry written requirements,
        # ``requirements*.txt``/``*.in`` carry pinned dependencies.
        return True
    if any(lower.startswith(prefix) for prefix in CONFIG_NAME_PREFIXES):
        return True
    return _suffix(lower) in CONFIG_SUFFIXES


def _is_data_name(lower):
    return _suffix(lower) in DATA_SUFFIXES


def _is_image_name(lower):
    return _suffix(lower) in MOCKUP_SUFFIXES


def _is_mockup_name(lower):
    if not _is_image_name(lower):
        return False
    return any(token in lower for token in MOCKUP_NAME_TOKENS)


def _mockup_dir_context(parent_parts):
    return any(part.lower() in MOCKUP_DIR_TOKENS for part in parent_parts)


def _classify_file(name, parent_parts):
    """Return ``(kind, reason)`` for a regular file. Pure, no I/O."""
    lower = name.lower()
    if lower in METADATA_DIRS:
        # A ``.git``/``.hg``/... entry may be a plain file (worktree or
        # submodule pointer). It is metadata, not an unrecognized file, and its
        # contents are never read.
        return "metadata", "version-control metadata"
    if lower in METADATA_FILE_NAMES:
        return "metadata", "operating-system metadata"
    if _is_secret_name(lower):
        return "secret", "secret-looking name; content is never read"
    if _is_scaffold_name(lower):
        return "scaffold", "boilerplate file, no product"
    if _is_config_name(lower):
        return "config", "product configuration"
    if _is_data_name(lower):
        return "data", "product data or key material"
    if _is_code_name(lower):
        return "code", "source code"
    if _is_mockup_name(lower) or (
        _mockup_dir_context(parent_parts) and _is_image_name(lower)
    ):
        return "mockup", "mockup or wireframe"
    if _is_identity_name(lower) or lower.endswith(tuple(DOCUMENT_SUFFIXES)):
        return "document", "written document"
    if _is_image_name(lower):
        return "mockup", "image asset"
    return "other", "unrecognized file"


def _classify_dir(name):
    lower = name.lower()
    if lower in METADATA_DIRS:
        return "metadata", "version-control metadata"
    if lower in CACHE_DIR_NAMES:
        return "metadata", "regenerable tool cache"
    if lower in SENSITIVE_DIR_NAMES:
        return "secret", "sensitive directory; content is never read"
    if lower in DATA_DIR_NAMES:
        return "data", "data directory"
    if lower in BUILD_DIR_NAMES:
        return "code", "build or dependency directory"
    return "dir", "directory"


# --------------------------------------------------------------------------
# Bounded, read-only filesystem work.


def _read_bounded(path, max_bytes):
    """Read at most ``max_bytes`` without following a symlink. Never writes."""
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    fd = os.open(path, flags)
    try:
        return os.read(fd, max_bytes + 1), os.fstat(fd).st_size
    finally:
        os.close(fd)


def _is_substantive(text):
    """Structural heuristic for "worth reading", not a semantic judgement."""
    body = "\n".join(
        line for line in text.splitlines() if not HEADING_RE.match(line)
    )
    return len(ALNUM_RE.findall(MARKDOWN_NOISE_RE.sub(" ", body))) >= MIN_IDENTITY_ALNUM


def _inspect_document(path, rel, max_bytes, diagnostics):
    """Bounded read of one document.

    Returns ``(substantive, reason, size, complete)``. A truncated read can
    still provide classification evidence, but it is never a complete
    inspection.

    The content is inspected to classify the document and is never returned, so
    a caller can not accidentally echo a file body. Raises ``OSError`` when the
    document can not be read; the caller turns that into an explicit diagnostic
    and an incomplete inspection instead of a confident answer.
    """
    raw, size = _read_bounded(path, max_bytes)
    complete = size <= max_bytes and len(raw) <= max_bytes
    if not complete:
        diagnostics.append(
            _diag(
                "content_limit_reached",
                "document truncated at {} bytes for a bounded read".format(max_bytes),
                rel,
            )
        )
        raw = raw[:max_bytes]
    if not raw:
        return False, "empty written document", size, complete
    text = raw.decode("utf-8", "replace")
    if _is_substantive(text):
        return True, "substantive written content", size, complete
    return False, "stub without substantive content", size, complete


def _selected_scope(root):
    """Resolve folder scope without mutating it. Returns ``(info, problem)``.

    ``root`` keeps the caller's spelling. ``resolved_root`` is the canonical
    path actually walked: the explicitly selected root is resolved once, since
    the user chose it, while nothing below it is ever followed.
    """
    root_abs = os.path.abspath(root)
    info = {
        "root": root_abs,
        "resolved_root": root_abs,
        "exists": False,
        "is_dir": False,
        "readable": False,
        "is_git_repo": False,
        "git_entry": None,
        "enclosing_git_root": None,
        "ancestor_instruction_files": [],
    }
    try:
        st = os.stat(root_abs)
    except FileNotFoundError:
        return info, _diag("root_missing", "selected root does not exist", root_abs)
    except NotADirectoryError:
        return info, _diag(
            "root_not_directory", "selected root is not a directory", root_abs
        )
    except PermissionError:
        return info, _diag(
            "root_unreadable", "selected root is not readable", root_abs
        )
    except OSError as exc:
        return info, _diag(
            "root_unreadable",
            "selected root could not be inspected: {}".format(exc.strerror or exc),
            root_abs,
        )

    info["exists"] = True
    if not stat.S_ISDIR(st.st_mode):
        return info, _diag(
            "root_not_directory", "selected root is not a directory", root_abs
        )
    info["is_dir"] = True
    if not os.access(root_abs, os.R_OK | os.X_OK):
        return info, _diag(
            "root_unreadable", "selected root is not readable", root_abs
        )
    info["readable"] = True

    resolved = os.path.realpath(root_abs)
    info["resolved_root"] = resolved

    if os.path.lexists(os.path.join(resolved, ".git")):
        info["is_git_repo"] = True
        info["git_entry"] = ".git"

    info["enclosing_git_root"] = _find_enclosing_git_root(resolved)
    info["ancestor_instruction_files"] = _instruction_files(resolved)
    return info, None


def _find_enclosing_git_root(root_abs):
    current = os.path.dirname(root_abs)
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _instruction_files(root_abs, limit=8):
    found = []
    current = root_abs
    for _step in range(limit):
        for name in ("AGENTS.md", "CLAUDE.md"):
            candidate = os.path.join(current, name)
            if os.path.isfile(candidate) and not os.path.islink(candidate):
                found.append(candidate)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return found


class _Child:
    """A directory child captured before the scandir iterator is closed."""

    __slots__ = ("name", "path", "is_symlink", "is_dir", "readable")

    def __init__(self, name, path, is_symlink, is_dir, readable=True):
        self.name = name
        self.path = path
        self.is_symlink = is_symlink
        self.is_dir = is_dir
        self.readable = readable


def _list_children(path, budget, diagnostics, rel_dir):
    """Collect at most ``budget`` children and sort that bounded set.

    ``overflow`` is true when the directory held more entries than the budget
    allowed, so the walk stops and reports an incomplete scan instead of first
    materialising a directory of unbounded size. Returns ``(children, overflow,
    error)``; ``error`` is set when the directory could not be listed at all.
    """
    children = []
    overflow = False
    try:
        with os.scandir(path) as iterator:
            for index, child in enumerate(iterator):
                if index >= budget:
                    overflow = True
                    break
                try:
                    name = child.name
                    is_symlink = child.is_symlink()
                    is_dir = child.is_dir(follow_symlinks=False)
                except OSError as exc:
                    diagnostics.append(
                        _diag(
                            "entry_unreadable",
                            "entry type could not be read: {}".format(
                                exc.strerror or exc
                            ),
                            _join_rel(rel_dir, child.name),
                        )
                    )
                    children.append(
                        _Child(child.name, child.path, False, False, readable=False)
                    )
                    continue
                children.append(_Child(name, child.path, is_symlink, is_dir))
    except OSError as exc:
        return [], False, exc
    children.sort(key=lambda item: item.name)
    return children, overflow, None


def _scan(root, max_entries, max_depth, diagnostics):
    """Breadth-first bounded walk of ``root``. Follows no symlinks."""
    entries = []
    counts = {"entries": 0, "files": 0, "dirs": 0, "symlinks": 0}
    complete = True
    queue = deque([(root, 0)])
    symlink_notes = 0

    while queue:
        current, depth = queue.popleft()
        remaining = max_entries - counts["entries"]
        rel_dir = _relpath(current, root)
        if remaining <= 0:
            diagnostics.append(
                _diag(
                    "entry_limit_reached",
                    "stopped after {} entries; folder may hold more".format(max_entries),
                )
            )
            return entries, counts, False

        children, overflow, error = _list_children(
            current, remaining, diagnostics, rel_dir
        )
        if error is not None:
            diagnostics.append(
                _diag(
                    "directory_unreadable",
                    "directory could not be listed: {}".format(
                        error.strerror or error
                    ),
                    rel_dir,
                )
            )
            complete = False
            continue

        for child in children:
            counts["entries"] += 1
            name = child.name
            rel = _relpath(child.path, root)
            parent_parts = rel.split("/")[:-1]

            if not child.readable:
                complete = False
                entries.append(
                    _Entry(rel, name, "other", depth + 1,
                           reason="entry could not be inspected")
                )
                continue

            if child.is_symlink:
                counts["symlinks"] += 1
                entries.append(
                    _Entry(rel, name, "symlink", depth + 1, is_symlink=True,
                           reason="symlink; not followed")
                )
                if symlink_notes < 32:
                    diagnostics.append(
                        _diag("symlink_not_followed", "symlink is never followed", rel)
                    )
                    symlink_notes += 1
                continue

            if child.is_dir:
                counts["dirs"] += 1
                kind, reason = _classify_dir(name)
                entries.append(
                    _Entry(rel, name, kind, depth + 1, is_dir=True, reason=reason)
                )
                if kind in ("metadata", "secret"):
                    # Version-control metadata and sensitive directories are
                    # named for the report; their contents are never read.
                    continue
                if overflow:
                    continue
                if depth + 1 < max_depth:
                    queue.append((child.path, depth + 1))
                else:
                    has_children, known = _has_children(child.path, diagnostics, rel)
                    if has_children:
                        diagnostics.append(
                            _diag(
                                "depth_limit_reached",
                                "stopped descending at depth {}; deeper entries".format(
                                    max_depth
                                )
                                + " were not scanned",
                                rel,
                            )
                        )
                        complete = False
                    elif not known:
                        complete = False
                continue

            counts["files"] += 1
            kind, reason = _classify_file(name, parent_parts)
            entries.append(_Entry(rel, name, kind, depth + 1, reason=reason))

        if overflow:
            diagnostics.append(
                _diag(
                    "entry_limit_reached",
                    "stopped after {} entries; folder may hold more".format(max_entries),
                )
            )
            return entries, counts, False

    return entries, counts, complete


def _relpath(path, root):
    rel = os.path.relpath(path, root)
    return "." if rel == "." else rel.replace(os.sep, "/")


def _join_rel(rel_dir, name):
    if rel_dir in ("", "."):
        return name
    return "{}/{}".format(rel_dir, name)


def _has_children(path, diagnostics, rel):
    """Return ``(has_children, known)``; ``known`` is false when listing failed."""
    try:
        with os.scandir(path) as iterator:
            for _child in iterator:
                return True, True
        return False, True
    except OSError as exc:
        diagnostics.append(
            _diag(
                "directory_unreadable",
                "directory could not be listed while checking depth: {}".format(
                    exc.strerror or exc
                ),
                rel,
            )
        )
        return False, False


def _inspect_documents(entries, root, max_identity_bytes, diagnostics):
    """Inspect document bodies in deterministic discovery order.

    Returns ``True`` only when every discovered document was inspected. A read
    failure or the read cap makes the inspection incomplete: the caller then
    refuses to answer ``brief_only`` or ``scaffold`` on partial evidence.
    """
    documents = [entry for entry in entries if entry.kind == "document"]
    complete = True
    for index, entry in enumerate(documents):
        if index >= MAX_DOCUMENT_READS:
            diagnostics.append(
                _diag(
                    "document_read_limit_reached",
                    "stopped inspecting documents after {}".format(MAX_DOCUMENT_READS),
                    entry.rel,
                )
            )
            complete = False
            break
        path = os.path.join(root, entry.rel.replace("/", os.sep))
        try:
            (
                entry.substantive,
                entry.reason,
                entry.size,
                document_complete,
            ) = _inspect_document(
                path, entry.rel, max_identity_bytes, diagnostics
            )
            complete = complete and document_complete
        except OSError as exc:
            entry.substantive = False
            entry.size = None
            entry.reason = "document could not be read"
            diagnostics.append(
                _diag(
                    "document_unreadable",
                    "document could not be read: {}".format(exc.strerror or exc),
                    entry.rel,
                )
            )
            complete = False
    return complete


def _has_component(entries):
    """True when a nested directory carries its own manifest."""
    for entry in entries:
        if entry.is_dir:
            continue
        if entry.name.lower() in MANIFEST_NAMES and entry.depth >= 2:
            return True
    return False


def _classify(entries, complete):
    """Return ``(classification, extra_diagnostics)``. Heuristic, not semantic."""
    extra = []
    user_entries = [entry for entry in entries if entry.kind != "metadata"]

    if not user_entries:
        base = "empty"
    elif any(entry.kind in EXISTING_KINDS for entry in user_entries) or _has_component(
        entries
    ):
        base = "existing"
    elif any(
        entry.kind == "mockup" or (entry.kind == "document" and entry.substantive)
        for entry in user_entries
    ):
        base = "brief_only"
    elif all(entry.kind in STRUCTURE_KINDS for entry in user_entries):
        base = "scaffold"
    else:
        base = "unknown"
        extra.append(
            _diag(
                "no_decision_evidence",
                "entries were found but none could be classified confidently",
            )
        )

    # Partial evidence can not prove an absence. Established code/config/data/
    # secret evidence still stands, but an unproven "empty", "scaffold" or
    # "brief_only" must not be reported as if the folder had been fully
    # inspected.
    if not complete and base in {"empty", "scaffold", "brief_only"}:
        base = "unknown"

    return base, extra


def _build_basis(entries, classification):
    """Deterministic, per-kind-capped explanation of the classification."""
    buckets = {}
    for entry in entries:
        buckets.setdefault(entry.kind, []).append(entry)
    basis = []
    for kind in BASIS_KIND_ORDER:
        selected = sorted(buckets.get(kind, []), key=lambda item: item.rel)
        for entry in selected[:BASIS_PER_KIND_CAP]:
            basis.append(
                {"path": entry.rel, "kind": entry.kind, "reason": entry.reason}
            )
    if classification != "empty" and not basis:
        basis.append(
            {"path": ".", "kind": "other", "reason": "no representative entry"}
        )
    return basis[:BASIS_TOTAL_CAP]


def probe_project(
    root,
    *,
    max_entries=DEFAULT_MAX_ENTRIES,
    max_depth=DEFAULT_MAX_DEPTH,
    max_identity_bytes=DEFAULT_MAX_IDENTITY_BYTES,
):
    """Classify the folder at ``root`` with a bounded, read-only walk.

    Returns a JSON-serializable dict with ``classification``, ``basis``,
    ``selected_scope``, ``scan_complete``, ``diagnostics``, ``counts`` and
    ``limits``. The function performs no writes and follows no child symlinks;
    the selected folder is never replaced by an enclosing repository root.
    ``scan_complete`` is true only when the walk finished and every document
    was inspected, so a non-``existing`` answer on partial evidence is
    ``unknown`` rather than a confident ``empty``, ``scaffold`` or
    ``brief_only``.
    """
    for name, value in (
        ("max_entries", max_entries),
        ("max_depth", max_depth),
        ("max_identity_bytes", max_identity_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("{} must be an int".format(name))
        if value < 1:
            raise ValueError("{} must be at least 1".format(name))

    limits = {
        "max_entries": max_entries,
        "max_depth": max_depth,
        "max_identity_bytes": max_identity_bytes,
    }
    zero_counts = {"entries": 0, "files": 0, "dirs": 0, "symlinks": 0}

    scope, problem = _selected_scope(root)
    if problem is not None:
        return {
            "schema_version": SCHEMA_VERSION,
            "classification": "unknown",
            "basis": [],
            "selected_scope": scope,
            "scan_complete": False,
            "diagnostics": [problem],
            "counts": dict(zero_counts),
            "limits": limits,
        }

    diagnostics = []
    walk_root = scope["resolved_root"]
    entries, counts, walk_complete = _scan(
        walk_root, max_entries, max_depth, diagnostics
    )
    inspection_complete = _inspect_documents(
        entries, walk_root, max_identity_bytes, diagnostics
    )
    complete = walk_complete and inspection_complete
    classification, extra = _classify(entries, complete)
    diagnostics.extend(extra)

    return {
        "schema_version": SCHEMA_VERSION,
        "classification": classification,
        "basis": _build_basis(entries, classification),
        "selected_scope": scope,
        "scan_complete": complete,
        "diagnostics": diagnostics,
        "counts": counts,
        "limits": limits,
    }


def build_parser():
    parser = argparse.ArgumentParser(
        prog="project_probe.py",
        description=(
            "Classify the state of a folder without changing it. Read-only, "
            "standard library only, no network and no git execution."
        ),
    )
    parser.add_argument(
        "--root",
        required=True,
        help="folder to inspect; used exactly as given, never replaced by a parent",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the JSON result (JSON is always printed; kept for clarity)",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=DEFAULT_MAX_ENTRIES,
        help="entry cap for the walk (default: %(default)s)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help="depth cap for the walk (default: %(default)s)",
    )
    parser.add_argument(
        "--max-identity-bytes",
        type=int,
        default=DEFAULT_MAX_IDENTITY_BYTES,
        help="bounded document read size (default: %(default)s)",
    )
    return parser


def _write_json(result):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8", "surrogateescape") + b"\n")
        stream.flush()
    else:  # pragma: no cover - only when stdout is replaced by a text object
        sys.stdout.write(text + "\n")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    for flag, value in (
        ("--max-entries", args.max_entries),
        ("--max-depth", args.max_depth),
        ("--max-identity-bytes", args.max_identity_bytes),
    ):
        if value < 1:
            parser.error("{} must be at least 1".format(flag))
    result = probe_project(
        args.root,
        max_entries=args.max_entries,
        max_depth=args.max_depth,
        max_identity_bytes=args.max_identity_bytes,
    )
    _write_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
