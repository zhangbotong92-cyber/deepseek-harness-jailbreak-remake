# 状态机与边界情况

## 状态转移

```
未登记 ──register──▶ ours / pristine
ours ──apply(新种子)──▶ ours
pristine ──apply(新种子)──▶ ours
modified ──apply(新种子)──▶ modified（跳过，返回 skipped）
modified ──adopt──▶ ours
任一状态 ──revert──▶ ours（用户主动要求）
任一状态 ──文件被删──▶ missing
missing ──register(新种子)──▶ ours
```

## 三个容易搞错的边界

**1. 用户"改了但改回原样"。**
哈希相同，判成 `ours` 或 `pristine`，升级照常进行。这是对的：内容没变，覆盖不会丢东西。

**2. 我们写了，用户又改，我们又想升级。**
状态变 `modified`，跳过。正确。想让升级继续，只能 `adopt`（接受用户版本）或 `revert`（丢掉用户版本），二选一，必须有人做决定。

**3. 状态文件丢了，但受管文件还在。**
`status` 返回 `unregistered`。此时**不要直接 apply** —— 库里没有基线，任何写入都是盲写。正确做法是先 `register` 建立基线（文件已存在则只记哈希，不覆盖）。

## 为什么不做三向合并

合并需要三份内容：基线、我们的新版、用户当前版。driftguard 只存哈希，不存基线内容，所以做不了合并。

这是刻意的取舍：**大多数场景要的不是合并，而是"别动我改过的东西"**。真需要合并的项目，应该用 git，而不是让一个配置工具去实现半吊子的 merge。
