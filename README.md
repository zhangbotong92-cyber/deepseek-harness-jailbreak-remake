# driftguard

自动管理的配置文件，怎么知道该不该覆盖？

这个问题不解决，会变成一个**没有报错的 bug**：用户升级了工具，改了配置，然后什么也没发生。

我是在一个真实场景里撞上的：某个工具自动往一个文件里写默认规则，用户手改过之后，新版本就再也进不去了——因为工具没法区分"这是用户改的"和"这是我上次写的"。于是它选择不覆盖，而用户以为升级成功了。

## 三种状态，两个哈希

driftguard 给每个受管文件记两个哈希：

| 字段 | 含义 |
|---|---|
| `seed` | 我们发布的那份内容 |
| `written` | 我们上次真正写进文件的哈希 |

拿当前文件比对，就得到状态：

```
current == written   → ours      我们写的，可以安全升级
current == seed      → pristine  用户没动过，可以安全升级
其它                  → modified   用户改过，不许覆盖
文件不存在            → missing    需要（重新）投放
```

只有 `ours` 和 `pristine` 允许被新版本覆盖。`modified` 会被跳过，并在 `status` 里标出来。

## 用法

```bash
# 登记一个文件（不存在就投放种子）
python -m driftguard.cli --state state.json register --file rules.md --seed seed.md

# 升级：只在安全时写入
python -m driftguard.cli --state state.json apply --file rules.md --seed seed-v2.md

# 看所有受管文件现在处于什么状态
python -m driftguard.cli --state state.json status

# 用户主动要求回退到种子
python -m driftguard.cli --state state.json revert --file rules.md --seed seed.md

# 接受用户当前的改动作为新基线（从此它算"我们的"）
python -m driftguard.cli --state state.json adopt --file rules.md
```

`status` 输出：

```
ok   /path/rules.md          seed=1a2b3c4d5e6f
EDIT /path/custom.md         seed=9f8e7d6c5b4a

有 1 个文件被手动改过，apply 会跳过它们；要接受现状用 adopt。
```

## 三条硬规矩

1. **`modified` 一律跳过，不静默覆盖。** 这是整个库存在的理由。
2. **状态文件损坏就退出，不重置。** 重置等于把所有文件变回"首次投放"，下一次 apply 就会覆盖用户改动。
3. **写入是原子的。** 先写临时文件再 `os.replace`；`fsync` 之后才替换，半写坏的状态比写错更麻烦。

## 测试

```bash
python -m unittest discover -s tests -v
```

11 个用例，覆盖：登记投放、安全升级、**手改后拒绝覆盖**、强制覆盖、幂等、回退、采纳现状、文件丢失、取消管理、状态损坏拒绝运行、原子写不留临时文件。

零第三方依赖，Python 3.8+。

## 适用与不适用

**适用**：插件安装器、提示词/规则注入、脚手架模板、dotfiles 管理——任何"我有一份默认内容，但用户可能改过"的场景。

**不适用**：需要真正三向合并（像 git 那样合并冲突）的场景。driftguard 只判断"能不能覆盖"，不合并内容；多数时候这就够了，做合并会把一件事变成两件事。

## 出处与致谢

这套"seed / written / customized"的状态思路，是从一个 MIT 协议的 DSH 插件里看到问题、然后自己实现的：上游把这三个字段写进 `override-state.json`，正是为了解决"手改之后升级不生效"。

本仓库是独立实现（Python、通用场景），**没有复制上游代码，也不包含任何第三方提示词内容**。详见 [CREDITS.md](CREDITS.md)。

## 许可

MIT，见 [LICENSE](LICENSE)。
