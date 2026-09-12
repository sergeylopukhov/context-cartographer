#!/usr/bin/env python3
"""Tests for resumable decision-discovery state.

The suite covers three layers:

* version 1 keeps its original semantics and stays valid;
* version 2 adds source kind, stage, authorization, desired state, blocking
  versus deferred questions, idea revisions and stale dependents;
* the command line wrapper validates, migrates and revises state on stdout
  without ever writing to disk.

Everything is standard library only and nothing here touches the network.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
REPO = HERE.parents[1]
SCRIPT = REPO / "scripts" / "decision_state.py"
FIXTURES = REPO / "tests" / "fixtures" / "decision-state"

_SPEC = importlib.util.spec_from_file_location(
    "context_cartographer_decision_state_tests", SCRIPT
)
decision_state = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(decision_state)


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def legacy_state():
    return load_fixture("legacy_v1.json")


def decision(decision_id, *, status="pending", **overrides):
    item = {
        "id": decision_id,
        "question": f"Question for {decision_id}?",
        "status": status,
        "depends_on": [],
        "conflicts": [],
        "recommendation": None,
        "answer": f"answer {decision_id}" if status == "resolved" else None,
        "blocking": True,
        "previous_answers": [],
    }
    item.update(overrides)
    return item


def v2_state(**overrides):
    state = {
        "version": 2,
        "topic": "Topic",
        "status": "active",
        "source_kind": "conversation",
        "stage": "idea",
        "authority": {
            "mode": "discussion",
            "scope": [],
            "evidence": "The user asked to discuss the idea first.",
        },
        "facts": [],
        "desired_state": [],
        "conflicts": [],
        "decisions": [decision("d1")],
        "out_of_scope": [],
    }
    state.update(overrides)
    return state


def chain_state(depth=3, statuses=None, **overrides):
    ids = [f"d{index}" for index in range(1, depth + 1)]
    statuses = list(statuses) if statuses else ["resolved"] * depth
    decisions = []
    for index, item_id in enumerate(ids):
        status = statuses[index]
        decisions.append(
            decision(
                item_id,
                status=status,
                depends_on=[ids[index - 1]] if index else [],
            )
        )
    return v2_state(decisions=decisions, **overrides)


def run_cli(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
    )


class LegacyCompatibilityTests(unittest.TestCase):
    def test_legacy_fixture_keeps_original_semantics(self):
        state = decision_state.validate_state(legacy_state())
        summary = decision_state.summarize_state(state)
        self.assertEqual(state["version"], 1)
        self.assertEqual(summary["frontier"], ["code_rules_mode"])
        self.assertFalse(summary["ready"])
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["resolved"], 1)

    def test_legacy_state_is_not_padded_with_version_2_fields(self):
        state = decision_state.validate_state(legacy_state())
        for field in ("source_kind", "stage", "authority", "desired_state"):
            self.assertNotIn(field, state)
        self.assertNotIn("blocking", state["decisions"][0])

    def test_version_1_rejects_version_2_state_field(self):
        state = legacy_state()
        state["stage"] = "idea"
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires version 2", str(ctx.exception))

    def test_version_1_rejects_version_2_decision_field(self):
        state = legacy_state()
        state["decisions"][1]["blocking"] = False
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires version 2", str(ctx.exception))

    def test_version_1_rejects_conflict_blocking_field(self):
        state = legacy_state()
        state["conflicts"] = [
            {"id": "c1", "description": "Disagreement", "status": "open", "blocking": False}
        ]
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires version 2", str(ctx.exception))

    def test_version_1_rejects_previous_next_steps(self):
        state = legacy_state()
        state["previous_next_steps"] = [{"step": "Ship the plan", "reason": "changed"}]
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires version 2", str(ctx.exception))

    def test_legacy_decision_is_blocking_by_default(self):
        summary = decision_state.summarize_state(decision_state.validate_state(legacy_state()))
        self.assertEqual(summary["blocking_open"], ["code_rules_mode"])
        self.assertFalse(summary["ready"])

    def test_legacy_state_can_still_reach_ready_and_confirmed(self):
        state = legacy_state()
        state["status"] = "confirmed"
        state["decisions"][1]["status"] = "resolved"
        state["decisions"][1]["answer"] = "Use code rules"
        normalized = decision_state.validate_state(state)
        summary = decision_state.summarize_state(normalized)
        self.assertEqual(normalized["version"], 1)
        self.assertEqual(normalized["status"], "confirmed")
        self.assertTrue(summary["ready"])
        self.assertTrue(summary["frontier"] == [])

    def test_legacy_ready_for_confirmation_gate_is_unchanged(self):
        state = legacy_state()
        state["status"] = "ready_for_confirmation"
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires all decisions", str(ctx.exception))


class VersionAndTypeTests(unittest.TestCase):
    def test_malformed_versions_are_rejected(self):
        for version in (True, False, 1.0, "1", "2", 3, None, []):
            state = legacy_state()
            state["version"] = version
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(version)):
                decision_state.validate_state(state)

    def test_missing_version_is_rejected(self):
        state = legacy_state()
        del state["version"]
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

    def test_state_must_be_an_object(self):
        for value in ([], "state", 3, None):
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(value)

    def test_blocking_must_be_a_real_boolean(self):
        for value in (1, 0, "true", "false", None, []):
            state = v2_state()
            state["decisions"][0]["blocking"] = value
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(state)

    def test_blocking_defaults_to_true(self):
        state = v2_state()
        del state["decisions"][0]["blocking"]
        normalized = decision_state.validate_state(state)
        self.assertIs(normalized["decisions"][0]["blocking"], True)

    def test_malformed_scalar_fields_are_rejected(self):
        cases = (
            ("topic", ""),
            ("status", "ready"),
            ("source_kind", "chat"),
            ("stage", "shipping"),
            ("next_step", "   "),
        )
        for field, value in cases:
            state = v2_state()
            state[field] = value
            with self.assertRaises(decision_state.DecisionStateError, msg=field):
                decision_state.validate_state(state)

    def test_authority_requires_known_mode_and_evidence(self):
        for mode in ("planning", "code", "", 1):
            state = v2_state()
            state["authority"] = {"mode": mode, "scope": [], "evidence": "because"}
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(mode)):
                decision_state.validate_state(state)

        state = v2_state()
        state["authority"] = {"mode": "implementation", "scope": [], "evidence": "  "}
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("evidence", str(ctx.exception))

    def test_unknown_authority_mode_accepts_empty_evidence(self):
        state = v2_state()
        state["authority"] = {"mode": "unknown", "scope": [], "evidence": ""}
        normalized = decision_state.validate_state(state)
        self.assertEqual(normalized["authority"]["mode"], "unknown")

    def test_desired_state_requires_statement_and_unique_ids(self):
        state = v2_state(desired_state=[{"id": "want", "statement": "Stay offline"}])
        self.assertEqual(len(decision_state.validate_state(state)["desired_state"]), 1)

        state = v2_state(desired_state=[{"id": "want"}])
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state(
            desired_state=[
                {"id": "want", "statement": "One"},
                {"id": "want", "statement": "Two"},
            ]
        )
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("duplicate", str(ctx.exception))

    def test_previous_answers_shape_is_validated(self):
        state = v2_state()
        state["decisions"][0]["previous_answers"] = [{"reason": "no answer key"}]
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state()
        state["decisions"][0]["previous_answers"] = {"answer": "not a list"}
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state()
        state["decisions"][0]["previous_answers"] = [{"answer": "old", "reason": "  "}]
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

    def test_previous_next_steps_shape_is_validated(self):
        for value in ("none", 5, [{"reason": "no step"}], [{"step": "  "}], [{"step": "x", "reason": "  "}]):
            state = v2_state()
            state["previous_next_steps"] = value
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(state)

        state = v2_state()
        state["previous_next_steps"] = [{"step": "Ship the plan", "reason": "changed"}]
        normalized = decision_state.validate_state(state)
        self.assertEqual(normalized["previous_next_steps"][0]["step"], "Ship the plan")

    def test_stale_decision_must_not_carry_an_active_answer(self):
        state = v2_state()
        state["decisions"][0]["status"] = "stale"
        state["decisions"][0]["answer"] = "still here"
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("stale", str(ctx.exception))

    def test_deferred_decision_must_not_be_blocking(self):
        state = v2_state()
        state["decisions"][0]["status"] = "deferred"
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("deferred", str(ctx.exception))

        state["decisions"][0]["blocking"] = False
        normalized = decision_state.validate_state(state)
        self.assertEqual(normalized["decisions"][0]["status"], "deferred")

    def test_unknown_decision_status_is_rejected(self):
        state = v2_state()
        state["decisions"][0]["status"] = "skipped"
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

    def test_malformed_collections_are_rejected(self):
        state = v2_state(facts={})
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state(conflicts="none")
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state(decisions=[])
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

        state = v2_state(out_of_scope={})
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)

    def test_duplicate_decision_ids_are_rejected(self):
        state = v2_state(decisions=[decision("d1"), decision("d1")])
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("duplicate", str(ctx.exception))

    def test_invalid_decision_id_is_rejected(self):
        state = v2_state(decisions=[decision("bad id!")])
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.validate_state(state)


class DependencyGraphTests(unittest.TestCase):
    def test_unknown_dependency_is_rejected(self):
        state = v2_state(decisions=[decision("d1", depends_on=["ghost"])])
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("unknown decision", str(ctx.exception))

    def test_self_dependency_is_rejected(self):
        state = v2_state(decisions=[decision("d1", depends_on=["d1"])])
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("cannot depend on itself", str(ctx.exception))

    def test_duplicate_dependency_is_rejected(self):
        state = v2_state(
            decisions=[
                decision("d1", status="resolved"),
                decision("d2", depends_on=["d1", "d1"]),
            ]
        )
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("duplicates", str(ctx.exception))

    def test_dependency_cycle_is_rejected(self):
        state = v2_state(
            decisions=[
                decision("d1", status="resolved", depends_on=["d3"]),
                decision("d2", status="resolved", depends_on=["d1"]),
                decision("d3", status="resolved", depends_on=["d2"]),
            ]
        )
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("dependency cycle", str(ctx.exception))

    def test_resolved_before_dependencies_is_rejected(self):
        state = v2_state(
            decisions=[
                decision("d1"),
                decision("d2", status="resolved", depends_on=["d1"]),
            ]
        )
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("resolved before dependencies", str(ctx.exception))

    def test_resolved_with_open_conflict_is_rejected(self):
        state = v2_state(
            conflicts=[{"id": "c1", "description": "Disagreement", "status": "open"}],
            decisions=[decision("d1", status="resolved", conflicts=["c1"])],
        )
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("conflicts remain open", str(ctx.exception))

    def test_unknown_conflict_reference_is_rejected(self):
        state = v2_state(decisions=[decision("d1", conflicts=["ghost"])])
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("unknown conflict", str(ctx.exception))

    def test_conflict_blocking_must_be_a_real_boolean(self):
        for value in (1, 0, "true", None):
            state = v2_state(
                conflicts=[{"id": "c1", "description": "d", "status": "open", "blocking": value}]
            )
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(state)

    def test_long_dependency_chain_does_not_recurse(self):
        depth = 1200
        decisions = [
            decision(
                f"d{index}",
                status="resolved",
                depends_on=[f"d{index - 1}"] if index else [],
            )
            for index in range(depth)
        ]
        normalized = decision_state.validate_state(v2_state(decisions=decisions))
        self.assertEqual(len(normalized["decisions"]), depth)

    def test_long_dependency_cycle_is_reported_without_a_recursion_error(self):
        depth = 1200
        decisions = [
            decision(
                f"d{index}",
                status="resolved",
                depends_on=[f"d{index - 1}"] if index else [],
            )
            for index in range(depth)
        ]
        decisions[0]["depends_on"] = [f"d{depth - 1}"]
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(v2_state(decisions=decisions))
        self.assertIn("dependency cycle", str(ctx.exception))

    def test_confirmed_status_requires_no_blocking_work(self):
        state = v2_state(status="confirmed")
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.validate_state(state)
        self.assertIn("requires all decisions", str(ctx.exception))

        state = chain_state(2, status="confirmed")
        self.assertEqual(decision_state.validate_state(state)["status"], "confirmed")


class ImmutabilityTests(unittest.TestCase):
    def test_validate_state_does_not_mutate_input(self):
        original = load_fixture("current_v2.json")
        snapshot = copy.deepcopy(original)
        decision_state.validate_state(original)
        self.assertEqual(original, snapshot)

    def test_validate_state_does_not_write_normalized_text_back(self):
        original = {
            "version": 1,
            "topic": "  Spaced topic  ",
            "status": "active",
            "facts": [
                {"id": "f1", "statement": "  Trailing  ", "source": " source ", "status": "verified"}
            ],
            "conflicts": [],
            "decisions": [
                {
                    "id": "d1",
                    "question": "  Q  ",
                    "status": "pending",
                    "depends_on": [],
                    "conflicts": [],
                    "recommendation": None,
                    "answer": None,
                }
            ],
            "out_of_scope": [],
        }
        snapshot = copy.deepcopy(original)
        decision_state.validate_state(original)
        self.assertEqual(original, snapshot)

    def test_upgrade_and_revise_do_not_mutate_input(self):
        legacy = legacy_state()
        legacy_snapshot = copy.deepcopy(legacy)
        decision_state.upgrade_state(legacy)
        self.assertEqual(legacy, legacy_snapshot)

        chain = chain_state(3)
        chain_snapshot = copy.deepcopy(chain)
        decision_state.revise_decision(chain, "d1", "changed")
        self.assertEqual(chain, chain_snapshot)

    def test_summarize_state_does_not_mutate(self):
        state = decision_state.validate_state(load_fixture("current_v2.json"))
        snapshot = copy.deepcopy(state)
        decision_state.summarize_state(state)
        self.assertEqual(state, snapshot)


class MigrationTests(unittest.TestCase):
    def test_upgrade_adds_honest_unknowns(self):
        upgraded = decision_state.upgrade_state(legacy_state())
        self.assertEqual(upgraded["version"], 2)
        self.assertEqual(upgraded["source_kind"], "unknown")
        self.assertEqual(upgraded["stage"], "unknown")
        self.assertEqual(upgraded["authority"], {"mode": "unknown", "scope": [], "evidence": ""})
        self.assertEqual(upgraded["desired_state"], [])
        self.assertEqual(upgraded["topic"], legacy_state()["topic"])
        self.assertEqual(len(upgraded["facts"]), 1)
        for item in upgraded["decisions"]:
            self.assertIs(item["blocking"], True)
            self.assertEqual(item["previous_answers"], [])

    def test_upgrade_preserves_resolved_answer_and_blocker(self):
        legacy = legacy_state()
        legacy["decisions"].append(
            {
                "id": "blocked_item",
                "question": "Which database?",
                "status": "blocked",
                "depends_on": ["agent_target"],
                "conflicts": [],
                "recommendation": None,
                "answer": None,
                "blocker": "The user has not chosen a database yet.",
            }
        )
        upgraded = decision_state.upgrade_state(legacy)
        by_id = {item["id"]: item for item in upgraded["decisions"]}
        self.assertEqual(by_id["agent_target"]["answer"], "Codex")
        self.assertEqual(by_id["blocked_item"]["blocker"], "The user has not chosen a database yet.")
        self.assertEqual(by_id["blocked_item"]["status"], "blocked")

    def test_upgrade_of_version_2_is_idempotent(self):
        state = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertEqual(decision_state.upgrade_state(state), state)

    def test_upgrade_keeps_legacy_file_valid_without_touching_it(self):
        legacy = legacy_state()
        decision_state.upgrade_state(legacy)
        # The legacy mapping still validates as version 1 afterwards.
        self.assertEqual(decision_state.validate_state(legacy)["version"], 1)


class RevisionTests(unittest.TestCase):
    def test_revise_invalidates_the_whole_transitive_chain(self):
        revised = decision_state.revise_decision(chain_state(3), "d1", "changed")
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertEqual(by_id["d1"]["status"], "resolved")
        self.assertEqual(by_id["d1"]["answer"], "changed")
        self.assertEqual(by_id["d1"]["previous_answers"][0]["answer"], "answer d1")
        for item_id in ("d2", "d3"):
            self.assertEqual(by_id[item_id]["status"], "stale")
            self.assertIsNone(by_id[item_id]["answer"])
            self.assertEqual(by_id[item_id]["previous_answers"][0]["answer"], f"answer {item_id}")
            self.assertIn("d1", by_id[item_id]["stale_reason"])

    def test_revise_preserves_facts_and_unaffected_decisions(self):
        state = chain_state(
            2,
            facts=[{"id": "f1", "statement": "A fact", "source": "a file", "status": "verified"}],
            desired_state=[{"id": "want", "statement": "A desired outcome"}],
        )
        state["decisions"].append(decision("unrelated", status="resolved"))
        revised = decision_state.revise_decision(state, "d1", "changed")
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertEqual(by_id["unrelated"]["status"], "resolved")
        self.assertEqual(by_id["unrelated"]["answer"], "answer unrelated")
        self.assertEqual(revised["facts"], state["facts"])
        self.assertEqual(revised["desired_state"], state["desired_state"])
        self.assertEqual(revised["out_of_scope"], state["out_of_scope"])

    def test_revise_downgrades_a_confirmed_session(self):
        state = decision_state.validate_state(chain_state(2, status="ready_for_confirmation"))
        self.assertEqual(state["status"], "ready_for_confirmation")
        revised = decision_state.revise_decision(state, "d1", "changed")
        self.assertEqual(revised["status"], "active")

    def test_revise_records_reason_and_source(self):
        revised = decision_state.revise_decision(
            chain_state(1),
            "d1",
            "changed",
            reason="The user replaced the earlier requirement.",
            source_kind="native",
        )
        target = revised["decisions"][0]
        self.assertEqual(target["resolution_reason"], "The user replaced the earlier requirement.")
        self.assertEqual(target["answer_source_kind"], "native")

    def test_revise_rejects_version_1_state(self):
        with self.assertRaises(decision_state.DecisionStateError) as ctx:
            decision_state.revise_decision(legacy_state(), "code_rules_mode", "changed")
        self.assertIn("version 2", str(ctx.exception))

    def test_revise_rejects_unknown_decision_and_empty_answer(self):
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.revise_decision(chain_state(1), "ghost", "changed")
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.revise_decision(chain_state(1), "d1", "   ")
        with self.assertRaises(decision_state.DecisionStateError):
            decision_state.revise_decision(chain_state(1), "d1", None)

    def test_revise_with_the_same_answer_is_idempotent(self):
        state = chain_state(3)
        same_answer = state["decisions"][0]["answer"]
        revised = decision_state.revise_decision(state, "d1", same_answer)
        self.assertEqual(revised, decision_state.validate_state(state))
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertEqual(by_id["d1"]["previous_answers"], [])
        for item_id in ("d2", "d3"):
            self.assertEqual(by_id[item_id]["status"], "resolved")
            self.assertEqual(by_id[item_id]["answer"], f"answer {item_id}")

    def test_repeated_answer_still_records_a_new_reason(self):
        state = chain_state(2)
        revised = decision_state.revise_decision(
            state, "d1", state["decisions"][0]["answer"], reason="Confirmed again by the user."
        )
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertEqual(by_id["d1"]["resolution_reason"], "Confirmed again by the user.")
        self.assertEqual(by_id["d1"]["previous_answers"], [])
        self.assertEqual(by_id["d2"]["status"], "resolved")

    def test_stale_reason_quotes_the_final_revision(self):
        revised = decision_state.revise_decision(chain_state(2), "d1", "changed")
        final_token = decision_state.idea_revision(revised)
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertIn(final_token, by_id["d2"]["stale_reason"])
        before_token = decision_state.idea_revision(chain_state(2))
        self.assertIn(before_token, by_id["d2"]["stale_reason"])

    def test_revised_state_still_validates(self):
        revised = decision_state.revise_decision(chain_state(3), "d1", "changed")
        self.assertEqual(decision_state.validate_state(revised), revised)


class RevisionTrackingTests(unittest.TestCase):
    def test_revision_token_is_deterministic(self):
        state = decision_state.validate_state(load_fixture("current_v2.json"))
        self.assertEqual(decision_state.idea_revision(state), decision_state.idea_revision(copy.deepcopy(state)))
        self.assertEqual(len(decision_state.idea_revision(state)), 16)

    def test_revision_changes_with_answers_and_facts(self):
        state = chain_state(2)
        token = decision_state.idea_revision(state)

        reanswered = decision_state.revise_decision(state, "d2", "different")
        self.assertNotEqual(decision_state.idea_revision(reanswered), token)

        with_new_fact = copy.deepcopy(state)
        with_new_fact["facts"].append(
            {"id": "f9", "statement": "New evidence", "source": "a file", "status": "verified"}
        )
        self.assertNotEqual(decision_state.idea_revision(with_new_fact), token)

    def test_revision_is_stable_across_supported_versions(self):
        legacy = decision_state.validate_state(legacy_state())
        upgraded = decision_state.upgrade_state(legacy)
        self.assertEqual(decision_state.idea_revision(legacy), decision_state.idea_revision(upgraded))

    def test_revision_covers_conflicts_and_the_project_stage(self):
        state = chain_state(2)
        token = decision_state.idea_revision(state)

        with_conflict = copy.deepcopy(state)
        with_conflict["conflicts"] = [
            {"id": "c1", "description": "Two readings of the brief", "status": "open"}
        ]
        self.assertNotEqual(
            decision_state.idea_revision(decision_state.validate_state(with_conflict)), token
        )

        resolved_conflict = copy.deepcopy(with_conflict)
        resolved_conflict["conflicts"][0]["status"] = "resolved"
        resolved_conflict["conflicts"][0]["resolution"] = "The runtime path wins."
        self.assertNotEqual(
            decision_state.idea_revision(decision_state.validate_state(resolved_conflict)),
            decision_state.idea_revision(decision_state.validate_state(with_conflict)),
        )

        promoted = copy.deepcopy(state)
        promoted["stage"] = "implemented"
        self.assertNotEqual(
            decision_state.idea_revision(decision_state.validate_state(promoted)), token
        )

    def test_open_conflict_invalidates_a_tool_result(self):
        state = chain_state(2)
        token = decision_state.idea_revision(state)
        revised = copy.deepcopy(state)
        revised["conflicts"] = [
            {"id": "c1", "description": "Important unresolved conflict", "status": "open"}
        ]
        normalized = decision_state.validate_state(revised)
        self.assertFalse(decision_state.is_result_current(normalized, token))
        self.assertTrue(decision_state.is_result_current(normalized, decision_state.idea_revision(normalized)))

    def test_stale_tool_result_is_detected_after_a_revision(self):
        state = chain_state(2)
        token = decision_state.idea_revision(state)
        self.assertTrue(decision_state.is_result_current(state, token))

        revised = decision_state.revise_decision(state, "d1", "changed")
        self.assertFalse(decision_state.is_result_current(revised, token))
        self.assertTrue(decision_state.is_result_current(revised, decision_state.idea_revision(revised)))

    def test_revision_requires_a_real_token(self):
        state = chain_state(1)
        for value in (None, "", "   ", 17, []):
            self.assertFalse(decision_state.is_result_current(state, value), msg=repr(value))


class ReadinessAndAuthorityTests(unittest.TestCase):
    def test_discussion_authorization_never_grants_code(self):
        state = decision_state.validate_state(load_fixture("current_v2.json"))
        self.assertEqual(state["authority"]["mode"], "discussion")
        self.assertTrue(decision_state.authorized_for(state, "discussion"))
        self.assertFalse(decision_state.authorized_for(state, "design"))
        self.assertFalse(decision_state.authorized_for(state, "implementation"))

    def test_implementation_authorization_covers_lower_modes(self):
        state = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertTrue(decision_state.authorized_for(state, "implementation"))
        self.assertTrue(decision_state.authorized_for(state, "design"))
        self.assertTrue(decision_state.authorized_for(state, "discussion"))
        self.assertFalse(decision_state.authorized_for(state, "unknown"))

    def test_scope_narrows_authorization(self):
        state = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertTrue(decision_state.authorized_for(state, "implementation", "documentation"))
        self.assertFalse(decision_state.authorized_for(state, "implementation", "payments"))

    def test_scope_check_fails_closed_without_a_recorded_scope(self):
        state = chain_state(
            1,
            authority={
                "mode": "implementation",
                "scope": [],
                "evidence": "Implement the agreed feature.",
            },
        )
        self.assertFalse(decision_state.authorized_for(state, "implementation", "unrelated task"))
        self.assertFalse(decision_state.authorized_for(state, "implementation"))
        self.assertTrue(decision_state.authorized_for(state, "discussion"))

    def test_recorded_scope_never_grants_an_unlisted_item(self):
        state = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertTrue(decision_state.authorized_for(state, "implementation", "documentation"))
        self.assertFalse(decision_state.authorized_for(state, "implementation", "unrelated task"))
        self.assertFalse(decision_state.authorized_for(state, "implementation", "payments"))

    def test_missing_authorization_grants_nothing(self):
        state = v2_state()
        del state["authority"]
        normalized = decision_state.validate_state(state)
        self.assertFalse(decision_state.authorized_for(normalized, "discussion"))
        readiness = decision_state.compute_readiness(normalized)
        self.assertEqual(readiness["mode"], "unknown")
        self.assertFalse(readiness["ready"])

    def test_discussion_readiness_allows_pending_questions(self):
        state = decision_state.validate_state(load_fixture("current_v2.json"))
        readiness = decision_state.compute_readiness(state)
        self.assertEqual(readiness["mode"], "discussion")
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["blocking_decisions"], ["first_scope"])
        self.assertEqual(readiness["deferred_decisions"], ["sync_later"])

    def test_implementation_readiness_needs_the_blocking_answers(self):
        state = chain_state(
            2,
            statuses=["resolved", "pending"],
            authority={
                "mode": "implementation",
                "scope": ["documentation"],
                "evidence": "The user asked to implement the agreed plan.",
            },
        )
        readiness = decision_state.compute_readiness(state)
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["blocking_decisions"], ["d2"])

        completed = decision_state.revise_decision(state, "d2", "answer d2")
        readiness = decision_state.compute_readiness(completed)
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["blocking_decisions"], [])

    def test_deferred_and_non_blocking_items_do_not_gate_readiness(self):
        state = v2_state(
            decisions=[
                decision("soft_question", blocking=False),
                decision("later", status="deferred", depends_on=["soft_question"], blocking=False),
            ]
        )
        normalized = decision_state.validate_state(state)
        summary = decision_state.summarize_state(normalized)
        self.assertEqual(summary["blocking_open"], [])
        self.assertTrue(summary["ready"])
        self.assertTrue(decision_state.compute_readiness(normalized)["ready"])

    def test_an_unassigned_open_conflict_gates_summary_and_readiness(self):
        state = v2_state(
            decisions=[decision("soft_question", blocking=False)],
            conflicts=[{"id": "c1", "description": "Important unresolved conflict", "status": "open"}],
        )
        normalized = decision_state.validate_state(state)
        summary = decision_state.summarize_state(normalized)
        readiness = decision_state.compute_readiness(normalized)
        self.assertFalse(summary["ready"])
        self.assertFalse(readiness["ready"])
        self.assertEqual(summary["open_blocking_conflicts"], ["c1"])
        self.assertEqual(readiness["blocking_conflicts"], ["c1"])
        self.assertEqual(decision_state.next_useful_step(normalized), "resolve open conflict 'c1'")

    def test_an_explicitly_non_blocking_conflict_does_not_gate(self):
        state = v2_state(
            decisions=[decision("soft_question", blocking=False)],
            conflicts=[
                {"id": "c1", "description": "Cosmetic wording", "status": "open", "blocking": False}
            ],
        )
        normalized = decision_state.validate_state(state)
        summary = decision_state.summarize_state(normalized)
        self.assertEqual(summary["open_conflicts"], 1)
        self.assertEqual(summary["open_blocking_conflicts"], [])
        self.assertTrue(summary["ready"])
        self.assertTrue(decision_state.compute_readiness(normalized)["ready"])

    def test_a_substantive_stage_needs_a_bounded_scope(self):
        state = chain_state(
            1,
            authority={"mode": "implementation", "scope": [], "evidence": "Build it."},
        )
        readiness = decision_state.compute_readiness(state)
        self.assertEqual(readiness["mode"], "implementation")
        self.assertFalse(readiness["authorized"])
        self.assertFalse(readiness["ready"])

        bounded = decision_state.validate_state(
            chain_state(
                1,
                authority={
                    "mode": "implementation",
                    "scope": ["documentation"],
                    "evidence": "Build the documentation plan.",
                },
            )
        )
        self.assertTrue(decision_state.compute_readiness(bounded)["ready"])

    def test_readiness_reports_the_next_authorized_stage_only(self):
        state = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        readiness = decision_state.compute_readiness(state)
        self.assertEqual(readiness["mode"], "implementation")
        self.assertEqual(readiness["project_stage"], "planned")
        self.assertEqual(readiness["stage"], "implementation")
        self.assertTrue(readiness["authorized"])
        self.assertTrue(readiness["ready"])

    def test_readiness_is_separate_from_authorization(self):
        # Authorized to implement, but the only blocking decision is unanswered.
        state = chain_state(
            1,
            statuses=["pending"],
            authority={
                "mode": "implementation",
                "scope": ["documentation"],
                "evidence": "The user said to build it.",
            },
        )
        readiness = decision_state.compute_readiness(state)
        self.assertTrue(readiness["authorized"])
        self.assertFalse(readiness["ready"])

    def test_next_useful_step_prefers_blocking_work(self):
        legacy = decision_state.validate_state(legacy_state())
        self.assertEqual(decision_state.next_useful_step(legacy), "answer decision 'code_rules_mode'")

        chain = decision_state.revise_decision(chain_state(2), "d1", "changed")
        self.assertEqual(decision_state.next_useful_step(chain), "revisit stale decision 'd2'")

        done = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertEqual(
            decision_state.next_useful_step(done), "continue with the authorized implementation stage"
        )

    def test_next_useful_step_reports_open_conflicts_first(self):
        state = v2_state(
            conflicts=[{"id": "c1", "description": "Two readings", "status": "open"}],
            decisions=[decision("d1", conflicts=["c1"])],
        )
        normalized = decision_state.validate_state(state)
        self.assertEqual(decision_state.next_useful_step(normalized), "resolve open conflict 'c1'")

    def test_next_useful_step_honours_a_current_explicit_field(self):
        state = decision_state.validate_state(
            chain_state(1, next_step="Read the saved brief and continue from it.")
        )
        self.assertEqual(
            decision_state.next_useful_step(state), "Read the saved brief and continue from it."
        )

    def test_open_blocking_work_wins_over_a_stored_step(self):
        state = decision_state.validate_state(
            chain_state(2, statuses=["resolved", "pending"], next_step="Implement the desktop UI")
        )
        self.assertEqual(decision_state.next_useful_step(state), "answer decision 'd2'")

        blocked = decision_state.validate_state(
            v2_state(
                next_step="Implement the desktop UI",
                decisions=[decision("needs_key", status="blocked", blocker="No API key yet.")],
            )
        )
        self.assertEqual(
            decision_state.next_useful_step(blocked), "resolve blocked decision 'needs_key'"
        )

    def test_a_stale_saved_next_step_does_not_outweigh_blocking_work(self):
        state = v2_state(
            status="confirmed",
            next_step="Implement the desktop UI",
            authority={
                "mode": "implementation",
                "scope": ["documentation"],
                "evidence": "The user approved the plan.",
            },
            decisions=[
                decision("platform", status="resolved", answer="desktop"),
                decision("ui", status="resolved", depends_on=["platform"], answer="native"),
            ],
        )
        normalized = decision_state.validate_state(state)
        self.assertTrue(decision_state.summarize_state(normalized)["ready"])
        self.assertEqual(decision_state.next_useful_step(normalized), "Implement the desktop UI")

        revised = decision_state.revise_decision(normalized, "platform", "command line")
        by_id = {item["id"]: item for item in revised["decisions"]}
        self.assertEqual(by_id["ui"]["status"], "stale")
        self.assertEqual(by_id["ui"]["previous_answers"][0]["answer"], "native")
        self.assertEqual(revised["status"], "active")
        self.assertFalse(decision_state.summarize_state(revised)["ready"])
        self.assertIsNone(revised["next_step"])
        self.assertEqual(revised["previous_next_steps"][0]["step"], "Implement the desktop UI")
        self.assertIn("platform", revised["previous_next_steps"][0]["reason"])
        self.assertEqual(decision_state.next_useful_step(revised), "revisit stale decision 'ui'")

    def test_structured_next_step_pinned_to_a_stale_revision_is_ignored(self):
        state = decision_state.validate_state(chain_state(1))
        current_token = decision_state.idea_revision(state)

        pinned = copy.deepcopy(state)
        pinned["next_step"] = {"step": "Ship the agreed plan", "revision": current_token}
        self.assertEqual(decision_state.next_useful_step(decision_state.validate_state(pinned)), "Ship the agreed plan")

        stale = copy.deepcopy(pinned)
        stale["next_step"] = {"step": "Ship the agreed plan", "revision": "0000000000000000"}
        self.assertEqual(
            decision_state.next_useful_step(decision_state.validate_state(stale)),
            "continue with the authorized discussion stage",
        )

    def test_malformed_next_step_shapes_are_rejected(self):
        for value in ("   ", 5, [], True):
            state = v2_state()
            state["next_step"] = value
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(state)

        for value in ({"reason": "no step"}, {"step": "  "}, {"step": "x", "revision": 5}):
            state = v2_state()
            state["next_step"] = value
            with self.assertRaises(decision_state.DecisionStateError, msg=repr(value)):
                decision_state.validate_state(state)

    def test_unknown_authority_separates_ready_from_stage_readiness(self):
        state = chain_state(1, status="ready_for_confirmation")
        state.pop("authority")
        normalized = decision_state.validate_state(state)
        summary = decision_state.summarize_state(normalized)
        self.assertEqual(normalized["status"], "ready_for_confirmation")
        self.assertTrue(summary["ready"])
        self.assertEqual(summary["readiness"]["mode"], "unknown")
        self.assertFalse(summary["readiness"]["authorized"])
        self.assertFalse(summary["readiness"]["ready"])
        self.assertEqual(
            decision_state.next_useful_step(normalized),
            "record the authorization basis for the next stage",
        )


class ResumingTests(unittest.TestCase):
    def test_stage_separates_a_plan_from_delivered_work(self):
        planned = decision_state.validate_state(load_fixture("dependency_chain_v2.json"))
        self.assertEqual(planned["stage"], "planned")

        implemented = copy.deepcopy(planned)
        implemented["stage"] = "implemented"
        self.assertEqual(decision_state.validate_state(implemented)["stage"], "implemented")

    def test_legacy_state_has_an_unknown_stage(self):
        upgraded = decision_state.upgrade_state(legacy_state())
        self.assertEqual(upgraded["stage"], "unknown")
        self.assertEqual(upgraded["source_kind"], "unknown")

    def test_answered_source_kinds_are_recorded(self):
        for source_kind in ("conversation", "native", "questionnaire", "saved_document"):
            state = chain_state(1, source_kind=source_kind)
            self.assertEqual(decision_state.validate_state(state)["source_kind"], source_kind)


class CommandLineTests(unittest.TestCase):
    def _write(self, workdir, payload, name="decision-state.json"):
        path = workdir / name
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def test_validate_only_passes_for_both_versions(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            for payload in (legacy_state(), load_fixture("current_v2.json")):
                path = self._write(workdir, payload)
                result = run_cli("--input", str(path), "--validate-only", cwd=workdir)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS: decision state is valid", result.stdout)

    def test_malformed_state_exits_two_with_a_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            bad = self._write(workdir, {"version": 3, "topic": "t"})
            result = run_cli("--input", str(bad), "--validate-only", cwd=workdir)
            self.assertEqual(result.returncode, 2)
            self.assertIn("ERROR:", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_missing_and_invalid_json_exit_two(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            missing = run_cli("--input", str(workdir / "absent.json"), "--validate-only", cwd=workdir)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("ERROR:", missing.stderr)

            broken = workdir / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            result = run_cli("--input", str(broken), "--validate-only", cwd=workdir)
            self.assertEqual(result.returncode, 2)
            self.assertIn("malformed JSON", result.stderr)

    def test_malformed_field_types_exit_two_without_a_traceback(self):
        base = {
            "version": 2,
            "topic": "Topic",
            "status": "active",
            "facts": [],
            "conflicts": [],
            "out_of_scope": [],
        }
        cases = (
            {"authority": "yes", "decisions": [decision("d1")]},
            {"authority": {"mode": "implementation", "scope": [], "evidence": "x"}, "decisions": "many"},
            {"authority": {"mode": "implementation", "scope": [], "evidence": "x"}, "decisions": [decision("d1")], "desired_state": 5},
            {
                "authority": {"mode": "implementation", "scope": [], "evidence": "x"},
                "decisions": [
                    {"id": "d1", "question": "q", "status": "pending", "previous_answers": 5}
                ],
            },
            {
                "authority": {"mode": "implementation", "scope": [], "evidence": "x"},
                "decisions": [{"id": "d1", "question": "q", "status": "pending", "blocking": "true"}],
            },
            {
                "authority": {"mode": "implementation", "scope": [], "evidence": "x"},
                "decisions": [decision("d1")],
                "conflicts": [{"id": "c1", "description": "d", "status": "open", "blocking": 1}],
            },
        )
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            for index, case in enumerate(cases):
                payload = dict(base)
                payload.update(case)
                path = self._write(workdir, payload, f"case-{index}.json")
                result = run_cli("--input", str(path), "--validate-only", cwd=workdir)
                self.assertEqual(result.returncode, 2, f"case {index}: {result.stdout}{result.stderr}")
                self.assertIn("ERROR:", result.stderr, f"case {index}")
                self.assertNotIn("Traceback", result.stderr, f"case {index}")

    def test_a_directory_input_exits_two(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            result = run_cli("--input", str(workdir), "--validate-only", cwd=workdir)
            self.assertEqual(result.returncode, 2)
            self.assertIn("ERROR:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_json_summary_keeps_the_original_keys(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, legacy_state())
            result = run_cli("--input", str(path), "--json", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            for key in (
                "topic",
                "status",
                "total_decisions",
                "resolved",
                "pending",
                "blocked",
                "open_conflicts",
                "frontier",
                "ready",
            ):
                self.assertIn(key, summary)
            self.assertEqual(summary["frontier"], ["code_rules_mode"])
            self.assertEqual(len(summary["idea_revision"]), 16)

    def test_json_summary_exposes_nested_stage_readiness(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, load_fixture("current_v2.json"))
            result = run_cli("--input", str(path), "--json", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            readiness = json.loads(result.stdout)["readiness"]
            self.assertEqual(readiness["mode"], "discussion")
            self.assertTrue(readiness["authorized"])
            self.assertTrue(readiness["ready"])
            self.assertEqual(readiness["blocking_decisions"], ["first_scope"])
            self.assertEqual(readiness["deferred_decisions"], ["sync_later"])

    def test_readiness_flag_prints_stage_readiness(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, legacy_state())
            result = run_cli("--input", str(path), "--readiness", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            readiness = json.loads(result.stdout)
            self.assertEqual(readiness["mode"], "unknown")
            self.assertFalse(readiness["authorized"])
            self.assertFalse(readiness["ready"])

    def test_text_output_labels_informational_ready_and_stage_readiness(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, load_fixture("current_v2.json"))
            result = run_cli("--input", str(path), cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("informational", result.stdout)
            self.assertIn("Next stage readiness (authorized)", result.stdout)
            self.assertIn("Frontier: first_scope", result.stdout)

    def test_companion_flags_require_revise_decision(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, load_fixture("current_v2.json"))
            for flags in (("--answer", "x"), ("--reason", "x"), ("--source-kind", "native")):
                result = run_cli("--input", str(path), "--validate-only", *flags, cwd=workdir)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("--revise-decision", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(result.stdout, "")

            # The revision is rejected for a state that has no such decision too.
            unknown = run_cli(
                "--input", str(path), "--revise-decision", "ghost", "--answer", "x", cwd=workdir
            )
            self.assertEqual(unknown.returncode, 2)
            self.assertIn("ERROR:", unknown.stderr)

    def test_invalid_utf8_state_exits_two_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = workdir / "bad-utf8.json"
            path.write_bytes(b'{"version": 2, "topic": "\xff\xfe"}')
            result = run_cli("--input", str(path), "--validate-only", cwd=workdir)
            self.assertEqual(result.returncode, 2)
            self.assertIn("ERROR:", result.stderr)
            self.assertIn("UTF-8", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(sorted(os.listdir(workdir)), ["bad-utf8.json"])

    def test_load_state_reports_invalid_utf8_and_a_directory(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = workdir / "bad-utf8.json"
            path.write_bytes(b'{"version": 1, "topic": "\xff\xfe"}')
            with self.assertRaises(decision_state.DecisionStateError) as ctx:
                decision_state.load_state(path)
            self.assertIn("UTF-8", str(ctx.exception))

            with self.assertRaises(decision_state.DecisionStateError) as ctx:
                decision_state.load_state(workdir)
            self.assertIn("could not read", str(ctx.exception))

    def test_idea_revision_token_matches_the_module_helper(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            payload = load_fixture("current_v2.json")
            path = self._write(workdir, payload)
            result = run_cli("--input", str(path), "--idea-revision", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            token = result.stdout.strip()
            self.assertEqual(token, decision_state.idea_revision(decision_state.validate_state(payload)))

    def test_upgrade_and_revise_print_to_stdout_only(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, legacy_state())
            before = path.read_bytes()

            upgraded = run_cli("--input", str(path), "--upgrade-to-v2", cwd=workdir)
            self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
            self.assertEqual(json.loads(upgraded.stdout)["version"], 2)
            self.assertEqual(upgraded.stderr, "")

            revised = run_cli(
                "--input", str(path), "--revise-decision", "code_rules_mode", "--answer", "Use code rules",
                cwd=workdir,
            )
            self.assertEqual(revised.returncode, 0, revised.stderr)
            payload = json.loads(revised.stdout)
            self.assertEqual(payload["version"], 2)
            by_id = {item["id"]: item for item in payload["decisions"]}
            self.assertEqual(by_id["code_rules_mode"]["status"], "resolved")
            self.assertEqual(by_id["code_rules_mode"]["answer"], "Use code rules")
            self.assertEqual(path.read_bytes(), before)

    def test_revise_without_an_answer_exits_two(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, load_fixture("current_v2.json"))
            result = run_cli("--input", str(path), "--revise-decision", "first_scope", cwd=workdir)
            self.assertEqual(result.returncode, 2)
            self.assertIn("--answer", result.stderr)

    def test_check_authorization_reports_without_granting(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            discussion_path = self._write(workdir, load_fixture("current_v2.json"), "discussion.json")
            allowed = run_cli(
                "--input", str(discussion_path), "--check-authorization", "discussion", cwd=workdir
            )
            self.assertEqual(allowed.returncode, 0)
            denied = run_cli(
                "--input", str(discussion_path), "--check-authorization", "implementation", cwd=workdir
            )
            self.assertEqual(denied.returncode, 3)
            self.assertIn("not authorized", denied.stdout)

            implementation_path = self._write(
                workdir, load_fixture("dependency_chain_v2.json"), "implementation.json"
            )
            granted = run_cli(
                "--input", str(implementation_path), "--check-authorization", "implementation", cwd=workdir
            )
            self.assertEqual(granted.returncode, 0)

    def test_next_step_command_prints_the_resume_hint(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, legacy_state())
            result = run_cli("--input", str(path), "--next-step", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "answer decision 'code_rules_mode'")

    def test_commands_never_write_next_to_the_state_file(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            path = self._write(workdir, legacy_state())
            before_listing = sorted(os.listdir(workdir))
            before_bytes = path.read_bytes()
            invocations = (
                ("--input", str(path), "--validate-only"),
                ("--input", str(path), "--json"),
                ("--input", str(path), "--idea-revision"),
                ("--input", str(path), "--upgrade-to-v2"),
                ("--input", str(path), "--next-step"),
                ("--input", str(path), "--check-authorization", "discussion"),
                ("--input", str(path), "--revise-decision", "code_rules_mode", "--answer", "Use code rules"),
            )
            for args in invocations:
                result = run_cli(*args, cwd=workdir)
                self.assertIn(result.returncode, (0, 3), result.stdout + result.stderr)
                self.assertEqual(sorted(os.listdir(workdir)), before_listing, args)
                self.assertEqual(path.read_bytes(), before_bytes, args)

    def test_help_works_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            result = run_cli("--help", cwd=workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--validate-only", result.stdout)

    def test_import_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_name:
            workdir = Path(temp_name)
            code = (
                "import importlib.util, sys\n"
                "sys.dont_write_bytecode = True\n"
                f"spec = importlib.util.spec_from_file_location('decision_state', {str(SCRIPT)!r})\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "print('imported')\n"
            )
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("imported", result.stdout)
            self.assertEqual(sorted(os.listdir(workdir)), [])


if __name__ == "__main__":
    unittest.main()
