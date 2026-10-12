"""Tests for the weekly review loop (scripts/review.py).

The review loop proposes changes to the agent's own instructions, so its
evaluator must not be something the proposer can bend. These tests pin the
evaluator: what the collector extracts, and what the report gate rejects.

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
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review  # noqa: E402

WEEK = "2026-W40"          # Mon 2026-09-28 .. Sun 2026-10-04
IN_WEEK = "2026-09-30T10:00:00.000Z"
OUT_WEEK = "2026-10-06T10:00:00.000Z"


def _user(text, ts=IN_WEEK, **extra):
    return {"type": "user", "timestamp": ts, "cwd": "/work/alpha",
            "sessionId": "s1", "message": {"role": "user", "content": text},
            **extra}


def _asst_text(text, ts=IN_WEEK):
    return {"type": "assistant", "timestamp": ts, "cwd": "/work/alpha",
            "message": {"content": [{"type": "text", "text": text}]}}


def _asst_tool(tool_id, name, ts=IN_WEEK):
    return {"type": "assistant", "timestamp": ts, "cwd": "/work/alpha",
            "message": {"content": [{"type": "tool_use", "id": tool_id,
                                     "name": name, "input": {}}]}}


def _tool_result(tool_id, content, is_error=True, ts=IN_WEEK, **extra):
    return {"type": "user", "timestamp": ts, "cwd": "/work/alpha",
            "message": {"content": [{"type": "tool_result",
                                     "tool_use_id": tool_id,
                                     "content": content,
                                     "is_error": is_error}]}, **extra}


class ReviewTestCase(unittest.TestCase):
    def setUp(self) -> None:
        importlib.reload(review)
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.src = root / "src"
        self.src.mkdir()
        review.REVIEW = root / "review"
        review.SESSIONS = review.REVIEW / "sessions"
        review.REPORTS = review.REVIEW / "reports"
        review.RULES = review.REVIEW / "rules.md"
        review.REJECTED = review.REVIEW / "rejected.md"
        review.REVIEW.mkdir()
        self._streams = contextlib.ExitStack()
        self.stdout = self._streams.enter_context(
            contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self._streams.enter_context(
            contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self) -> None:
        self._streams.close()
        self._tmp.cleanup()

    # helpers ---------------------------------------------------------------
    def write_session(self, records, project="proj-a", name="s1.jsonl"):
        d = self.src / project
        d.mkdir(exist_ok=True)
        with open(d / name, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def collect(self) -> list[dict]:
        rc = review.main(["collect", "--week", WEEK,
                          "--source", str(self.src)])
        self.assertEqual(rc, 0, self.stderr.getvalue())
        digest = review.SESSIONS / WEEK / "digest.jsonl"
        return [json.loads(l) for l in digest.read_text("utf-8").splitlines()]

    def write_rules(self, text):
        review.RULES.write_text(text, encoding="utf-8")

    def write_report(self, text):
        review.REPORTS.mkdir(parents=True, exist_ok=True)
        (review.REPORTS / f"{WEEK}.md").write_text(text, encoding="utf-8")

    def check(self) -> int:
        return review.main(["check"])


# -------------------------------------------------------------------- collect
class TestCollect(ReviewTestCase):
    def test_extracts_correction_with_preceding_assistant_context(self):
        self.write_session([
            _asst_text("I refactored the whole module."),
            _user("нет, не так — я просил только переименовать"),
        ])
        sig = [s for s in self.collect() if s["kind"] == "user-msg"]
        self.assertEqual(len(sig), 1)
        self.assertTrue(sig[0]["correction_hint"])
        self.assertIn("refactored", sig[0]["prev_assistant"])
        self.assertEqual(sig[0]["project"], "alpha")

    def test_neutral_message_is_not_a_correction(self):
        self.write_session([_user("add a test for the parser")])
        sig = self.collect()
        self.assertFalse(sig[0]["correction_hint"])

    def test_noise_is_filtered(self):
        self.write_session([
            _user("<command-name>/clock-in</command-name>"),
            _user("Base directory for this skill: /x/y"),
            _user("Continue from where you left off."),
            _user("real request", isMeta=True),
        ])
        self.assertEqual(self.collect(), [])

    def test_interrupt_and_denial_are_signals(self):
        self.write_session([
            _user("[Request interrupted by user for tool use]"),
            _asst_tool("t1", "Bash"),
            _tool_result("t1", "user rejected", toolDenialKind="reject"),
        ])
        kinds = sorted(s["kind"] for s in self.collect())
        self.assertEqual(kinds, ["interrupt", "tool-denied"])

    def test_tool_error_carries_tool_name(self):
        self.write_session([
            _asst_tool("t1", "Edit"),
            _tool_result("t1", "old_string not found"),
            _asst_tool("t2", "Read"),
            _tool_result("t2", "ok", is_error=False),
        ])
        sig = self.collect()
        self.assertEqual([(s["kind"], s["tool"]) for s in sig],
                         [("tool-error", "Edit")])

    def test_repeat_request_is_flagged(self):
        self.write_session([
            _user("покажи вывод тестов"),
            _asst_text("done"),
            _user("Покажи вывод тестов!"),
        ])
        sig = self.collect()
        self.assertIsNone(sig[0]["repeat_of"])
        self.assertEqual(sig[1]["repeat_of"], sig[0]["ref"])

    # Shapes below come from real misses of the first heuristic (paraphrased).
    def test_frustration_without_no_is_a_correction(self):
        self.write_session([
            _user("слушай, то есть ты мне пересобираешь одно и то же 10 раз?"),
            _user("может быть ты сначала зайдешь в нужную папку?"),
        ])
        self.assertTrue(all(s["correction_hint"] for s in self.collect()))

    def test_long_paste_is_not_a_correction(self):
        log = "смотри логи:\n" + "epoch 1 val 9.3 ok\n" * 40 + "revert undo"
        self.write_session([_user(log)])
        self.assertFalse(self.collect()[0]["correction_hint"])

    def test_extended_reask_is_a_repeat(self):
        self.write_session([
            _user("то есть мне сейчас не надо перезапускать сборку, да?"),
            _user("[Request interrupted by user]"),
            _user("то есть мне сейчас не надо перезапускать сборку, да? и "
                  "кэш там есть?"),
        ])
        msgs = [s for s in self.collect() if s["kind"] == "user-msg"]
        self.assertEqual(msgs[1]["repeat_of"], msgs[0]["ref"])

    def test_try_again_is_a_retry(self):
        self.write_session([_user("Try again")])
        self.assertTrue(self.collect()[0]["retry_hint"])

    def test_out_of_week_records_are_excluded(self):
        self.write_session([_user("old", ts=OUT_WEEK), _user("in week")])
        self.assertEqual([s["text"] for s in self.collect()], ["in week"])

    def test_ref_points_at_the_raw_copy_line(self):
        self.write_session([_asst_text("x"), _user("нет, не то")])
        s = self.collect()[0]
        fname, line = s["ref"].rsplit(":", 1)
        raw = review.SESSIONS / WEEK / "raw" / fname
        rec = json.loads(raw.read_text("utf-8").splitlines()[int(line) - 1])
        self.assertEqual(rec["message"]["content"], "нет, не то")

    def test_session_with_nothing_in_window_is_not_copied(self):
        self.write_session([_user("old", ts=OUT_WEEK)])
        self.collect()
        self.assertEqual(list((review.SESSIONS / WEEK / "raw").iterdir()), [])


# ---------------------------------------------------------------------- rules
GOOD_RULES = """# Rules

### R-001
- rule: paste the test command output before saying tests pass
- scope: when I ask to fix or verify something
- hypothesis: removes my "show me the output" follow-ups
- predicts_re: (покажи|show).{0,20}(вывод|output)
- trigger_re: (почини|fix|verify)
- at_risk: replies get long on trivial edits
- target: CLAUDE.md
- evidence: 2026-W40 proj-a__s1.jsonl:2
- added: 2026-10-05
- last_hit: never
- status: active
"""


class TestRules(ReviewTestCase):
    def test_good_rules_pass(self):
        self.write_rules(GOOD_RULES)
        self.assertEqual(self.check(), 0, self.stdout.getvalue())

    def test_missing_hypothesis_rejected(self):
        self.write_rules(GOOD_RULES.replace(
            "- hypothesis: removes my \"show me the output\" follow-ups\n", ""))
        self.assertEqual(self.check(), 1)
        self.assertIn("hypothesis", self.stdout.getvalue())

    def test_bad_status_rejected(self):
        self.write_rules(GOOD_RULES.replace("status: active", "status: maybe"))
        self.assertEqual(self.check(), 1)

    def test_bad_regex_rejected(self):
        self.write_rules(GOOD_RULES.replace(
            "predicts_re: (покажи", "predicts_re: ((покажи"))
        self.assertEqual(self.check(), 1)

    def test_duplicate_id_rejected(self):
        self.write_rules(GOOD_RULES + GOOD_RULES.split("# Rules")[1])
        self.assertEqual(self.check(), 1)


# --------------------------------------------------------------------- audit
class TestAudit(ReviewTestCase):
    def test_audit_counts_predicted_corrections_and_triggers(self):
        self.write_rules(GOOD_RULES)
        self.write_session([
            _user("fix the parser"),
            _asst_text("fixed"),
            _user("покажи вывод тестов"),
        ])
        self.collect()
        rc = review.main(["audit", "--week", WEEK, "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(self.stdout.getvalue().strip().splitlines()[-1])
        self.assertEqual(out["R-001"]["predicted_hits"], 1)
        self.assertEqual(out["R-001"]["trigger_hits"], 1)


# -------------------------------------------------------------------- report
def _item(n, kind="new", surface="check", rule="always run the linter",
          ref="proj-a__s1.jsonl:2", extra=""):
    return f"""
## P{n}: item {n}
- kind: {kind}
- rule: {rule} {n}
- scope: when I ask for a refactor
- hypothesis: removes my "you broke lint" corrections
- predicts_re: lint
- at_risk: slower small edits
- surface: {surface}
- mechanism: agent edits without running lint because no step says to
- decision: pending
- evidence: {ref}
{extra}
```diff
+ rule text
```
"""


class TestReportGate(ReviewTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_session([_asst_text("x"), _user("нет, lint сломан")])
        self.collect()
        self.stdout.truncate(0)

    def header(self):
        meta = json.loads(
            (review.SESSIONS / WEEK / "meta.json").read_text("utf-8"))
        return f"# Review {WEEK}\ncollector_sha: {meta['collector_sha']}\n"

    def test_valid_report_passes(self):
        self.write_report(self.header() + _item(1) + _item(2, surface="prose"))
        self.assertEqual(self.check(), 0, self.stdout.getvalue())

    def test_more_than_five_items_rejected(self):
        self.write_report(self.header() +
                          "".join(_item(i) for i in range(1, 7)))
        self.assertEqual(self.check(), 1)
        self.assertIn("5", self.stdout.getvalue())

    def test_missing_mechanism_rejected(self):
        # A cluster without a causal mechanism is a symptom, not a proposal.
        self.write_report(self.header() + _item(1).replace(
            "- mechanism: agent edits without running lint because no step "
            "says to\n", ""))
        self.assertEqual(self.check(), 1)
        self.assertIn("mechanism", self.stdout.getvalue())

    def test_missing_predicts_rejected(self):
        self.write_report(self.header() +
                          _item(1).replace("- predicts_re: lint\n", ""))
        self.assertEqual(self.check(), 1)

    def test_evidence_ref_must_exist_in_digest(self):
        self.write_report(self.header() + _item(1, ref="proj-a__s1.jsonl:99"))
        self.assertEqual(self.check(), 1)
        self.assertIn("evidence", self.stdout.getvalue())

    def test_previously_rejected_rule_rejected(self):
        review.REJECTED.write_text(
            "# Rejected\n\n### X-001\n- rule: Always run the linter 1\n"
            "- reason: too broad\n- date: 2026-10-01\n", encoding="utf-8")
        self.write_report(self.header() + _item(1))
        self.assertEqual(self.check(), 1)
        self.assertIn("rejected", self.stdout.getvalue())

    def test_collector_changed_after_collect_rejected(self):
        self.write_report(
            f"# Review {WEEK}\ncollector_sha: deadbeef\n" + _item(1))
        self.assertEqual(self.check(), 1)
        self.assertIn("collector", self.stdout.getvalue())

    def test_questioned_item_must_reference_existing_rule(self):
        self.write_rules(GOOD_RULES)
        self.write_report(self.header() + _item(
            1, kind="questioned", extra="- rule_id: R-404"))
        self.assertEqual(self.check(), 1)

    def test_all_prose_is_a_warning_not_a_failure(self):
        self.write_report(self.header() + "".join(
            _item(i, surface="prose") for i in range(1, 4)))
        self.assertEqual(self.check(), 0)
        self.assertIn("WARN", self.stdout.getvalue())

    def test_report_without_digest_is_skipped_not_failed(self):
        # sessions/ is gitignored: a fresh clone has reports but no digests.
        import shutil
        shutil.rmtree(review.SESSIONS)
        self.write_report(f"# Review {WEEK}\ncollector_sha: x\n" + _item(1))
        self.assertEqual(self.check(), 0)
        self.assertIn("SKIP", self.stdout.getvalue())


# --------------------------------------------------------- hooks: snapshot
class TestSnapshotAndStatus(ReviewTestCase):
    def setUp(self) -> None:
        super().setUp()
        review.LIVE = review.SESSIONS / "_live"

    def snapshot(self, payload: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()), \
                unittest.mock.patch("sys.stdin", io.StringIO(payload)):
            return review.main(["snapshot"])

    def test_snapshot_copies_transcript_in_projects_layout(self):
        self.write_session([_user("hello")])
        path = self.src / "proj-a" / "s1.jsonl"
        rc = self.snapshot(json.dumps({"transcript_path": str(path)}))
        self.assertEqual(rc, 0)
        self.assertTrue((review.LIVE / "proj-a" / "s1.jsonl").exists())

    def test_snapshot_never_fails_the_session(self):
        self.assertEqual(self.snapshot("not json"), 0)
        self.assertEqual(self.snapshot(json.dumps(
            {"transcript_path": "/nope/x.jsonl"})), 0)

    def test_collect_merges_live_copy_when_source_was_cleaned(self):
        # Claude Code deleted the original; the SessionEnd snapshot survives.
        live_src = review.LIVE
        (live_src / "proj-b").mkdir(parents=True)
        (live_src / "proj-b" / "s9.jsonl").write_text(
            json.dumps(_user("из снапшота")) + "\n", encoding="utf-8")
        self.write_session([_user("из источника")])
        rc = review.main(["collect", "--week", WEEK, "--source", str(self.src),
                          "--source", str(live_src)])
        self.assertEqual(rc, 0)
        digest = (review.SESSIONS / WEEK / "digest.jsonl").read_text("utf-8")
        self.assertIn("из снапшота", digest)
        self.assertIn("из источника", digest)

    def test_collect_prefers_the_longer_copy_of_one_session(self):
        self.write_session([_user("первое")])
        (review.LIVE / "proj-a").mkdir(parents=True)
        (review.LIVE / "proj-a" / "s1.jsonl").write_text(
            json.dumps(_user("первое")) + "\n" +
            json.dumps(_user("второе")) + "\n", encoding="utf-8")
        review.main(["collect", "--week", WEEK, "--source", str(self.src),
                     "--source", str(review.LIVE)])
        texts = [json.loads(l)["text"] for l in
                 (review.SESSIONS / WEEK / "digest.jsonl")
                 .read_text("utf-8").splitlines()]
        self.assertEqual(texts, ["первое", "второе"])

    # status ----------------------------------------------------------------
    def status(self, today="2026-10-06") -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            review.main(["status", "--today", today])
        return buf.getvalue()

    def test_status_flags_overdue_review(self):
        self.assertIn("2026-W40", self.status())
        self.assertIn("/weekly-review", self.status())

    def test_status_flags_pending_decisions(self):
        self.write_report(f"# Review {WEEK}\ncollector_sha: x\n" + _item(1) +
                          _item(2).replace("decision: pending",
                                           "decision: accepted"))
        out = self.status()
        self.assertIn("1 item(s) await", out)
        self.assertNotIn("/weekly-review for", out)

    def test_status_is_silent_when_all_decided(self):
        self.write_report(f"# Review {WEEK}\ncollector_sha: x\n" +
                          _item(1).replace("decision: pending",
                                           "decision: rejected"))
        self.assertEqual(self.status(), "")


if __name__ == "__main__":
    unittest.main()
