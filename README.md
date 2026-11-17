# driftguard

**dsh-purge 的 Python 重写版。**

dsh-purge 是一个 DSH（DeepSeek Harness）插件，做的是"破甲"：替换或注入提示词层，让不同模型用不同提示词。它用 Node 写，3.5MB，除了这件事还带桌面端解包、红队评测、进程处理。

这个仓库只拿其中一件事重做：**提示词层被替换之后，怎么判断该不该再次覆盖。** 零依赖 Python，有测试，能在 CI 里跑。

## 它解决的具体问题

插件会往一个文件里写默认提示词。用户手动改过之后，下一次升级该不该覆盖？

- 覆盖：用户改的东西没了。
- 不覆盖：升级永远不生效，**而且不报错**。用户以为升了，其实还是旧的那份。

dsh-purge 的源码注释里点了这个坑：状态文件必须记住"我们上次写下去的那一份"，否则会把用户手改误判成自己写的，从此永久拒绝更新。

driftguard 把这条判断抽出来，单独做成一个小库：

```
current == written   → ours      我们写的，可以升级
current == seed      → pristine  没动过，可以升级
其它                  → modified  用户改过，不覆盖，并解释差异
文件不存在            → missing   需要（重新）投放
```

## 现在有什么 / 没有什么

**有**：状态判断、安全覆盖、基线快照、差异解释、原子写、状态损坏拒绝运行、13 个用例。

**没有**：

- 不含任何默认提示词内容。提示词由你提供（`--seed` 指向你的文件），仓库里不附带。
- 不含红队评测、桌面端解包、进程处理、自动更新。那些是原插件的其余部分，不在这个重写的范围内。
- 不做三向合并。只回答"能不能覆盖"，以及"差在哪几行"。

## 用法

```bash
# 登记：文件不存在就投放种子
python -m driftguard.cli --state state.json register --file prompt.md --seed my-prompt.md

# 升级：只在安全时写入，被手改过就跳过
python -m driftguard.cli --state state.json apply --file prompt.md --seed my-prompt-v2.md

# 看状态
python -m driftguard.cli --state state.json status

# 被跳过时，看用户到底改了哪几行
python -m driftguard.cli --state state.json drift --file prompt.md

# 用户要求回退到种子
python -m driftguard.cli --state state.json revert --file prompt.md --seed my-prompt.md

# 接受用户当前版本作为新基线
python -m driftguard.cli --state state.json adopt --file prompt.md
```

`drift` 的输出（真跑的结果）：

```
状态：modified
--- baseline
+++ current
@@ -2 +2,2 @@
 - be brief
+- 我自己加的一条
```

`status` 的输出：

```
ok   /path/prompt.md         seed=1a2b3c4d5e6f
EDIT /path/custom.md         seed=9f8e7d6c5b4a

有 1 个文件被手动改过，apply 会跳过它们；要接受现状用 adopt。
```

## 三条规矩

1. `modified` 一律跳过，不静默覆盖。这是它存在的理由。
2. 状态文件损坏就退出。重置等于把所有文件变回"首次投放"，下一次 apply 就会覆盖用户改动。
3. 写入是原子的。先写临时文件，`fsync`，再 `os.replace`。

## 测试

```bash
python -m unittest discover -s tests -v
```

13 个用例。其中最关键那条：用户手改之后 `apply` 必须返回 `skipped`，且文件内容一个字都不能变。

## 和原插件的关系

- 原插件：`dsh-purge`，MIT，作者 YuJunZhiXue。本仓库沿用同一套状态思路（`hash` / `seedHash` / `customized`）。
- 本仓库是**重新实现**，不是 fork，也没有复制其代码；不包含它的默认提示词内容。
- 多做的部分：基线快照、`drift` 差异解释、`adopt`、`forget`、状态损坏时拒绝运行。

细节见 [CREDITS.md](CREDITS.md)。

## 许可

MIT，见 [LICENSE](LICENSE)。

---

**English**: A Python re-implementation of the override-state mechanism from `dsh-purge` (a DSH prompt-layer plugin). It decides whether an auto-managed prompt file may be overwritten after the user has edited it, explains the drift, and ships no prompt content of its own. Stdlib only, 13 tests.
