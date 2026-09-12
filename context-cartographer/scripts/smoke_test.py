#!/usr/bin/env python3
"""Behavioral smoke tests for Context Cartographer and its local tools."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_skill  # noqa: E402  (imported after the sys.path bootstrap)

SCRIPT_PATH = SCRIPTS_DIR / "questionnaire_server.py"
UPDATE_SCRIPT_PATH = SCRIPTS_DIR / "check_update.py"
DECISION_STATE_SCRIPT_PATH = SCRIPTS_DIR / "decision_state.py"
SKILL_DIR = SCRIPTS_DIR.parent
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
SETUP_WORKFLOW_PATH = REFERENCES_DIR / "setup-workflow.md"
EXISTING_WORKFLOW_PATH = REFERENCES_DIR / "existing-docs-workflow.md"
DECISION_DISCOVERY_PATH = REFERENCES_DIR / "decision-discovery.md"
TEMPLATES_DIR = REFERENCES_DIR / "templates"
REPOSITORY_ROOT = SKILL_DIR.parent
README_PATH = REPOSITORY_ROOT / "README.md"
CLAUDE_ADAPTER_PATH = REPOSITORY_ROOT / "adapters" / "claude" / "CLAUDE.md"
IS_REPOSITORY_CHECKOUT = README_PATH.is_file() and (REPOSITORY_ROOT / "adapters").is_dir()

# The routed templates split the former file-templates.md; the Cursor router is
# generated from the root instruction template, not from a static adapter file.
TEMPLATE_ROLE_CANDIDATES = {
    "root instructions": ("root-instructions.md", "root-agents.md"),
    "documentation map": ("documentation-map.md", "architecture-map.md"),
    "documentation rules": ("documentation-rules.md",),
    "core docs": ("core-docs.md",),
    "profile docs": ("profile-docs.md",),
    "code rules": ("code-rules.md",),
    "idea docs": ("idea-docs.md",),
}
CLAUDE_ROUTE_TOKEN = "CLAUDE.md"
CURSOR_ROUTE_TOKEN = ".cursor/rules/context-cartographer.mdc"
MARKDOWN_TARGET_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_LINE_RE = re.compile(r"^(?: {0,3})(`{3,}|~{3,})(.*)$")
MAINTENANCE_MODE_RE = re.compile(r"Maintenance mode:\s*`([^`]+)`")
CODE_RULES_MODE_RE = re.compile(r"Code-rules mode:\s*`([^`]+)`")
ROOT_ADAPTER_LINK_SUFFIXES = (
    "docs/architecture.md",
    "docs/documentation-rules.md",
)
ADAPTER_TARGET_TOKENS = ("AGENTS.md", "CLAUDE.md", "context-cartographer.mdc")
MAINTENANCE_MODES = ("automatic durable maintenance", "request-only maintenance")
CODE_RULES_MODES = ("use code rules file", "do not use code rules file")
EXPLICIT_REQUEST_PHRASE = "when the user asks to create, save, or update an artifact"
FORBIDDEN_READ_ONLY_PHRASE = (
    "questions, analysis, review, diagnosis, or planning"
)
FORBIDDEN_DURABLE_STATUS = "no durable docs update was needed"
MAP_BLOCK_FORBIDDEN_PATHS = ("DEPLOYMENT.md", "code_rules.md")


def load_server_module():
    spec = importlib.util.spec_from_file_location("questionnaire_server", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_update_module():
    spec = importlib.util.spec_from_file_location("check_update", UPDATE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {UPDATE_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_decision_state_module():
    spec = importlib.util.spec_from_file_location("decision_state", DECISION_STATE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {DECISION_STATE_SCRIPT_PATH}")
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


SKIPPED_CHECKS: list[tuple[str, bool]] = []


def skip_line(message: str, *, required: bool = False) -> None:
    SKIPPED_CHECKS.append((message, required))
    marker = "required, cannot run here" if required else "optional, not applicable here"
    print(f"SKIP ({marker}): {message}")


def normalize_contract_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " "))


def load_reference_docs() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8")
        for path in sorted(REFERENCES_DIR.rglob("*.md"))
    }


def resolve_template_files() -> dict[str, Path]:
    """Resolve each routed template role to the first matching real file."""
    resolved: dict[str, Path] = {}
    for role, candidates in TEMPLATE_ROLE_CANDIDATES.items():
        for name in candidates:
            candidate = TEMPLATES_DIR / name
            if candidate.is_file():
                resolved[role] = candidate
                break
    return resolved


DURABLE_COVERAGE_PHRASES = (
    "durable",
    "setup",
    "architecture",
    "deployment",
    "staging",
    "data model",
    "public interface",
    "agent workflow",
    "documentation ownership",
)

# The root adapter contract is checked in the routed root instruction template.
# Requirements must be satisfied by that file alone, so an unrelated reference
# cannot stand in for a missing rule.
ROOT_TEMPLATE_GROUPS = {
    "routine maintenance stays project-local": (
        "do not invoke",
        "the local project instructions and existing owner documents suffice",
    ),
    "unclear-ownership escalation": ("unclear ownership",),
    "durable change coverage": DURABLE_COVERAGE_PHRASES,
    "neutral modes": (
        "automatic durable maintenance",
        "request-only maintenance",
        "use code rules file",
        "do not use code rules file",
        "do not infer code rules mode or documentation maintenance mode",
    ),
    "root path discipline": ("resolve the project root once",),
}

# The self-sufficient maintenance contract is owned by the rules template, so
# owner-creation rules are checked there rather than in the thin root adapter.
RULES_TEMPLATE_GROUPS = {
    "self-sufficient contract": ("self-sufficient",),
    "local sufficiency": (
        "the local project instructions and existing owner documents suffice",
    ),
    "project-local owner creation": ("smallest justified owner",),
    "owner creation without extra permission": (
        "without asking merely for permission to create a markdown file",
    ),
    "owner creation stays project-local": ("without invoking the skill",),
    "unclear-ownership escalation": ("unclear ownership",),
    "no parallel memory": ("context map.md",),
    "durable change coverage": DURABLE_COVERAGE_PHRASES,
    "neutral maintenance modes": (
        "automatic durable maintenance",
        "request-only maintenance",
    ),
}

# Reading discipline lives in the workflows and the audit checklist, not in the
# root adapter, so it is verified where it is actually stated.
READING_DISCIPLINE_GROUPS = {
    "reuse already-read files": ("reuse files already read",),
    "limited rereads": ("reread only",),
}

# The repository-level Claude adapter is a static pointer outside the installable
# package. It is only held to the phrases it must keep; the two new package rules
# live in the routed templates, so the adapter is not forced to duplicate them.
ADAPTER_CONTRACT_GROUPS = {
    "project-local owner creation": ("smallest justified owner",),
    "owner creation without extra permission": (
        "without asking merely for permission to create a markdown file",
    ),
    "routine maintenance stays project-local": ("do not invoke",),
    "unclear-ownership escalation": ("unclear ownership",),
    "durable change coverage": DURABLE_COVERAGE_PHRASES,
    "neutral modes": (
        "automatic durable maintenance",
        "do not infer documentation maintenance mode",
        "code rules",
    ),
}


def missing_contract_phrases(text: str, groups: dict) -> list[str]:
    normalized = normalize_contract_text(text)
    missing: list[str] = []
    for label, phrases in groups.items():
        for phrase in phrases:
            if normalize_contract_text(phrase) not in normalized:
                missing.append(f"{label}: '{phrase}'")
    return missing


def frontmatter_blocks(text: str) -> list[str]:
    """Return the bodies of `---`-delimited frontmatter blocks in a document."""
    lines = text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == "---":
            for closing in range(index + 1, len(lines)):
                if lines[closing].strip() == "---":
                    blocks.append("\n".join(lines[index + 1:closing]))
                    index = closing
                    break
            else:
                break
        index += 1
    return blocks


def markdown_link_targets(text: str) -> list[str]:
    return [match.group(1) for match in MARKDOWN_TARGET_RE.finditer(text)]


def fenced_blocks_with_heading(text: str) -> list[tuple[str, str]]:
    """Return (nearest preceding '## ' heading, fence body) for every fence."""
    blocks: list[tuple[str, str]] = []
    heading = ""
    marker: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        fence = FENCE_LINE_RE.match(line)
        if fence:
            current = fence.group(1)
            if marker is None:
                marker = current
                buffer = []
                continue
            if (
                current[0] == marker[0]
                and len(current) >= len(marker)
                and not fence.group(2).strip()
            ):
                blocks.append((heading, "\n".join(buffer)))
                marker = None
                continue
        if marker is None:
            if line.startswith("## "):
                heading = line[3:].strip()
        else:
            buffer.append(line)
    return blocks


def adapter_bodies(template_text: str) -> dict[str, str]:
    """Map each adapter target heading to its generated Markdown body."""
    bodies: dict[str, str] = {}
    for heading, block in fenced_blocks_with_heading(template_text):
        if any(token in heading for token in ADAPTER_TARGET_TOKENS):
            bodies[heading] = block
    return bodies


def parse_simple_frontmatter(text: str, source: str) -> dict[str, str]:
    lines = text.splitlines()
    assert_true(lines and lines[0] == "---", f"{source} frontmatter is missing")

    values: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return values
        if not line or line.startswith((" ", "\t")):
            continue
        assert_true(":" in line, f"{source} has malformed frontmatter: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        assert_true(key not in values, f"{source} has duplicate frontmatter key: {key}")
        values[key] = value.strip().strip("\"'")

    raise AssertionError(f"{source} frontmatter is not closed")


def main() -> int:
    SKIPPED_CHECKS.clear()
    try:
        server = load_server_module()
        pass_line("questionnaire_server.py imports cleanly")

        updater = load_update_module()
        local_version = updater.read_local_version()
        assert_true(local_version, "local VERSION was not read")
        assert_true(updater.is_newer("0.1.1", "0.1.0"), "newer patch version was not detected")
        assert_true(not updater.is_newer("0.1.0", "0.1.0"), "same version was treated as newer")
        assert_true(updater.should_check({}, 1, False), "empty cache should trigger update check")
        assert_true(not updater.should_check({"checked_at": updater.time.time()}, 1, False), "fresh cache should skip update check")
        pass_line("check_update.py imports and compares versions")

        decision_state = load_decision_state_module()
        pass_line("decision_state.py imports cleanly")

        skill_text = SKILL_PATH.read_text(encoding="utf-8")
        setup_workflow = SETUP_WORKFLOW_PATH.read_text(encoding="utf-8")
        existing_workflow = EXISTING_WORKFLOW_PATH.read_text(encoding="utf-8")
        decision_discovery = DECISION_DISCOVERY_PATH.read_text(encoding="utf-8")
        readme_text = README_PATH.read_text(encoding="utf-8") if IS_REPOSITORY_CHECKOUT else ""
        skill_frontmatter = parse_simple_frontmatter(skill_text, "SKILL.md")
        print(
            "INFO: SKILL.md occupies "
            f"{len(skill_text.encode('utf-8'))} bytes across {len(skill_text.splitlines())} lines"
        )
        skill_description = skill_frontmatter.get("description", "").lower()
        assert_true(
            "do not use for" in skill_description and "routine" in skill_description,
            "skill metadata does not exclude routine documentation edits",
        )
        validation = validate_skill.validate_package(SKILL_DIR)
        assert_true(
            validation["ok"],
            "stdlib skill validation failed: " + "; ".join(validation["problems"]),
        )
        pass_line(
            "stdlib validation accepts the skill frontmatter and reference routing "
            f"({validation['skill_md_bytes']} byte SKILL.md, "
            f"{len(validation['reference_files'])} references)"
        )
        assert_true(
            "automatic durable documentation maintenance already governed by project root instructions" in skill_text,
            "skill metadata does not preserve independent automatic maintenance",
        )
        assert_true(
            "always read `references/setup-workflow.md`" in skill_text
            and "always read `references/existing-docs-workflow.md`" in skill_text,
            "SKILL.md does not require the scenario workflows",
        )
        assert_true(
            "Choose the interaction method by task shape, not by a fixed question count" in skill_text,
            "SKILL.md still routes questions by an arbitrary count",
        )
        assert_true(
            "Never create `CONTEXT.md`, `CONTEXT-MAP.md`, or another parallel source of truth" in decision_discovery,
            "adaptive discovery can create a parallel documentation system",
        )
        if IS_REPOSITORY_CHECKOUT:
            removed_cursor_copy_command = "cp adapters/cursor/" + "context-cartographer.mdc"
            assert_true(
                removed_cursor_copy_command not in readme_text,
                "README references the removed Cursor adapter file",
            )
        else:
            skip_line("README route checks need a repository checkout", required=False)
        public_skill_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SKILL_DIR.rglob("*"))
            if path.is_file() and path.suffix in {".md", ".py", ".yaml"}
        ) + readme_text
        forbidden_reference = "gri" + "ll"
        assert_true(
            forbidden_reference not in public_skill_text.lower(),
            "skill contains an unwanted external interview-skill reference",
        )
        for required_setup_rule in (
            "Do not infer code-rules mode or documentation maintenance mode",
            "Create `docs/architecture.md` as a concise documentation map",
            "Create `docs/documentation-rules.md` with the self-sufficient maintenance contract",
            "invoke `context-cartographer` only when ownership is genuinely unclear",
        ):
            assert_true(required_setup_rule in setup_workflow, f"setup workflow lost rule: {required_setup_rule}")
        assert_true(
            "Require later agents to invoke `context-cartographer` before creating a new owner document"
            not in setup_workflow,
            "setup workflow still requires the full skill for an obvious new owner",
        )
        for required_existing_rule in (
            "Do not require a general cleanup strategy",
            "create the smallest justified owner automatically without asking for approval",
            "Do not ask a question merely because a new Markdown file is needed",
            "Add the new owner to `docs/architecture.md`",
            "Create a new owner file during routine maintenance only for a durable topic that no existing owner can hold",
        ):
            assert_true(
                required_existing_rule in existing_workflow,
                f"existing-docs workflow lost rule: {required_existing_rule}",
            )
        assert_true(
            "Do not create a new Markdown file during routine maintenance"
            not in existing_workflow,
            "existing-docs workflow still forbids creating a needed owner during routine maintenance",
        )
        assert_true(
            "Folder classification does not replace the user's requested operation"
            in existing_workflow
            and "stay on this workflow even when the folder is `brief_only`"
            in existing_workflow,
            "brief-only classification can still override an explicit documentation audit",
        )

        reference_docs = load_reference_docs()
        reached_docs = validate_skill.reachable_markdown(SKILL_DIR)
        template_files = resolve_template_files()
        missing_roles = [
            role for role in TEMPLATE_ROLE_CANDIDATES if role not in template_files
        ]
        assert_true(
            not missing_roles,
            "routed template roles are missing: " + ", ".join(missing_roles),
        )
        for role, path in template_files.items():
            assert_true(
                path.resolve() in reached_docs,
                f"{role} template is not routed from SKILL.md: "
                + path.relative_to(SKILL_DIR).as_posix(),
            )
            template_text = path.read_text(encoding="utf-8")
            assert_true(
                len(template_text.encode("utf-8")) > 200
                and "\n# " in "\n" + template_text,
                f"{role} template looks empty or has no top-level heading",
            )

        root_template_path = template_files["root instructions"]
        rules_template_path = template_files["documentation rules"]
        root_template_text = root_template_path.read_text(encoding="utf-8")
        rules_template_text = rules_template_path.read_text(encoding="utf-8")

        root_template_missing = missing_contract_phrases(
            root_template_text, ROOT_TEMPLATE_GROUPS
        )
        assert_true(
            not root_template_missing,
            "root instruction template lost contract phrases: "
            + "; ".join(root_template_missing),
        )
        rules_template_missing = missing_contract_phrases(
            rules_template_text, RULES_TEMPLATE_GROUPS
        )
        assert_true(
            not rules_template_missing,
            "documentation-rules template lost contract phrases: "
            + "; ".join(rules_template_missing),
        )
        for discipline_path in (
            SETUP_WORKFLOW_PATH,
            REFERENCES_DIR / "audit-checklist.md",
        ):
            discipline_text = discipline_path.read_text(encoding="utf-8")
            discipline_missing = missing_contract_phrases(
                discipline_text, READING_DISCIPLINE_GROUPS
            )
            assert_true(
                not discipline_missing,
                f"{discipline_path.name} lost reading-discipline rules: "
                + "; ".join(discipline_missing),
            )

        claude_route_docs = {
            path: text for path, text in reference_docs.items() if CLAUDE_ROUTE_TOKEN in text
        }
        assert_true(
            claude_route_docs,
            "no reference material routes the supported Claude Code target (CLAUDE.md)",
        )

        cursor_route_docs = {
            path: text
            for path, text in reference_docs.items()
            if CURSOR_ROUTE_TOKEN in text
        }
        assert_true(
            cursor_route_docs,
            f"no reference template routes the supported Cursor target ({CURSOR_ROUTE_TOKEN})",
        )
        assert_true(
            root_template_path in cursor_route_docs,
            "the routed root template does not carry the Cursor .mdc route",
        )
        cursor_normalized = normalize_contract_text(root_template_text)
        assert_true(
            ".mdc" in root_template_text
            and "cursor" in cursor_normalized
            and "frontmatter" in cursor_normalized,
            "Cursor route template lost the .mdc frontmatter requirement",
        )
        # A real routed Cursor rule keeps a genuine frontmatter block whose
        # alwaysApply value is true. A missing key must fail the check rather
        # than leave an empty loop that passes vacuously.
        cursor_rule_blocks = [
            block
            for block in frontmatter_blocks(root_template_text)
            if re.search(r"(?mi)^\s*alwaysApply\s*:", block)
        ]
        assert_true(
            cursor_rule_blocks,
            "the routed Cursor template defines no real rule frontmatter block with alwaysApply",
        )
        always_apply_true = [
            block
            for block in cursor_rule_blocks
            if re.search(r"(?mi)^\s*alwaysApply\s*:\s*[\"']?true[\"']?\s*$", block)
        ]
        assert_true(
            always_apply_true,
            "the Cursor rule frontmatter must keep a real alwaysApply: true",
        )
        root_link_targets = markdown_link_targets(root_template_text)
        for suffix in ROOT_ADAPTER_LINK_SUFFIXES:
            assert_true(
                any(target.endswith(suffix) for target in root_link_targets),
                f"the root adapter template has no real Markdown link to {suffix}",
            )

        # Each generated adapter must pin exactly one mode per bullet, and the
        # Cursor rule must route with links relative to .cursor/rules/.
        bodies = adapter_bodies(root_template_text)
        assert_true(
            len(bodies) == 3,
            "root template must define exactly three adapter bodies, found "
            + str(len(bodies)),
        )
        for heading, body in bodies.items():
            maintenance = MAINTENANCE_MODE_RE.findall(body)
            assert_true(
                len(maintenance) == 1 and maintenance[0] in MAINTENANCE_MODES,
                f"{heading} must pin exactly one maintenance mode, found {maintenance}",
            )
            code_rules = CODE_RULES_MODE_RE.findall(body)
            assert_true(
                len(code_rules) == 1 and code_rules[0] in CODE_RULES_MODES,
                f"{heading} must pin exactly one code-rules mode, found {code_rules}",
            )
        cursor_bodies = {
            heading: body
            for heading, body in bodies.items()
            if "context-cartographer.mdc" in heading
        }
        assert_true(
            len(cursor_bodies) == 1,
            "root template has no single Cursor adapter body",
        )
        cursor_body = next(iter(cursor_bodies.values()))
        cursor_targets = markdown_link_targets(cursor_body)
        for suffix in ROOT_ADAPTER_LINK_SUFFIXES:
            assert_true(
                any(
                    target.startswith("../../") and target.endswith(suffix)
                    for target in cursor_targets
                ),
                f"the Cursor rule needs a project-relative Markdown link to {suffix}",
            )

        code_rules_text = template_files["code rules"].read_text(encoding="utf-8")
        for label, text in (
            ("root instruction template", root_template_text),
            ("code-rules template", code_rules_text),
        ):
            assert_true(
                normalize_contract_text(EXPLICIT_REQUEST_PHRASE)
                in normalize_contract_text(text),
                f"{label} lost the explicit-request intent rule",
            )
            assert_true(
                FORBIDDEN_READ_ONLY_PHRASE not in normalize_contract_text(text),
                f"{label} restored the unconditional read-only question rule",
            )
            assert_true(
                FORBIDDEN_DURABLE_STATUS not in normalize_contract_text(text),
                f"{label} restored the mandatory 'no durable update' status line",
            )

        map_text = template_files["documentation map"].read_text(encoding="utf-8")
        map_blocks = fenced_blocks_with_heading(map_text)
        assert_true(map_blocks, "documentation map template has no generated map block")
        main_map_block = map_blocks[0][1]
        for forbidden_path in MAP_BLOCK_FORBIDDEN_PATHS:
            assert_true(
                forbidden_path not in main_map_block,
                f"the main map block must not ship a row for {forbidden_path}",
            )
        assert_true(
            "code rules mode" in normalize_contract_text(map_text)
            and "code.rules" in map_text,
            "documentation map template lost the optional code-rules rows",
        )

        if IS_REPOSITORY_CHECKOUT:
            assert_true(
                CLAUDE_ADAPTER_PATH.is_file(),
                f"supported Claude adapter file is missing: {CLAUDE_ADAPTER_PATH}",
            )
            claude_adapter = CLAUDE_ADAPTER_PATH.read_text(encoding="utf-8")
            claude_missing = missing_contract_phrases(
                claude_adapter, ADAPTER_CONTRACT_GROUPS
            )
            assert_true(
                not claude_missing,
                "Claude adapter lost supported contract phrases: " + "; ".join(claude_missing),
            )
            assert_true(
                normalize_contract_text(EXPLICIT_REQUEST_PHRASE)
                in normalize_contract_text(claude_adapter),
                "Claude adapter lost the explicit-request intent rule",
            )
            assert_true(
                FORBIDDEN_READ_ONLY_PHRASE
                not in normalize_contract_text(claude_adapter),
                "Claude adapter restored the unconditional read-only question rule",
            )
        else:
            skip_line("Claude static adapter checks need a repository checkout", required=False)

        reference_bytes = sum(len(text.encode("utf-8")) for text in reference_docs.values())
        assert_true(
            validation["skill_md_bytes"] < reference_bytes,
            "SKILL.md is not smaller than its routed reference corpus; detail belongs in references",
        )
        pass_line(
            "skill routing is narrow, root templates keep the project-local contract, "
            f"and SKILL.md ({validation['skill_md_bytes']} bytes) stays below its "
            f"{reference_bytes}-byte reference corpus"
        )

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

            valid_state = {
                "version": 1,
                "topic": "Documentation setup",
                "status": "active",
                "facts": [
                    {
                        "id": "fact_stack",
                        "statement": "The project uses Python.",
                        "source": "pyproject.toml",
                        "status": "verified",
                    }
                ],
                "conflicts": [
                    {
                        "id": "conflict_docs",
                        "description": "README and runtime disagree about the docs root.",
                        "status": "resolved",
                        "resolution": "Use the runtime path.",
                    }
                ],
                "decisions": [
                    {
                        "id": "agent_target",
                        "question": "Which agent target is required?",
                        "status": "resolved",
                        "depends_on": [],
                        "conflicts": [],
                        "recommendation": "Codex",
                        "answer": "Codex",
                    },
                    {
                        "id": "code_rules_mode",
                        "question": "Should code rules be used?",
                        "status": "pending",
                        "depends_on": ["agent_target"],
                        "conflicts": ["conflict_docs"],
                        "recommendation": None,
                        "answer": None,
                    },
                ],
                "out_of_scope": [],
            }
            normalized_state = decision_state.validate_state(valid_state)
            state_summary = decision_state.summarize_state(normalized_state)
            assert_true(state_summary["frontier"] == ["code_rules_mode"], "decision frontier was computed incorrectly")
            assert_true(not state_summary["ready"], "incomplete decision state was marked ready")
            pass_line("decision state computes dependency-aware frontier")

            completed_state = json.loads(json.dumps(valid_state))
            completed_state["status"] = "ready_for_confirmation"
            completed_state["decisions"][1]["status"] = "resolved"
            completed_state["decisions"][1]["answer"] = "Do not use code rules"
            completed_summary = decision_state.summarize_state(decision_state.validate_state(completed_state))
            assert_true(completed_summary["ready"], "completed decision state was not marked ready")
            assert_true(completed_summary["frontier"] == [], "completed state still has a frontier")
            pass_line("decision state accepts a fully resolved confirmation gate")

            cyclic_state = json.loads(json.dumps(valid_state))
            cyclic_state["decisions"][0]["depends_on"] = ["code_rules_mode"]
            try:
                decision_state.validate_state(cyclic_state)
            except decision_state.DecisionStateError as exc:
                assert_true("dependency cycle" in str(exc), "dependency cycle produced an unclear error")
                pass_line("decision state rejects dependency cycles")
            else:
                raise AssertionError("decision dependency cycle unexpectedly passed")

            premature_state = json.loads(json.dumps(valid_state))
            premature_state["status"] = "confirmed"
            try:
                decision_state.validate_state(premature_state)
            except decision_state.DecisionStateError as exc:
                assert_true("requires all decisions" in str(exc), "premature confirmation produced an unclear error")
                pass_line("decision state rejects premature confirmation")
            else:
                raise AssertionError("premature confirmed state unexpectedly passed")

            out_of_order_state = json.loads(json.dumps(valid_state))
            out_of_order_state["decisions"][0]["status"] = "pending"
            out_of_order_state["decisions"][0]["answer"] = None
            out_of_order_state["decisions"][1]["status"] = "resolved"
            out_of_order_state["decisions"][1]["answer"] = "Do not use code rules"
            try:
                decision_state.validate_state(out_of_order_state)
            except decision_state.DecisionStateError as exc:
                assert_true("resolved before dependencies" in str(exc), "out-of-order resolution produced an unclear error")
                pass_line("decision state rejects out-of-order resolution")
            else:
                raise AssertionError("out-of-order resolved decision unexpectedly passed")

            valid_path = temp_dir / "questions.json"
            valid_path.write_text(json.dumps(valid_questionnaire, indent=2), encoding="utf-8")

            loaded = server.load_questionnaire(valid_path)
            assert_true(loaded["title"] == "Тестовая анкета", "valid questionnaire title was not preserved")
            assert_true(len(loaded["questions"]) == 5, "valid questionnaire question count changed")
            pass_line("valid questionnaire parses and validates")

            direct = server.validate_questionnaire(valid_questionnaire)
            assert_true(direct["questions"][0]["id"] == "audience", "direct validation returned unexpected data")
            pass_line("schema validation accepts valid data")

            cyclic_questionnaire = {
                "title": "Cyclic questionnaire",
                "questions": [
                    {
                        "id": "first",
                        "title": "First",
                        "type": "text",
                        "show_if": {"question_id": "second", "is_answered": True},
                    },
                    {
                        "id": "second",
                        "title": "Second",
                        "type": "text",
                        "show_if": {"question_id": "first", "is_answered": True},
                    },
                ],
            }
            try:
                server.validate_questionnaire(cyclic_questionnaire)
            except server.QuestionnaireError as exc:
                assert_true("dependency cycle" in str(exc), "question cycle produced an unclear error")
                pass_line("questionnaire rejects conditional dependency cycles")
            else:
                raise AssertionError("questionnaire dependency cycle unexpectedly passed")

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
            assert_true(
                output["metadata"]["generated_by"] == "context-cartographer-questionnaire",
                "questionnaire output carries stale generator metadata",
            )
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
            (out_dir / "decision-state.json").write_text("{}", encoding="utf-8")
            (out_dir / "keep.txt").write_text("keep", encoding="utf-8")
            deleted = server.cleanup_questionnaire_dir(out_dir)
            assert_true((out_dir / ".gitignore").exists(), "cleanup removed .gitignore")
            assert_true(not (out_dir / "answers.json").exists(), "cleanup did not remove answers.json")
            assert_true(not (out_dir / "answers.md").exists(), "cleanup did not remove answers.md")
            assert_true(not (out_dir / "questions.json").exists(), "cleanup did not remove questions.json")
            assert_true(not (out_dir / "decision-state.json").exists(), "cleanup did not remove decision-state.json")
            assert_true((out_dir / "keep.txt").exists(), "cleanup removed a non-generated file")
            assert_true(any("answers.json" in path for path in deleted), "cleanup did not report deleted answers")
            pass_line("explicit cleanup removes generated files and keeps .gitignore")

        required_skips = [name for name, required in SKIPPED_CHECKS if required]
        if required_skips:
            raise AssertionError(
                "required checks were skipped: " + ", ".join(required_skips)
            )
        if SKIPPED_CHECKS:
            skipped_names = ", ".join(name for name, _ in SKIPPED_CHECKS)
            print(
                "PASS: all runnable smoke checks passed "
                f"({len(SKIPPED_CHECKS)} explicitly skipped: {skipped_names})"
            )
        else:
            print("PASS: all smoke tests passed")
        return 0

    except Exception as exc:
        fail_line(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
