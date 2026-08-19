#!/usr/bin/env python3
"""Validate and summarize Context Cartographer decision-discovery state."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STATE_VERSION = 1
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
SESSION_STATUSES = {"active", "ready_for_confirmation", "confirmed"}
FACT_STATUSES = {"verified", "uncertain", "conflicting"}
DECISION_STATUSES = {"pending", "resolved", "blocked"}
CONFLICT_STATUSES = {"open", "resolved"}


class DecisionStateError(ValueError):
    """Raised when decision-state JSON is malformed or inconsistent."""


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionStateError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DecisionStateError(f"{label} must be an array")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionStateError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_id(value: Any, label: str) -> str:
    item_id = _require_text(value, label)
    if not ID_RE.fullmatch(item_id):
        raise DecisionStateError(f"{label} must match {ID_RE.pattern}")
    return item_id


def _has_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _validate_unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(items):
        item_id = _validate_id(item.get("id"), f"{label}[{index}].id")
        if item_id in ids:
            raise DecisionStateError(f"duplicate {label} id: {item_id}")
        ids.add(item_id)
    return ids


def _detect_dependency_cycle(decisions: list[dict[str, Any]]) -> None:
    graph = {item["id"]: item["depends_on"] for item in decisions}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            cycle_start = trail.index(node)
            cycle = trail[cycle_start:] + [node]
            raise DecisionStateError(f"decision dependency cycle: {' -> '.join(cycle)}")
        if node in visited:
            return
        visiting.add(node)
        trail.append(node)
        for dependency in graph[node]:
            visit(dependency, trail)
        trail.pop()
        visiting.remove(node)
        visited.add(node)

    for decision_id in graph:
        visit(decision_id, [])


def validate_state(raw_state: Any) -> dict[str, Any]:
    """Return a normalized state or raise DecisionStateError."""

    state = dict(_require_object(raw_state, "decision state"))
    if state.get("version") != STATE_VERSION:
        raise DecisionStateError(f"version must be {STATE_VERSION}")
    state["topic"] = _require_text(state.get("topic"), "topic")
    status = state.get("status")
    if status not in SESSION_STATUSES:
        raise DecisionStateError(f"status must be one of: {', '.join(sorted(SESSION_STATUSES))}")

    facts = [_require_object(item, f"facts[{index}]") for index, item in enumerate(_require_list(state.get("facts", []), "facts"))]
    _validate_unique_ids(facts, "facts")
    for index, fact in enumerate(facts):
        fact["statement"] = _require_text(fact.get("statement"), f"facts[{index}].statement")
        fact["source"] = _require_text(fact.get("source"), f"facts[{index}].source")
        if fact.get("status") not in FACT_STATUSES:
            raise DecisionStateError(f"facts[{index}].status must be one of: {', '.join(sorted(FACT_STATUSES))}")

    conflicts = [
        _require_object(item, f"conflicts[{index}]")
        for index, item in enumerate(_require_list(state.get("conflicts", []), "conflicts"))
    ]
    conflict_ids = _validate_unique_ids(conflicts, "conflicts")
    for index, conflict in enumerate(conflicts):
        conflict["description"] = _require_text(conflict.get("description"), f"conflicts[{index}].description")
        if conflict.get("status") not in CONFLICT_STATUSES:
            raise DecisionStateError(
                f"conflicts[{index}].status must be one of: {', '.join(sorted(CONFLICT_STATUSES))}"
            )
        if conflict["status"] == "resolved" and not _has_answer(conflict.get("resolution")):
            raise DecisionStateError(f"conflicts[{index}].resolution is required when status is resolved")

    decisions = [
        _require_object(item, f"decisions[{index}]")
        for index, item in enumerate(_require_list(state.get("decisions"), "decisions"))
    ]
    if not decisions:
        raise DecisionStateError("decisions must contain at least one decision")
    decision_ids = _validate_unique_ids(decisions, "decisions")

    for index, decision in enumerate(decisions):
        decision["question"] = _require_text(decision.get("question"), f"decisions[{index}].question")
        if decision.get("status") not in DECISION_STATUSES:
            raise DecisionStateError(
                f"decisions[{index}].status must be one of: {', '.join(sorted(DECISION_STATUSES))}"
            )
        dependencies = _require_list(decision.get("depends_on", []), f"decisions[{index}].depends_on")
        decision["depends_on"] = [
            _validate_id(item, f"decisions[{index}].depends_on") for item in dependencies
        ]
        if len(set(decision["depends_on"])) != len(decision["depends_on"]):
            raise DecisionStateError(f"decisions[{index}].depends_on contains duplicates")
        for dependency in decision["depends_on"]:
            if dependency not in decision_ids:
                raise DecisionStateError(f"decision {decision['id']} depends on unknown decision: {dependency}")
            if dependency == decision["id"]:
                raise DecisionStateError(f"decision {decision['id']} cannot depend on itself")

        related_conflicts = _require_list(decision.get("conflicts", []), f"decisions[{index}].conflicts")
        decision["conflicts"] = [
            _validate_id(item, f"decisions[{index}].conflicts") for item in related_conflicts
        ]
        if len(set(decision["conflicts"])) != len(decision["conflicts"]):
            raise DecisionStateError(f"decisions[{index}].conflicts contains duplicates")
        for conflict_id in decision["conflicts"]:
            if conflict_id not in conflict_ids:
                raise DecisionStateError(f"decision {decision['id']} references unknown conflict: {conflict_id}")

        recommendation = decision.get("recommendation")
        if recommendation is not None and (not isinstance(recommendation, str) or not recommendation.strip()):
            raise DecisionStateError(f"decisions[{index}].recommendation must be null or a non-empty string")
        if decision["status"] == "resolved" and not _has_answer(decision.get("answer")):
            raise DecisionStateError(f"decisions[{index}].answer is required when status is resolved")
        if decision["status"] == "blocked":
            _require_text(decision.get("blocker"), f"decisions[{index}].blocker")

    _detect_dependency_cycle(decisions)

    decision_statuses = {item["id"]: item["status"] for item in decisions}
    conflict_statuses = {item["id"]: item["status"] for item in conflicts}
    for index, decision in enumerate(decisions):
        if decision["status"] != "resolved":
            continue
        unresolved_dependencies = [
            item for item in decision["depends_on"] if decision_statuses[item] != "resolved"
        ]
        if unresolved_dependencies:
            raise DecisionStateError(
                f"decisions[{index}] is resolved before dependencies: {', '.join(unresolved_dependencies)}"
            )
        open_related_conflicts = [
            item for item in decision["conflicts"] if conflict_statuses[item] != "resolved"
        ]
        if open_related_conflicts:
            raise DecisionStateError(
                f"decisions[{index}] is resolved while conflicts remain open: {', '.join(open_related_conflicts)}"
            )

    out_of_scope = _require_list(state.get("out_of_scope", []), "out_of_scope")
    state["out_of_scope"] = [
        _require_text(item, f"out_of_scope[{index}]") for index, item in enumerate(out_of_scope)
    ]

    state["facts"] = facts
    state["conflicts"] = conflicts
    state["decisions"] = decisions
    summary = summarize_state(state)
    if status in {"ready_for_confirmation", "confirmed"} and not summary["ready"]:
        raise DecisionStateError(f"status {status} requires all decisions and conflicts to be resolved")
    return state


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Summarize a validated or structurally compatible decision state."""

    decisions = state.get("decisions", [])
    conflicts = state.get("conflicts", [])
    status_by_decision = {item["id"]: item["status"] for item in decisions}
    status_by_conflict = {item["id"]: item["status"] for item in conflicts}
    frontier = []
    for decision in decisions:
        if decision["status"] != "pending":
            continue
        dependencies_ready = all(status_by_decision.get(item) == "resolved" for item in decision.get("depends_on", []))
        conflicts_ready = all(status_by_conflict.get(item) == "resolved" for item in decision.get("conflicts", []))
        if dependencies_ready and conflicts_ready:
            frontier.append(decision["id"])

    counts = {status: sum(item["status"] == status for item in decisions) for status in sorted(DECISION_STATUSES)}
    open_conflicts = sum(item["status"] == "open" for item in conflicts)
    return {
        "topic": state.get("topic"),
        "status": state.get("status"),
        "total_decisions": len(decisions),
        **counts,
        "open_conflicts": open_conflicts,
        "frontier": frontier,
        "ready": bool(decisions) and counts["resolved"] == len(decisions) and open_conflicts == 0,
    }


def load_state(path: Path) -> dict[str, Any]:
    try:
        raw_state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DecisionStateError(f"state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DecisionStateError(f"malformed JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise DecisionStateError(f"could not read {path}: {exc}") from exc
    return validate_state(raw_state)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and inspect decision-discovery state.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(".project-questionnaire/decision-state.json"),
        help="Path to decision-state.json.",
    )
    parser.add_argument("--validate-only", action="store_true", help="Validate state and print a short result.")
    parser.add_argument("--json", action="store_true", help="Print the status summary as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        state = load_state(args.input)
    except DecisionStateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summary = summarize_state(state)
    if args.validate_only:
        print(f"PASS: decision state is valid ({args.input})")
        return 0
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"Topic: {summary['topic']}")
    print(f"Status: {summary['status']}")
    print(
        "Decisions: "
        f"{summary['resolved']} resolved, {summary['pending']} pending, "
        f"{summary['blocked']} blocked, {summary['total_decisions']} total"
    )
    print(f"Open conflicts: {summary['open_conflicts']}")
    print(f"Frontier: {', '.join(summary['frontier']) if summary['frontier'] else 'empty'}")
    print(f"Ready for confirmation: {'yes' if summary['ready'] else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
