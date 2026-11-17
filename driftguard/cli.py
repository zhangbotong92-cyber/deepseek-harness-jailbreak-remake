#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""命令行：status / apply / revert / adopt / forget。

例子：
    python -m driftguard.cli --state state.json status
    python -m driftguard.cli --state state.json apply --file rules.md --seed seed.md
"""

import argparse
import json
import os
import sys

from driftguard.core import Guard, StateError


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def build_parser():
    ap = argparse.ArgumentParser(prog="driftguard", description="自动管理文件的漂移守卫")
    ap.add_argument("--state", default="driftguard-state.json", help="状态文件路径")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="看每个受管文件处于什么状态")
    p_status.add_argument("--json", action="store_true")

    for name, text in (("register", "登记并把种子投放下去（文件不存在时）"),
                       ("apply", "把种子写进去，除非用户改过"),
                       ("revert", "无条件回到种子内容"),
                       ("adopt", "把当前内容认作新基线")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--file", required=True, dest="target")
        if name != "adopt":
            p.add_argument("--seed", required=True, help="种子文件路径")
        if name == "apply":
            p.add_argument("--force", action="store_true", help="即使被改过也覆盖")

    p_drift = sub.add_parser("drift", help="对照基线，看用户改了哪几行")
    p_drift.add_argument("--file", required=True, dest="target")

    p_forget = sub.add_parser("forget", help="不再管理某个文件")
    p_forget.add_argument("--file", required=True, dest="target")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        guard = Guard(args.state)
    except StateError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return 2

    if args.cmd == "status":
        rows = guard.report()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        if not rows:
            print("（还没有受管文件）")
            return 0
        mark = {"ours": "ok  ", "pristine": "ok  ", "modified": "EDIT", "missing": "GONE"}
        for r in rows:
            print("%s %-40s seed=%s" % (mark.get(r["state"], "?   "), r["path"], r["seed"]))
        edited = [r for r in rows if r["state"] == "modified"]
        if edited:
            print("\n有 %d 个文件被手动改过，apply 会跳过它们；要接受现状用 adopt。" % len(edited))
        return 0

    if args.cmd == "drift":
        res = guard.drift(args.target)
        print("状态：%s%s" % (res["state"], ("（%s）" % res["reason"]) if res["reason"] else ""))
        if not res["lines"]:
            print("没有差异。")
            return 0
        for line in res["lines"]:
            print(line)
        if res.get("truncated"):
            print("...（差异太长，已截断）")
        return 0

    if args.cmd == "forget":
        print(guard.forgot(args.target))
        return 0

    if args.cmd == "adopt":
        print(guard.adopt(args.target))
        return 0

    seed = _read(args.seed)
    if args.cmd == "register":
        print(guard.register(args.target, seed))
        return 0
    if args.cmd == "revert":
        print(guard.revert(args.target, seed))
        return 0
    if args.cmd == "apply":
        action, state = guard.apply(args.target, seed, force=args.force)
        print("%s（写入前状态：%s）" % (action, state))
        return 0 if action != "skipped" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
