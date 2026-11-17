#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核心实现：只依赖标准库。

状态机（每个被管理的文件都有这两个哈希）：

    seed      = 我们发布的那份内容
    written   = 我们上次真正写进文件的那份内容

判断当前文件属于哪一种，靠比对 current 的哈希：

    current == written      -> "ours"      我们写的，可以安全升级
    current == seed         -> "pristine"  用户没动过，可以安全升级
    其它                     -> "modified"   用户改过，不许覆盖
    文件不存在               -> "missing"   需要（重新）投放
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


class StateError(Exception):
    pass


def sha256_text(text):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def atomic_write(path, text):
    """先写临时文件再 os.replace。半写坏的状态文件比写错更麻烦。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".driftguard-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Guard(object):
    """一份状态文件，管理若干个"种子 + 目标"对。"""

    def __init__(self, state_path):
        self.state_path = os.path.abspath(state_path)
        self.state = self._load()

    # ---------------------------------------------------------------- state
    def _load(self):
        if not os.path.exists(self.state_path):
            return {"version": 1, "files": {}}
        try:
            with open(self.state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            # 状态坏了不要静默重置：那会让所有文件变成"首次投放"，覆盖用户改动
            raise StateError("状态文件损坏，拒绝继续：%s" % exc)
        if data.get("version") != 1:
            raise StateError("未知状态版本：%r" % data.get("version"))
        data.setdefault("files", {})
        return data

    def _save(self):
        self.state["updatedAt"] = _now()
        atomic_write(self.state_path, json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")

    # ---------------------------------------------------------------- query
    @staticmethod
    def _read(path):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()

    def status(self, target):
        target = os.path.abspath(target)
        entry = self.state["files"].get(target)
        current = self._read(target)
        if entry is None:
            return "unregistered" if current is not None else "unregistered-missing"
        if current is None:
            return "missing"
        h = sha256_text(current)
        if h == entry.get("written"):
            return "ours"
        if h == entry.get("seed"):
            return "pristine"
        return "modified"

    # ---------------------------------------------------------------- write
    def register(self, target, seed_text, write_if_missing=True):
        """登记一个受管文件。文件不存在时按需投放种子。"""
        target = os.path.abspath(target)
        entry = self.state["files"].setdefault(target, {})
        entry["seed"] = sha256_text(seed_text)
        entry["seedUpdatedAt"] = _now()
        if write_if_missing and self._read(target) is None:
            atomic_write(target, seed_text)
            entry["written"] = sha256_text(seed_text)
            entry["writtenAt"] = _now()
        self._save()
        return self.status(target)

    def apply(self, target, seed_text, force=False):
        """把种子写进去——除非用户改过。

        返回 (动作, 状态)：动作是 written / skipped / forced。
        """
        target = os.path.abspath(target)
        state = self.status(target)
        if state == "modified" and not force:
            return "skipped", state
        atomic_write(target, seed_text)
        entry = self.state["files"].setdefault(target, {})
        entry["seed"] = sha256_text(seed_text)
        entry["written"] = sha256_text(seed_text)
        entry["writtenAt"] = _now()
        entry["seedUpdatedAt"] = entry.get("seedUpdatedAt") or _now()
        self._save()
        return ("forced" if force and state == "modified" else "written"), state

    def revert(self, target, seed_text):
        """回到种子内容，不看当前状态（用户主动要求回退）。"""
        target = os.path.abspath(target)
        atomic_write(target, seed_text)
        entry = self.state["files"].setdefault(target, {})
        entry["seed"] = sha256_text(seed_text)
        entry["written"] = sha256_text(seed_text)
        entry["writtenAt"] = _now()
        self._save()
        return self.status(target)

    def adopt(self, target):
        """把用户当前的改动认作新的基线，从此它算"我们的"。"""
        target = os.path.abspath(target)
        current = self._read(target)
        if current is None:
            raise StateError("文件不存在，无法 adopt：%s" % target)
        entry = self.state["files"].setdefault(target, {})
        entry["written"] = sha256_text(current)
        entry["adoptedAt"] = _now()
        self._save()
        return self.status(target)

    def forgot(self, target):
        target = os.path.abspath(target)
        self.state["files"].pop(target, None)
        self._save()
        return "unregistered"

    # ---------------------------------------------------------------- audit
    def report(self):
        rows = []
        for target, entry in sorted(self.state["files"].items()):
            rows.append({
                "path": target,
                "state": self.status(target),
                "seed": (entry.get("seed") or "")[:12],
                "written": (entry.get("written") or "")[:12],
                "seedUpdatedAt": entry.get("seedUpdatedAt"),
            })
        return rows
