"""driftguard —— 自动管理的配置文件，怎么知道该不该覆盖。

问题很具体：一个工具会自动写某份配置（提示词、规则、模板）。用户手改过之后，
下一次升级该不该覆盖它？

- 覆盖了：用户改的东西没了。
- 不覆盖：升级永远不生效，而且**没有任何报错**——这才是最难查的那种。

driftguard 用三个哈希把这件事说清楚：种子（seed）、上次写入（written）、当前（current）。
"""

from driftguard.core import Guard, StateError, atomic_write, sha256_text

__all__ = ["Guard", "StateError", "atomic_write", "sha256_text"]
__version__ = "0.1.0"
