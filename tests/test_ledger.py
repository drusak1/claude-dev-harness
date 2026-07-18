"""Tests for the anti-grind guards.

Each test names the discipline it protects (docs/DISCIPLINES.md). These are the
rules that prose failed to enforce, so a regression here is not cosmetic -- it
re-opens the exact failure mode the harness exists to prevent.

Pure stdlib: `python -m unittest discover -s tests`.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ledger  # noqa: E402


class LedgerTestCase(unittest.TestCase):
    """Redirects the ledger at a throwaway registry for each test."""

    def setUp(self) -> None:
        importlib.reload(ledger)
        self._tmp = tempfile.TemporaryDirectory()
        reg = Path(self._tmp.name)
        ledger.REGISTRY = reg
        ledger.APPROACHES = reg / "approaches.jsonl"
        ledger.QUEUE = reg / "queue.jsonl"

        # The CLI is chatty by design (agent-oriented what/WHY/FIX output).
        # Capture it so the suite stays readable; assertion failures still
        # report normally, since teardown restores the streams first.
        self._streams = contextlib.ExitStack()
        self.stdout = self._streams.enter_context(
            contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self._streams.enter_context(
            contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self) -> None:
        self._streams.close()
        self._tmp.cleanup()

    # helpers ---------------------------------------------------------------
    def add(self, klass="cache-layer", objective="cut p99 latency",
            hypothesis="memoize the resolver", source="failure-correlated",
            project="api") -> int:
        return ledger.main([
            "add", "--project", project, "--class", klass,
            "--objective", objective, "--hypothesis", hypothesis,
            "--source", source,
        ])

    def refute(self, rid: int, why="the resolver was never the hot path") -> int:
        return ledger.main([
            "set-status", str(rid), "refuted",
            "--evidence", json.dumps([{"cmd": "make bench", "result": "p99 unchanged",
                                       "gate_tier": "local-test"}]),
            "--why", why,
        ])

    def rows(self) -> list[dict]:
        return ledger.load_approaches()


class TestDeadSignature(LedgerTestCase):
    """Discipline 8: no silent re-try of a refuted signature."""

    def test_identical_signature_is_rejected_after_refute(self) -> None:
        self.assertEqual(self.add(), 0)
        self.refute(1)
        self.assertEqual(self.add(), 2, "a refuted signature was silently re-admitted")

    def test_different_hypothesis_same_class_is_allowed(self) -> None:
        self.add()
        self.refute(1)
        self.assertEqual(self.add(hypothesis="batch the N+1 queries"), 0)


class TestWipOne(LedgerTestCase):
    """Discipline 5: exactly one approach in flight."""

    def test_second_testing_is_rejected(self) -> None:
        self.add()
        self.add(hypothesis="batch the N+1 queries")
        self.assertEqual(ledger.main(["set-status", "1", "testing"]), 0)
        self.assertEqual(ledger.main(["set-status", "2", "testing"]), 2)

    def test_reopening_the_same_row_is_allowed(self) -> None:
        self.add()
        ledger.main(["set-status", "1", "testing"])
        self.assertEqual(ledger.main(["set-status", "1", "testing"]), 0)


class TestForcedScout(LedgerTestCase):
    """Discipline 6: N same-class refutes block the class and force a scout."""

    def test_n_refutes_block_the_class_and_queue_a_scout(self) -> None:
        for i, h in enumerate(["memoize resolver", "add redis", "warm the cache"], 1):
            self.add(hypothesis=h)
            self.refute(i)

        self.assertTrue(all(r["class_blocked"] for r in self.rows()),
                        "the class was not blocked at the N-refute threshold")
        queue = ledger.load_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["type"], "forced-scout")
        self.assertEqual(queue[0]["class_blocked"], "cache-layer")

    def test_below_threshold_does_not_block(self) -> None:
        for i, h in enumerate(["memoize resolver", "add redis"], 1):
            self.add(hypothesis=h)
            self.refute(i)
        self.assertEqual(ledger.load_queue(), [])

    def test_threshold_is_configurable(self) -> None:
        import os
        os.environ["CDH_REFUTE_N"] = "2"
        try:
            for i, h in enumerate(["memoize resolver", "add redis"], 1):
                self.add(hypothesis=h)
                self.refute(i)
            self.assertEqual(len(ledger.load_queue()), 1)
        finally:
            del os.environ["CDH_REFUTE_N"]


class TestRefuteEvidence(LedgerTestCase):
    """Discipline 9: an unmeasured refutation is not a refutation."""

    def test_refute_without_evidence_is_rejected(self) -> None:
        self.add()
        self.assertEqual(
            ledger.main(["set-status", "1", "refuted", "--why", "did not help"]), 2
        )

    def test_refute_without_gate_tier_is_rejected(self) -> None:
        self.add()
        rc = ledger.main([
            "set-status", "1", "refuted",
            "--evidence", json.dumps([{"cmd": "make bench", "result": "no change"}]),
        ])
        self.assertEqual(rc, 2, "evidence lacking a gate_tier was accepted")


class TestCeilingGate(LedgerTestCase):
    """Discipline 7: ceiling-claimed is gated and auto-reopens."""

    def test_ceiling_requires_sub_variants_and_control(self) -> None:
        self.add()
        self.assertEqual(ledger.main(["set-status", "1", "ceiling-claimed"]), 2)
        self.assertEqual(ledger.main([
            "set-status", "1", "ceiling-claimed",
            "--sub-variants", json.dumps(["lru", "ttl", "write-through"]),
        ]), 2, "a ceiling was accepted with no control")

    def test_gated_ceiling_queues_a_rechallenge(self) -> None:
        self.add()
        rc = ledger.main([
            "set-status", "1", "ceiling-claimed",
            "--sub-variants", json.dumps(["lru", "ttl", "write-through"]),
            "--control", json.dumps({"repro": "upstream driver caps at 5k rps"}),
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(ledger.load_queue()[0]["type"], "ceiling-rechallenge")


class TestAppendOnlyWhy(LedgerTestCase):
    """Discipline 3: a verdict is never silently rewritten."""

    def test_second_why_appends_rather_than_overwrites(self) -> None:
        self.add()
        ledger.main(["set-status", "1", "testing", "--why", "first read"])
        self.refute(1, why="second read, with the bench")
        why = self.rows()[0]["why"]
        self.assertIn("first read", why)
        self.assertIn("second read, with the bench", why)
        self.assertEqual(len(why.splitlines()), 2)


class TestCheck(LedgerTestCase):
    """Discipline 4: banned stop-reasons fail the gate."""

    def test_banned_stop_reason_fails_check(self) -> None:
        self.add()
        self.refute(1, why="wontfix")
        self.assertEqual(ledger.main(["check"]), 1)

    def test_mechanism_explanation_passes_check(self) -> None:
        self.add()
        self.refute(1, why="the resolver was 2% of p99; the hot path is TLS handshake")
        self.assertEqual(ledger.main(["check"]), 0)

    def test_banned_word_as_prose_in_a_live_row_is_not_flagged(self) -> None:
        self.add()
        ledger.main(["set-status", "1", "testing",
                     "--why", "exploring whether we hit a ceiling here"])
        self.assertEqual(ledger.main(["check"]), 0)

    def test_clean_ledger_passes(self) -> None:
        self.add()
        self.assertEqual(ledger.main(["check"]), 0)


if __name__ == "__main__":
    unittest.main()
