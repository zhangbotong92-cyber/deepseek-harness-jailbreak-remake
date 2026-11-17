#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回归测试：把"该不该覆盖"的每一种情形都钉死。

跑法：
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from driftguard.core import Guard, StateError, sha256_text  # noqa: E402

SEED_V1 = "# rules v1\n- be brief\n"
SEED_V2 = "# rules v2\n- be brief\n- cite sources\n"


class DriftGuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="driftguard-test-")
        self.state = os.path.join(self.dir, "state.json")
        self.target = os.path.join(self.dir, "rules.md")

    def tearDown(self):
        for root, dirs, files in os.walk(self.dir, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(self.dir)

    def _write(self, text):
        with open(self.target, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def _read(self):
        with open(self.target, "r", encoding="utf-8", newline="") as fh:
            return fh.read()

    # ---------------------------------------------------------------- 基本
    def test_register_creates_file_and_state(self):
        g = Guard(self.state)
        self.assertEqual(g.register(self.target, SEED_V1), "ours")
        self.assertEqual(self._read(), SEED_V1)
        self.assertTrue(os.path.exists(self.state))
        with open(self.state, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["version"], 1)
        self.assertEqual(saved["files"][os.path.abspath(self.target)]["seed"], sha256_text(SEED_V1))

    def test_apply_upgrades_pristine_file(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        action, before = g.apply(self.target, SEED_V2)
        self.assertEqual((action, before), ("written", "ours"))
        self.assertEqual(self._read(), SEED_V2)
        self.assertEqual(g.status(self.target), "ours")

    # ---------------------------------------------------------------- 关键：不许覆盖手改
    def test_manual_edit_blocks_upgrade(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self._write("# 我自己的规则\n")
        self.assertEqual(g.status(self.target), "modified")
        action, before = g.apply(self.target, SEED_V2)
        self.assertEqual(action, "skipped")
        self.assertEqual(self._read(), "# 我自己的规则\n", "手改内容被覆盖了，这是最严重的错误")

    def test_force_overrides_edit(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self._write("mine\n")
        action, _ = g.apply(self.target, SEED_V2, force=True)
        self.assertEqual(action, "forced")
        self.assertEqual(self._read(), SEED_V2)

    def test_apply_is_idempotent(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        g.apply(self.target, SEED_V2)
        mtime = os.path.getmtime(self.target)
        action, before = g.apply(self.target, SEED_V2)
        self.assertEqual((action, before), ("written", "ours"))
        self.assertEqual(self._read(), SEED_V2)
        self.assertGreaterEqual(os.path.getmtime(self.target), mtime)

    # ---------------------------------------------------------------- 其余动作
    def test_revert_restores_seed_even_if_edited(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self._write("mine\n")
        self.assertEqual(g.revert(self.target, SEED_V1), "ours")
        self.assertEqual(self._read(), SEED_V1)

    def test_adopt_accepts_user_edits_as_baseline(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self._write("mine\n")
        self.assertEqual(g.adopt(self.target), "ours")
        action, before = g.apply(self.target, SEED_V2)
        self.assertEqual(action, "written", "adopt 之后应该可以正常升级")
        self.assertEqual(before, "ours")

    def test_missing_file_is_reported(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        os.unlink(self.target)
        self.assertEqual(g.status(self.target), "missing")
        g.register(self.target, SEED_V2)
        self.assertEqual(self._read(), SEED_V2)

    def test_forget_drops_tracking(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self.assertEqual(g.forgot(self.target), "unregistered")
        self.assertEqual(g.status(self.target), "unregistered")

    # ---------------------------------------------------------------- 漂移解释
    def test_drift_shows_what_user_changed(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        self._write("# rules v1\n- be brief\n- 加了中文一条\n")
        res = g.drift(self.target)
        self.assertEqual(res["state"], "modified")
        joined = "\n".join(res["lines"])
        self.assertIn("+", joined)
        self.assertIn("加了中文一条", joined)

    def test_drift_without_baseline_says_why(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1, write_if_missing=False)
        res = g.drift(self.target)
        self.assertEqual(res["lines"], [])
        self.assertTrue(res["reason"])

    # ---------------------------------------------------------------- 状态文件本身
    def test_corrupt_state_refuses_to_run(self):
        with open(self.state, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 json")
        with self.assertRaises(StateError):
            Guard(self.state)

    def test_atomic_write_leaves_no_temp_files(self):
        g = Guard(self.state)
        g.register(self.target, SEED_V1)
        leftovers = [f for f in os.listdir(self.dir) if f.startswith(".driftguard-")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

