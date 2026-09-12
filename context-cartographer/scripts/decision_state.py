#!/usr/bin/env python3
"""Validate, migrate, and evolve Context Cartographer decision-discovery state.

Version 1 is the legacy schema and keeps its original semantics. Version 2 adds
the answer source kind, the project stage, the authorization basis, observed
facts versus desired state, blocking versus deferred questions, idea-revision
tracking, and stale dependents.

Both versions validate through the same entry point. Migration and revision are
explicit, pure, in-memory operations that print to stdout; nothing in this
module writes to disk, so no state file is ever rewritten implicitly.

The validator is structural. It never certifies that a recorded fact is true
and never treats a recorded authorization as permission granted by the script.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


LEGACY_STATE_VERSION = 1
STATE_VERSION = 2
SUPPORTED_STATE_VERSIONS = (LEGACY_STATE_VERSION, STATE_VERSION)
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
SESSION_STATUSES = {"active", "ready_for_confirmation", "confirmed"}
FACT_STATUSES = {"verified", "uncertain", "conflicting"}
DECISION_STATUSES = {"pending", "resolved", "blocked", "stale", "deferred"}
CONFLICT_STATUSES = {"open", "resolved"}
SOURCE_KINDS = {"conversation", "native", "questionnaire", "saved_document", "unknown"}
AUTHORITY_MODES = {"discussion", "design", "implementation", "unknown"}
PROJECT_STAGES = {"idea", "planned", "implemented", "unknown"}
# An authorized mode also covers the lower, less consequential modes.
MODE_RANK = {"unknown": -1, "discussion": 0, "design": 1, "implementation": 2}
REVISION_LENGTH = 16
V2_STATE_FIELDS = (
    "source_kind",
    "stage",
    "authority",
    "desired_state",
    "next_step",
    "previous_next_steps",
)
COMPANION_CLI_FLAGS = ("answer", "reason", "source_kind")
V2_DECISION_FIELDS = (
    "blocking",
    "previous_answers",
    "stale_reason",
    "answer_source_kind",
    "resolution_reason",
)


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


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise DecisionStateError(f"{label} must be a boolean")
    return value


def _is_state_version(value: Any) -> bool:
    # bool is a subclass of int, so ``version: true`` must be rejected explicitly.
    return isinstance(value, int) and not isinstance(value, bool) and value in SUPPORTED_STATE_VERSIONS


def _validate_id(value: Any, label: str) -> str:
    item_id = _require_text(value, label)
    if not ID_RE.fullmatch(item_id):
        raise DecisionStateError(f"{label} must match {ID_RE.pattern}")
    return item_id


def _validate_choice(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise DecisionStateError(f"{label} must be one of: {', '.join(sorted(allowed))}")
    return value


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


def _reject_v2_fields(
    state: dict[str, Any],
    decisions: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    """Refuse version 2 fields under version 1 instead of silently ignoring them."""

    for field in V2_STATE_FIELDS:
        if field in state:
            raise DecisionStateError(f"{field} requires version {STATE_VERSION}")
    for index, conflict in enumerate(conflicts):
        if "blocking" in conflict:
            raise DecisionStateError(f"conflicts[{index}].blocking requires version {STATE_VERSION}")
    for index, decision in enumerate(decisions):
        for field in V2_DECISION_FIELDS:
            if field in decision:
                raise DecisionStateError(f"decisions[{index}].{field} requires version {STATE_VERSION}")


def _normalize_session_status(state: dict[str, Any]) -> None:
    state["status"] = _validate_choice(state.get("status"), SESSION_STATUSES, "status")


def _normalize_facts(state: dict[str, Any]) -> list[dict[str, Any]]:
    facts = [
        _require_object(item, f"facts[{index}]")
        for index, item in enumerate(_require_list(state.get("facts", []), "facts"))
    ]
    _validate_unique_ids(facts, "facts")
    for index, fact in enumerate(facts):
        fact["statement"] = _require_text(fact.get("statement"), f"facts[{index}].statement")
        fact["source"] = _require_text(fact.get("source"), f"facts[{index}].source")
        fact["status"] = _validate_choice(fact.get("status"), FACT_STATUSES, f"facts[{index}].status")
    return facts


def _normalize_conflicts(state: dict[str, Any], version: int) -> list[dict[str, Any]]:
    conflicts = [
        _require_object(item, f"conflicts[{index}]")
        for index, item in enumerate(_require_list(state.get("conflicts", []), "conflicts"))
    ]
    _validate_unique_ids(conflicts, "conflicts")
    for index, conflict in enumerate(conflicts):
        conflict["description"] = _require_text(conflict.get("description"), f"conflicts[{index}].description")
        conflict["status"] = _validate_choice(
            conflict.get("status"), CONFLICT_STATUSES, f"conflicts[{index}].status"
        )
        if conflict["status"] == "resolved" and not _has_answer(conflict.get("resolution")):
            raise DecisionStateError(f"conflicts[{index}].resolution is required when status is resolved")
        # An unassigned conflict is blocking: an open disagreement must never be
        # silently downgraded to non-blocking bookkeeping.
        if version == STATE_VERSION:
            conflict["blocking"] = _require_bool(
                conflict.get("blocking", True), f"conflicts[{index}].blocking"
            )
    return conflicts


def _normalize_v2_decision(decision: dict[str, Any], label: str, decision_status: str) -> None:
    decision["blocking"] = _require_bool(decision.get("blocking", True), f"{label}.blocking")

    previous_answers = []
    for position, item in enumerate(
        _require_list(decision.get("previous_answers", []), f"{label}.previous_answers")
    ):
        entry_label = f"{label}.previous_answers[{position}]"
        entry = _require_object(item, entry_label)
        if "answer" not in entry:
            raise DecisionStateError(f"{entry_label}.answer is required")
        reason = entry.get("reason")
        if reason is not None:
            reason = _require_text(reason, f"{entry_label}.reason")
        previous_answers.append({"answer": copy.deepcopy(entry["answer"]), "reason": reason})
    decision["previous_answers"] = previous_answers

    source_kind = decision.get("answer_source_kind")
    if source_kind is not None:
        decision["answer_source_kind"] = _validate_choice(
            source_kind, SOURCE_KINDS, f"{label}.answer_source_kind"
        )

    stale_reason = decision.get("stale_reason")
    if stale_reason is not None:
        decision["stale_reason"] = _require_text(stale_reason, f"{label}.stale_reason")

    resolution_reason = decision.get("resolution_reason")
    if resolution_reason is not None:
        decision["resolution_reason"] = _require_text(resolution_reason, f"{label}.resolution_reason")

    if decision_status == "deferred" and decision["blocking"]:
        raise DecisionStateError(f"{label} is deferred but still marked blocking")
    if decision_status == "stale":
        if decision.get("answer") is not None:
            raise DecisionStateError(f"{label} is stale and must not carry an active answer")
        decision["answer"] = None


def _normalize_v2_state(state: dict[str, Any]) -> None:
    state["source_kind"] = _validate_choice(
        state.get("source_kind", "unknown"), SOURCE_KINDS, "source_kind"
    )
    state["stage"] = _validate_choice(state.get("stage", "unknown"), PROJECT_STAGES, "stage")

    desired_state = [
        _require_object(item, f"desired_state[{index}]")
        for index, item in enumerate(_require_list(state.get("desired_state", []), "desired_state"))
    ]
    _validate_unique_ids(desired_state, "desired_state")
    for index, item in enumerate(desired_state):
        item["statement"] = _require_text(item.get("statement"), f"desired_state[{index}].statement")
        source = item.get("source")
        if source is not None:
            item["source"] = _require_text(source, f"desired_state[{index}].source")
    state["desired_state"] = desired_state

    authority = state.get("authority")
    if authority is not None:
        authority = dict(_require_object(authority, "authority"))
        mode = _validate_choice(authority.get("mode"), AUTHORITY_MODES, "authority.mode")
        scope = [
            _require_text(item, f"authority.scope[{index}]")
            for index, item in enumerate(_require_list(authority.get("scope", []), "authority.scope"))
        ]
        evidence = authority.get("evidence")
        if evidence is None or (isinstance(evidence, str) and not evidence.strip()):
            if mode != "unknown":
                raise DecisionStateError(
                    "authority.evidence must be a non-empty string when authority.mode is known"
                )
            evidence = ""
        elif not isinstance(evidence, str):
            raise DecisionStateError(
                "authority.evidence must be a non-empty string when authority.mode is known"
            )
        else:
            evidence = evidence.strip()
        state["authority"] = {"mode": mode, "scope": scope, "evidence": evidence}

    next_step = state.get("next_step")
    if isinstance(next_step, str):
        state["next_step"] = _require_text(next_step, "next_step")
    elif isinstance(next_step, dict):
        entry = dict(_require_object(next_step, "next_step"))
        entry_revision = entry.get("revision")
        state["next_step"] = {
            "step": _require_text(entry.get("step"), "next_step.step"),
            "revision": (
                _require_text(entry_revision, "next_step.revision")
                if entry_revision is not None
                else None
            ),
        }
    elif next_step is not None:
        raise DecisionStateError("next_step must be a non-empty string or an object with a step")

    if "previous_next_steps" in state:
        previous_steps = []
        for position, item in enumerate(
            _require_list(state.get("previous_next_steps", []), "previous_next_steps")
        ):
            label = f"previous_next_steps[{position}]"
            entry = _require_object(item, label)
            entry_reason = entry.get("reason")
            previous_steps.append(
                {
                    "step": _require_text(entry.get("step"), f"{label}.step"),
                    "reason": (
                        _require_text(entry_reason, f"{label}.reason")
                        if entry_reason is not None
                        else None
                    ),
                }
            )
        state["previous_next_steps"] = previous_steps


def _normalize_decisions(state: dict[str, Any], version: int) -> list[dict[str, Any]]:
    decisions = [
        _require_object(item, f"decisions[{index}]")
        for index, item in enumerate(_require_list(state.get("decisions", []), "decisions"))
    ]
    if not decisions:
        raise DecisionStateError("decisions must contain at least one decision")
    decision_ids = _validate_unique_ids(decisions, "decisions")
    conflict_ids = {item["id"] for item in state.get("conflicts", [])}

    if version == LEGACY_STATE_VERSION:
        _reject_v2_fields(state, decisions, state.get("conflicts", []))

    for index, decision in enumerate(decisions):
        label = f"decisions[{index}]"
        decision["question"] = _require_text(decision.get("question"), f"{label}.question")
        decision_status = _validate_choice(decision.get("status"), DECISION_STATUSES, f"{label}.status")

        dependencies = _require_list(decision.get("depends_on", []), f"{label}.depends_on")
        decision["depends_on"] = [_validate_id(item, f"{label}.depends_on") for item in dependencies]
        if len(set(decision["depends_on"])) != len(decision["depends_on"]):
            raise DecisionStateError(f"{label}.depends_on contains duplicates")
        for dependency in decision["depends_on"]:
            if dependency not in decision_ids:
                raise DecisionStateError(f"decision {decision['id']} depends on unknown decision: {dependency}")
            if dependency == decision["id"]:
                raise DecisionStateError(f"decision {decision['id']} cannot depend on itself")

        related_conflicts = _require_list(decision.get("conflicts", []), f"{label}.conflicts")
        decision["conflicts"] = [_validate_id(item, f"{label}.conflicts") for item in related_conflicts]
        if len(set(decision["conflicts"])) != len(decision["conflicts"]):
            raise DecisionStateError(f"{label}.conflicts contains duplicates")
        for conflict_id in decision["conflicts"]:
            if conflict_id not in conflict_ids:
                raise DecisionStateError(f"decision {decision['id']} references unknown conflict: {conflict_id}")

        recommendation = decision.get("recommendation")
        if recommendation is not None and (not isinstance(recommendation, str) or not recommendation.strip()):
            raise DecisionStateError(f"{label}.recommendation must be null or a non-empty string")
        if decision_status == "resolved" and not _has_answer(decision.get("answer")):
            raise DecisionStateError(f"{label}.answer is required when status is resolved")
        if decision_status == "blocked":
            _require_text(decision.get("blocker"), f"{label}.blocker")
        if version == STATE_VERSION:
            _normalize_v2_decision(decision, label, decision_status)
    return decisions


def _detect_dependency_cycle(decisions: list[dict[str, Any]]) -> None:
    """Report a dependency cycle without recursing, so long chains stay safe."""

    graph = {item["id"]: item["depends_on"] for item in decisions}
    dependents: dict[str, list[str]] = {decision_id: [] for decision_id in graph}
    pending_dependencies = {}
    for decision_id, dependencies in graph.items():
        pending_dependencies[decision_id] = len(dependencies)
        for dependency in dependencies:
            dependents[dependency].append(decision_id)

    # Kahn's algorithm: repeatedly settle decisions whose dependencies are settled.
    queue = [decision_id for decision_id, count in pending_dependencies.items() if count == 0]
    settled: set[str] = set()
    while queue:
        decision_id = queue.pop()
        settled.add(decision_id)
        for dependent in dependents[decision_id]:
            pending_dependencies[dependent] -= 1
            if pending_dependencies[dependent] == 0:
                queue.append(dependent)

    unresolved = [decision_id for decision_id in graph if decision_id not in settled]
    if not unresolved:
        return
    unresolved_set = set(unresolved)

    # Every unresolved node keeps at least one unresolved dependency, so walking
    # that subgraph always reaches a node it has already visited.
    trail: list[str] = []
    position: dict[str, int] = {}
    node = unresolved[0]
    while node not in position:
        position[node] = len(trail)
        trail.append(node)
        node = next(item for item in graph[node] if item in unresolved_set)
    cycle = trail[position[node]:] + [node]
    raise DecisionStateError(f"decision dependency cycle: {' -> '.join(cycle)}")


def _check_resolution_order(decisions: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> None:
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


def validate_state(raw_state: Any) -> dict[str, Any]:
    """Return a normalized copy of the state or raise DecisionStateError.

    The caller's input is never modified: normalization works on a deep copy
    because the earlier version mutated nested fact and decision objects in
    place.
    """

    raw = _require_object(raw_state, "decision state")
    version = raw.get("version")
    if not _is_state_version(version):
        allowed = ", ".join(str(item) for item in SUPPORTED_STATE_VERSIONS)
        raise DecisionStateError(f"version must be one of: {allowed}")

    state = copy.deepcopy(raw)
    state["topic"] = _require_text(state.get("topic"), "topic")
    _normalize_session_status(state)

    facts = _normalize_facts(state)
    conflicts = _normalize_conflicts(state, version)
    state["facts"] = facts
    state["conflicts"] = conflicts

    decisions = _normalize_decisions(state, version)
    if version == STATE_VERSION:
        _normalize_v2_state(state)
    state["decisions"] = decisions

    _detect_dependency_cycle(decisions)
    _check_resolution_order(decisions, conflicts)

    state["out_of_scope"] = [
        _require_text(item, f"out_of_scope[{index}]")
        for index, item in enumerate(_require_list(state.get("out_of_scope", []), "out_of_scope"))
    ]

    summary = summarize_state(state)
    if state["status"] in {"ready_for_confirmation", "confirmed"} and not summary["ready"]:
        raise DecisionStateError(
            f"status {state['status']} requires all decisions and conflicts to be resolved; "
            "only deferred non-blocking items may stay open"
        )
    return state


def _is_blocking_decision(decision: dict[str, Any]) -> bool:
    return bool(decision.get("blocking", True)) and decision.get("status") != "resolved"


def _is_blocking_conflict(conflict: dict[str, Any]) -> bool:
    """An open conflict is blocking unless it is explicitly marked otherwise."""

    return conflict.get("status") == "open" and bool(conflict.get("blocking", True))


def idea_revision(state: dict[str, Any]) -> str:
    """Return a deterministic token for the current revision of the idea.

    The token covers the topic, the project stage, the desired state, the
    observed facts, the decisions, and the conflicts, so a changed answer, a new
    fact, or a newly opened disagreement makes a tool result computed against
    the previous token stale. Volatile bookkeeping such as the session status
    and the authorization note is deliberately excluded.
    """

    def identifier(item: dict[str, Any]) -> str:
        return str(item.get("id", ""))

    def sorted_dicts(items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        return sorted((item for item in items if isinstance(item, dict)), key=identifier)

    projection = {
        "topic": state.get("topic"),
        "stage": state.get("stage") or "unknown",
        "desired_state": [
            {"id": item.get("id"), "statement": item.get("statement"), "source": item.get("source")}
            for item in sorted_dicts(state.get("desired_state"))
        ],
        "conflicts": [
            {
                "id": item.get("id"),
                "description": item.get("description"),
                "status": item.get("status"),
                "resolution": item.get("resolution"),
                "blocking": item.get("blocking", True),
            }
            for item in sorted_dicts(state.get("conflicts"))
        ],
        "facts": [
            {
                "id": item.get("id"),
                "statement": item.get("statement"),
                "source": item.get("source"),
                "status": item.get("status"),
            }
            for item in sorted_dicts(state.get("facts"))
        ],
        "decisions": [
            {
                "id": item.get("id"),
                "question": item.get("question"),
                "answer": item.get("answer"),
                "status": item.get("status"),
                "depends_on": sorted(str(dep) for dep in (item.get("depends_on") or [])),
                "conflicts": sorted(str(conf) for conf in (item.get("conflicts") or [])),
                "blocking": item.get("blocking", True),
            }
            for item in sorted_dicts(state.get("decisions"))
        ],
    }
    blob = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:REVISION_LENGTH]


def is_result_current(state: dict[str, Any], revision: Any) -> bool:
    """Report whether a tool result computed at ``revision`` is still current."""

    if not isinstance(revision, str) or not revision.strip():
        return False
    return idea_revision(state) == revision.strip()


def authorized_for(state: dict[str, Any], mode: str, scope_item: str | None = None) -> bool:
    """Report whether the recorded authorization covers ``mode``.

    A recorded ``implementation`` mode covers ``design`` and ``discussion``; a
    recorded ``discussion`` mode never covers design or implementation. The
    check fails closed: an absent or empty scope never authorizes a requested
    item, and a substantive mode (``design`` or ``implementation``) needs a
    bounded recorded scope even when no particular item is named. The structural
    validator does not grant anything: this function only reads the
    authorization the user already gave.
    """

    if mode not in MODE_RANK:
        raise DecisionStateError(f"unknown authority mode: {mode}")
    if MODE_RANK[mode] < 0:
        return False
    authority = state.get("authority")
    if not isinstance(authority, dict):
        return False
    granted = authority.get("mode", "unknown")
    if MODE_RANK.get(granted, -1) < MODE_RANK[mode]:
        return False
    scope = authority.get("scope") or []
    if scope_item is not None:
        return scope_item in scope
    if mode == "discussion":
        return True
    return bool(scope)


def compute_readiness(state: dict[str, Any]) -> dict[str, Any]:
    """Report readiness for the next authorized stage, not for every future question."""

    decisions = state.get("decisions") or []
    conflicts = state.get("conflicts") or []
    authority = state.get("authority")
    mode = authority.get("mode", "unknown") if isinstance(authority, dict) else "unknown"
    if mode not in MODE_RANK:
        mode = "unknown"
    stage = mode if mode != "unknown" else "discussion"

    open_blocking = [item["id"] for item in decisions if _is_blocking_decision(item)]
    blocked_ids = [
        item["id"] for item in decisions if item.get("blocking", True) and item.get("status") == "blocked"
    ]
    deferred_ids = [
        item["id"] for item in decisions if item.get("status") == "deferred" or not item.get("blocking", True)
    ]
    # An open conflict gates by default; only an explicit ``blocking: false``
    # removes it, so an unassigned disagreement is never silently non-blocking.
    gating_conflicts = [conflict["id"] for conflict in conflicts if _is_blocking_conflict(conflict)]
    authorized = authorized_for(state, stage)

    if mode == "unknown":
        ready = False
        reason = "no authorized stage is recorded yet"
    elif mode == "discussion":
        # Pending questions are the substance of the interview, so only a truly
        # blocked decision or an open gating conflict stops the discussion.
        ready = not blocked_ids and not gating_conflicts
        reason = (
            "discussion can continue; pending questions are expected"
            if ready
            else "a blocking decision is blocked or an open conflict needs an authoritative choice"
        )
    else:
        ready = authorized and not open_blocking and not gating_conflicts
        reason = (
            f"no blocking unknowns remain for the {mode} stage"
            if ready
            else "the stage is not authorized or blocking decisions or conflicts are still unresolved"
        )

    return {
        "project_stage": state.get("stage", "unknown"),
        "mode": mode,
        "stage": stage,
        "authorized": authorized,
        "ready": bool(ready),
        "blocking_decisions": open_blocking,
        "blocking_conflicts": gating_conflicts,
        "deferred_decisions": deferred_ids,
        "reason": reason,
    }


def _current_stored_next_step(state: dict[str, Any]) -> str | None:
    """Return the stored next step only while it still applies.

    A plain string is accepted because ``revise_decision`` archives and clears
    the stored step whenever a decision meaning changes. A structured step may
    pin the idea revision it was written for; a step pinned to an older revision
    is ignored instead of being recommended.
    """

    stored = state.get("next_step")
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    if isinstance(stored, dict):
        step = stored.get("step")
        revision = stored.get("revision")
        if isinstance(step, str) and step.strip():
            if revision is None or is_result_current(state, revision):
                return step.strip()
    return None


def next_useful_step(state: dict[str, Any]) -> str | None:
    """Return the single most useful next step for resuming the session.

    Open blocking work is reported before any stored or generic hint, so a saved
    plan can never mask a stale decision, a disagreement, or an unanswered
    blocking question.
    """

    decisions = state.get("decisions") or []
    conflicts = state.get("conflicts") or []

    open_conflicts = [
        item for item in conflicts if isinstance(item, dict) and _is_blocking_conflict(item)
    ]
    if open_conflicts:
        return f"resolve open conflict '{open_conflicts[0].get('id')}'"

    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("status") == "stale" and decision.get("blocking", True):
            return f"revisit stale decision '{decision.get('id')}'"

    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("status") == "blocked" and decision.get("blocking", True):
            return f"resolve blocked decision '{decision.get('id')}'"

    status_by_decision = {
        item.get("id"): item.get("status") for item in decisions if isinstance(item, dict)
    }
    status_by_conflict = {
        item.get("id"): item.get("status") for item in conflicts if isinstance(item, dict)
    }
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("status") != "pending":
            continue
        if not decision.get("blocking", True):
            continue
        dependencies_ready = all(
            status_by_decision.get(item) == "resolved" for item in (decision.get("depends_on") or [])
        )
        conflicts_ready = all(
            status_by_conflict.get(item) == "resolved" for item in (decision.get("conflicts") or [])
        )
        if dependencies_ready and conflicts_ready:
            return f"answer decision '{decision.get('id')}'"

    stored = _current_stored_next_step(state)
    if stored is not None:
        return stored

    readiness = compute_readiness(state)
    if readiness.get("ready"):
        return f"continue with the authorized {readiness.get('mode')} stage"
    if readiness.get("mode") == "unknown":
        return "record the authorization basis for the next stage"
    if not readiness.get("authorized"):
        return f"record a bounded authorization scope for the {readiness.get('mode')} stage"
    return None


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Summarize a validated or structurally compatible decision state.

    ``ready`` is informational: it reports that no blocking decision or
    conflict is still open, which is what the confirmation status needs. The
    nested ``readiness`` mapping separately reports whether the next authorized
    stage may proceed, so a state with resolved decisions but no recorded
    authorization is still confirmable while its stage readiness stays False.
    """

    decisions = state.get("decisions", [])
    conflicts = state.get("conflicts", [])
    status_by_decision = {item["id"]: item["status"] for item in decisions}
    status_by_conflict = {item["id"]: item["status"] for item in conflicts}
    frontier = []
    for decision in decisions:
        if decision["status"] not in {"pending", "stale"}:
            continue
        dependencies_ready = all(
            status_by_decision.get(item) == "resolved" for item in decision.get("depends_on", [])
        )
        conflicts_ready = all(
            status_by_conflict.get(item) == "resolved" for item in decision.get("conflicts", [])
        )
        if dependencies_ready and conflicts_ready:
            frontier.append(decision["id"])

    counts = {
        status: sum(item["status"] == status for item in decisions) for status in sorted(DECISION_STATUSES)
    }
    open_conflicts = sum(item["status"] == "open" for item in conflicts)
    blocking_open = [item["id"] for item in decisions if _is_blocking_decision(item)]
    open_blocking_conflicts = [item["id"] for item in conflicts if _is_blocking_conflict(item)]
    return {
        "topic": state.get("topic"),
        "status": state.get("status"),
        "total_decisions": len(decisions),
        **counts,
        "open_conflicts": open_conflicts,
        "open_blocking_conflicts": open_blocking_conflicts,
        "frontier": frontier,
        "blocking_open": blocking_open,
        "ready": bool(decisions) and not blocking_open and not open_blocking_conflicts,
        "source_kind": state.get("source_kind", "unknown"),
        "stage": state.get("stage", "unknown"),
        "idea_revision": idea_revision(state),
        "next_step": next_useful_step(state),
        "readiness": compute_readiness(state),
    }


def upgrade_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a version 2 copy of any supported state without touching disk.

    Values that version 1 never recorded become ``"unknown"`` instead of a
    guessed value. The caller's mapping is not modified, and no file is written.
    """

    validated = validate_state(state)
    if validated.get("version") == STATE_VERSION:
        return validated

    upgraded: dict[str, Any] = {
        "version": STATE_VERSION,
        "topic": validated["topic"],
        "status": validated["status"],
        "source_kind": "unknown",
        "stage": "unknown",
        "authority": {"mode": "unknown", "scope": [], "evidence": ""},
        "facts": copy.deepcopy(validated.get("facts", [])),
        "desired_state": [],
        "conflicts": copy.deepcopy(validated.get("conflicts", [])),
        "decisions": [],
        "out_of_scope": list(validated.get("out_of_scope", [])),
    }
    for decision in validated.get("decisions", []):
        migrated = {
            "id": decision["id"],
            "question": decision["question"],
            "status": decision["status"],
            "depends_on": list(decision["depends_on"]),
            "conflicts": list(decision["conflicts"]),
            "recommendation": decision.get("recommendation"),
            "answer": decision.get("answer"),
            "blocking": True,
            "previous_answers": [],
        }
        if decision.get("blocker"):
            migrated["blocker"] = decision["blocker"]
        upgraded["decisions"].append(migrated)
    return validate_state(upgraded)


def _transitive_dependents(decisions: list[dict[str, Any]], decision_id: str) -> set[str]:
    children: dict[str, list[str]] = {}
    for decision in decisions:
        for dependency in decision.get("depends_on", []):
            children.setdefault(dependency, []).append(decision["id"])
    seen: set[str] = set()
    queue = list(children.get(decision_id, []))
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        queue.extend(children.get(current, []))
    return seen


def _archive_answer(decision: dict[str, Any], reason: str) -> None:
    if _has_answer(decision.get("answer")):
        decision.setdefault("previous_answers", []).append(
            {"answer": copy.deepcopy(decision["answer"]), "reason": reason}
        )


def _canonical_answer(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _archive_next_step(state: dict[str, Any], reason: str) -> None:
    """Archive and clear a stored next step whose premise just changed."""

    stored = state.get("next_step")
    step_text = None
    if isinstance(stored, str) and stored.strip():
        step_text = stored.strip()
    elif isinstance(stored, dict) and isinstance(stored.get("step"), str) and stored["step"].strip():
        step_text = stored["step"].strip()
    if step_text is None:
        return
    state.setdefault("previous_next_steps", []).append({"step": step_text, "reason": reason})
    state["next_step"] = None


def revise_decision(
    state: dict[str, Any],
    decision_id: str,
    answer: Any,
    *,
    reason: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    """Return a new version 2 state with one decision re-answered.

    Previously resolved dependents are invalidated transitively: each keeps its
    old answer in ``previous_answers`` and becomes ``stale`` rather than staying
    active. Facts, conflicts, and unrelated decisions are preserved. Nothing is
    written to disk.
    """

    validated = validate_state(state)
    if validated.get("version") != STATE_VERSION:
        raise DecisionStateError(
            "revise_decision requires a version 2 state; run upgrade_state() first"
        )
    if not isinstance(decision_id, str) or not ID_RE.fullmatch(decision_id):
        raise DecisionStateError(f"decision id must match {ID_RE.pattern}")
    if not _has_answer(answer):
        raise DecisionStateError("a revised decision requires a non-empty answer")
    if source_kind is not None:
        source_kind = _validate_choice(source_kind, SOURCE_KINDS, "source_kind")
    if reason is not None:
        reason = _require_text(reason, "reason")

    before_revision = idea_revision(validated)
    working = copy.deepcopy(validated)
    target = next((item for item in working["decisions"] if item["id"] == decision_id), None)
    if target is None:
        raise DecisionStateError(f"unknown decision: {decision_id}")

    if target["status"] == "resolved" and _canonical_answer(target.get("answer")) == _canonical_answer(answer):
        # Re-stating the same answer does not change the decision meaning, so
        # dependents stay valid instead of being invalidated.
        if reason is not None:
            target["resolution_reason"] = reason
        if source_kind is not None:
            target["answer_source_kind"] = source_kind
        return validate_state(working)

    _archive_answer(target, "replaced by a later answer")
    target["answer"] = copy.deepcopy(answer)
    target["status"] = "resolved"
    target.pop("stale_reason", None)
    if reason is not None:
        target["resolution_reason"] = reason
    if source_kind is not None:
        target["answer_source_kind"] = source_kind
    _archive_next_step(working, f"decision '{decision_id}' changed")

    dependents = _transitive_dependents(working["decisions"], decision_id)
    invalidated = []
    for decision in working["decisions"]:
        if decision["id"] not in dependents or decision["status"] != "resolved":
            continue
        _archive_answer(decision, f"dependency '{decision_id}' changed")
        decision["answer"] = None
        decision["status"] = "stale"
        decision.pop("stale_reason", None)
        invalidated.append(decision)

    # The quoted revision must describe the state that results from the
    # invalidation, so compute the token after the dependents were rewritten.
    after_revision = idea_revision(working)
    for decision in invalidated:
        decision["stale_reason"] = (
            f"dependency '{decision_id}' changed (revision {before_revision} -> {after_revision})"
        )

    if (
        working.get("status") in {"ready_for_confirmation", "confirmed"}
        and not summarize_state(working)["ready"]
    ):
        working["status"] = "active"
    return validate_state(working)


def load_state(path: Path) -> dict[str, Any]:
    try:
        raw_state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DecisionStateError(f"state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DecisionStateError(f"malformed JSON in {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise DecisionStateError(f"could not decode {path} as UTF-8: {exc}") from exc
    except OSError as exc:
        raise DecisionStateError(f"could not read {path}: {exc}") from exc
    return validate_state(raw_state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate, migrate, and inspect decision-discovery state.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(".project-questionnaire/decision-state.json"),
        help="Path to decision-state.json.",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--validate-only", action="store_true", help="Validate state and print a short result.")
    actions.add_argument("--json", action="store_true", help="Print the status summary as JSON.")
    actions.add_argument(
        "--idea-revision", action="store_true", help="Print the current idea-revision token."
    )
    actions.add_argument(
        "--upgrade-to-v2",
        action="store_true",
        help="Print a migrated version 2 state on stdout; never writes the file.",
    )
    actions.add_argument("--next-step", action="store_true", help="Print the next useful step for this session.")
    actions.add_argument(
        "--readiness",
        action="store_true",
        help="Print readiness for the next authorized stage as JSON.",
    )
    actions.add_argument(
        "--check-authorization",
        metavar="MODE",
        choices=sorted(AUTHORITY_MODES),
        help="Exit 0 when the recorded authorization covers MODE, 3 otherwise.",
    )
    actions.add_argument(
        "--revise-decision",
        metavar="DECISION_ID",
        help="Print a revised version 2 state on stdout; never writes the file.",
    )
    parser.add_argument("--answer", help="Answer text for --revise-decision.")
    parser.add_argument("--reason", help="Optional reason recorded with a revised answer.")
    parser.add_argument("--source-kind", choices=sorted(SOURCE_KINDS), help="Where a revised answer came from.")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.revise_decision is None:
        stray_flags = [
            f"--{name.replace('_', '-')}"
            for name in COMPANION_CLI_FLAGS
            if getattr(args, name) is not None
        ]
        if stray_flags:
            print(
                f"ERROR: {', '.join(stray_flags)} requires --revise-decision",
                file=sys.stderr,
            )
            return 2

    try:
        state = load_state(args.input)
    except DecisionStateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"PASS: decision state is valid ({args.input})")
        return 0
    if args.idea_revision:
        print(idea_revision(state))
        return 0
    if args.upgrade_to_v2:
        print(json.dumps(upgrade_state(state), ensure_ascii=False, indent=2))
        return 0
    if args.next_step:
        step = next_useful_step(state)
        print(step if step else "none")
        return 0
    if args.readiness:
        print(json.dumps(compute_readiness(state), ensure_ascii=False, indent=2))
        return 0
    if args.check_authorization:
        if authorized_for(state, args.check_authorization):
            print(f"authorized: {args.check_authorization}")
            return 0
        print(f"not authorized: {args.check_authorization}")
        return 3
    if args.revise_decision:
        if not args.answer or not args.answer.strip():
            print("ERROR: --revise-decision requires --answer", file=sys.stderr)
            return 2
        working = state if state.get("version") == STATE_VERSION else upgrade_state(state)
        try:
            revised = revise_decision(
                working,
                args.revise_decision,
                args.answer,
                reason=args.reason,
                source_kind=args.source_kind,
            )
        except DecisionStateError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(revised, ensure_ascii=False, indent=2))
        return 0

    summary = summarize_state(state)
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
    print(f"All blocking decisions and conflicts resolved (informational): {'yes' if summary['ready'] else 'no'}")
    readiness = summary["readiness"]
    print(
        "Next stage readiness (authorized): "
        f"{'ready' if readiness['ready'] else 'not ready'} "
        f"[stage={readiness['stage']}, authorized={'yes' if readiness['authorized'] else 'no'}, "
        f"blockers={', '.join(readiness['blocking_decisions'] + readiness['blocking_conflicts']) or 'none'}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
