"""The installer edits the user's global Claude Code settings, so it must keep
every key and hook that is not its own, and be safe to run twice."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import install_review_hooks as inst  # noqa: E402

FOREIGN = {"type": "command", "command": "echo mine"}


class TestInstaller(unittest.TestCase):
    def base(self):
        return {"theme": "dark",
                "hooks": {"SessionStart": [{"hooks": [FOREIGN]}]}}

    def test_keeps_foreign_keys_and_hooks(self):
        s = inst.merge(self.base())
        self.assertEqual(s["theme"], "dark")
        cmds = [h["command"] for g in s["hooks"]["SessionStart"]
                for h in g["hooks"]]
        self.assertIn("echo mine", cmds)
        self.assertTrue(any("status" in c for c in cmds))
        self.assertIn("SessionEnd", s["hooks"])

    def test_idempotent(self):
        once = inst.merge(self.base())
        twice = inst.merge(json.loads(json.dumps(once)))
        self.assertEqual(once, twice)

    def test_remove_restores_original(self):
        s = inst.merge(inst.merge(self.base()), remove=True)
        self.assertEqual(s, self.base())

    def test_remove_on_clean_settings_drops_empty_hooks(self):
        self.assertEqual(inst.merge(inst.merge({"a": 1}), remove=True),
                         {"a": 1})


if __name__ == "__main__":
    unittest.main()
