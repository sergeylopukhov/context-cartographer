#!/usr/bin/env python3
"""Project-specific standard-library validation for this skill package.

This is not a YAML implementation and not a drop-in replacement for the
PyYAML-based skill-creator ``quick_validate.py``. It parses the flat scalar
subset of ``SKILL.md`` frontmatter that this package actually uses, plus
resource-routing checks, so CI can run without installing packages. Unsupported
YAML shapes (block or folded scalars, flow collections, anchors, tags, nested
mappings, non-string scalars) raise a clear error instead of being accepted as
literal text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
ALLOWED_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "license", "allowed-tools", "metadata"}
)
NAME_RE = re.compile(r"^[a-z0-9-]+$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---[ \t]*\n?", re.DOTALL)
ROUTE_TOKEN_RE = re.compile(
    r"(?P<kind>references|scripts)/(?P<name>[A-Za-z0-9._/-]+\.(?:md|py))"
)
MARKDOWN_TARGET_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TODO_PLACEHOLDER_RE = re.compile(r"[ ]{0,3}\[TODO:[^\n]*\][ \t]*")
FENCE_RE = re.compile(r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$")
VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9_.-]+)?$")
# Plain (unquoted) scalars that YAML would read as a non-string type.
NON_STRING_SCALAR_RE = re.compile(
    r"^(?:true|false|null|~|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$",
    re.IGNORECASE,
)
# Leading characters that open YAML shapes this parser does not implement.
UNSUPPORTED_VALUE_PREFIXES = {
    "|": "block scalar values are not supported",
    ">": "folded block values are not supported",
    "{": "flow mappings are not supported",
    "[": "flow sequences are not supported",
    "&": "anchors are not supported",
    "*": "aliases are not supported",
    "!": "tags are not supported",
}


class SkillValidationError(RuntimeError):
    """Raised when the package structure cannot be parsed at all."""


def scalar_frontmatter_value(raw_value: str, key: str, source: str) -> str:
    """Return a supported single-line scalar value or reject the shape."""
    value = raw_value.strip()
    if not value:
        return ""
    first = value[0]
    if first in UNSUPPORTED_VALUE_PREFIXES:
        raise SkillValidationError(
            f"{source}: unsupported YAML for '{key}': {UNSUPPORTED_VALUE_PREFIXES[first]}"
        )
    if first in "\"'":
        if len(value) < 2 or value[-1] != first:
            raise SkillValidationError(f"{source}: unterminated quoted value for '{key}'")
        return value[1:-1]
    if NON_STRING_SCALAR_RE.match(value):
        raise SkillValidationError(
            f"{source}: '{key}' must be a string scalar, found plain value {value!r}"
        )
    return value


def parse_frontmatter(text: str, source: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise SkillValidationError(f"{source}: file must start with YAML frontmatter")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise SkillValidationError(f"{source}: frontmatter is not closed with ---")
    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip():
            continue
        if raw_line[0] in " \t":
            raise SkillValidationError(
                f"{source}: nested or indented frontmatter is not supported: {raw_line.strip()}"
            )
        if ":" not in raw_line:
            raise SkillValidationError(f"{source}: malformed frontmatter line: {raw_line}")
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if not key:
            raise SkillValidationError(f"{source}: frontmatter line has an empty key: {raw_line}")
        if key in values:
            raise SkillValidationError(f"{source}: duplicate frontmatter key: {key}")
        values[key] = scalar_frontmatter_value(value, key, source)
    return values, text[match.end():]


def unfinished_placeholder(body: str) -> str | None:
    fence_marker: str | None = None
    fence_length = 0
    for line in body.splitlines():
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker = marker[0]
                fence_length = len(marker)
            elif (
                marker[0] == fence_marker
                and len(marker) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_marker = None
                fence_length = 0
            continue
        if fence_marker is None and TODO_PLACEHOLDER_RE.fullmatch(line):
            return line.strip()
    return None


def route_tokens(text: str) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    tokens: list[tuple[str, str]] = []
    for match in ROUTE_TOKEN_RE.finditer(text):
        token = (match.group("kind"), match.group("name"))
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def strip_fenced_code(text: str) -> str:
    """Blank out fenced code blocks so examples are not read as real routes."""
    result: list[str] = []
    fence_marker: str | None = None
    fence_length = 0
    for line in text.splitlines():
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker = marker[0]
                fence_length = len(marker)
            elif (
                marker[0] == fence_marker
                and len(marker) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_marker = None
                fence_length = 0
            result.append("")
            continue
        result.append("" if fence_marker is not None else line)
    return "\n".join(result)


def markdown_md_targets(text: str, base_dir: Path) -> list[Path]:
    targets: list[Path] = []
    for match in MARKDOWN_TARGET_RE.finditer(text):
        target = match.group(1).split("#", 1)[0]
        if not target or "://" in target or not target.endswith(".md"):
            continue
        try:
            targets.append((base_dir / target).resolve())
        except OSError:
            continue
    return targets


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_resolve(path: Path) -> Path | None:
    try:
        return path.resolve()
    except OSError:
        return None


def _skill_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def check_frontmatter(skill_dir: Path) -> list[str]:
    problems: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"SKILL.md is missing at {skill_md}"]

    try:
        frontmatter, body = parse_frontmatter(
            skill_md.read_text(encoding="utf-8"), "SKILL.md"
        )
    except SkillValidationError as exc:
        return [str(exc)]

    unexpected = sorted(set(frontmatter) - ALLOWED_FRONTMATTER_KEYS)
    if unexpected:
        problems.append("unexpected frontmatter key(s): " + ", ".join(unexpected))

    name = frontmatter.get("name", "").strip()
    if not name:
        problems.append("frontmatter is missing a non-empty 'name'")
    else:
        if not NAME_RE.match(name):
            problems.append(
                f"name '{name}' must be hyphen-case (lowercase letters, digits, hyphens)"
            )
        if name.startswith("-") or name.endswith("-") or "--" in name:
            problems.append(
                f"name '{name}' must not start/end with a hyphen or repeat hyphens"
            )
        if len(name) > MAX_SKILL_NAME_LENGTH:
            problems.append(f"name is too long ({len(name)} > {MAX_SKILL_NAME_LENGTH})")
        if name != skill_dir.name:
            problems.append(
                f"name '{name}' does not match the skill folder name '{skill_dir.name}'"
            )

    description = frontmatter.get("description", "").strip()
    if not description:
        problems.append("frontmatter is missing a non-empty 'description'")
    else:
        if description.startswith("[TODO:"):
            problems.append("description contains an unfinished TODO placeholder")
        if "<" in description or ">" in description:
            problems.append("description must not contain angle brackets")
        if len(description) > MAX_DESCRIPTION_LENGTH:
            problems.append(
                f"description is too long ({len(description)} > {MAX_DESCRIPTION_LENGTH})"
            )

    placeholder = unfinished_placeholder(body)
    if placeholder:
        problems.append(f"SKILL.md body keeps an unfinished placeholder: {placeholder}")

    version_file = skill_dir / "VERSION"
    if not version_file.is_file():
        problems.append("VERSION file is missing")
    else:
        version = version_file.read_text(encoding="utf-8").strip()
        if not version:
            problems.append("VERSION file is empty")
        elif not VERSION_RE.match(version):
            problems.append(f"VERSION '{version}' is not a supported version string")

    return problems


def collect_routing(skill_dir: Path) -> tuple[set[Path], list[str]]:
    """Walk resource routes from SKILL.md and report the edges that do not hold.

    A route is truthful only when every ``references/*`` or ``scripts/*`` token
    and every intra-package Markdown link resolves to a real file that stays
    inside the skill package. Fenced code is ignored because documented examples
    are not routing instructions.
    """
    root = skill_dir.resolve()
    problems: list[str] = []
    reached: set[Path] = set()
    entry = (skill_dir / "SKILL.md").resolve()
    if not entry.is_file():
        return reached, ["SKILL.md is missing"]

    reached.add(entry)
    queue: list[Path] = [entry]
    while queue:
        current = queue.pop()
        try:
            raw_text = current.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"cannot read routed document {_skill_relative(current, root)}: {exc}")
            continue
        text = strip_fenced_code(raw_text)
        source = _skill_relative(current, root)

        for kind, name in route_tokens(text):
            kind_dir = (skill_dir / kind).resolve()
            resolved = _safe_resolve(skill_dir / kind / name)
            if resolved is None or not _is_within(resolved, kind_dir):
                problems.append(f"{source} routes outside {kind}/: {kind}/{name}")
                continue
            if not resolved.is_file():
                problems.append(f"{source} routes to a missing resource: {kind}/{name}")
                continue
            if resolved.suffix == ".md" and resolved not in reached:
                reached.add(resolved)
                queue.append(resolved)

        for resolved in markdown_md_targets(text, current.parent):
            if not _is_within(resolved, root):
                problems.append(
                    f"{source} links outside the skill package: {resolved.as_posix()}"
                )
                continue
            if not resolved.exists():
                problems.append(
                    f"{source} links to a missing file: {_skill_relative(resolved, root)}"
                )
                continue
            if resolved.suffix == ".md" and resolved not in reached:
                reached.add(resolved)
                queue.append(resolved)

    return reached, problems


def reachable_markdown(skill_dir: Path) -> set[Path]:
    """Return the Markdown documents routed from SKILL.md (problems ignored)."""
    reached, _ = collect_routing(skill_dir)
    return reached


def check_resource_routing(skill_dir: Path) -> list[str]:
    problems: list[str] = []
    if not (skill_dir / "SKILL.md").is_file():
        return ["SKILL.md is missing"]

    reached, routing_problems = collect_routing(skill_dir)
    problems.extend(routing_problems)

    references_dir = skill_dir / "references"
    if references_dir.is_dir():
        for path in sorted(references_dir.rglob("*.md")):
            if path.resolve() not in reached:
                problems.append(
                    "reference file is not routed from SKILL.md: "
                    + path.relative_to(skill_dir).as_posix()
                )
    return problems


def validate_package(skill_dir: str | Path) -> dict:
    resolved = Path(skill_dir).resolve()
    skill_md = resolved / "SKILL.md"
    references_dir = resolved / "references"
    scripts_dir = resolved / "scripts"

    problems = check_frontmatter(resolved) + check_resource_routing(resolved)
    skill_text = skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
    return {
        "skill_dir": str(resolved),
        "skill_md_bytes": len(skill_text.encode("utf-8")),
        "skill_md_lines": len(skill_text.splitlines()),
        "reference_files": sorted(
            path.relative_to(resolved).as_posix()
            for path in references_dir.rglob("*.md")
        )
        if references_dir.is_dir()
        else [],
        "script_files": sorted(
            path.relative_to(resolved).as_posix() for path in scripts_dir.glob("*.py")
        )
        if scripts_dir.is_dir()
        else [],
        "problems": problems,
        "ok": not problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the context-cartographer skill package with the standard library."
    )
    parser.add_argument(
        "skill_dir",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="Skill folder to validate. Defaults to this script's skill folder.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report.")
    args = parser.parse_args(argv)

    report = validate_package(args.skill_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print(f"Context Cartographer skill validation: {Path(report['skill_dir']).name}")
    print(f"  SKILL.md: {report['skill_md_bytes']} bytes, {report['skill_md_lines']} lines")
    print(f"  references: {len(report['reference_files'])} markdown files")
    print(f"  scripts: {len(report['script_files'])} python files")
    if report["ok"]:
        print("PASS: frontmatter and reference routing are valid")
        return 0
    for problem in report["problems"]:
        print(f"FAIL: {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
