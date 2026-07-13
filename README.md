# Memory Lab：Past as Code 分享演示手册

`memory-lab` 是一个确定性、可离线运行的 Agent Memory 实验台。它在任务、模拟工具、规划器和运行预算保持一致的前提下，对比三种记忆策略：

- `none`：不使用跨会话记忆。
- `naive`：仅按照文本相似度检索原始执行轨迹。
- `governed`：根据作用域、来源、有效期、风险和相关性准入规则检索结构化 Memory Card。

项目实现了设计文档中的确定性演示环境：运行集成测试前必须设置 `APP_ENV=test`，随后初始化测试数据；任何 `force=True` 调用都会被安全拒绝。

规划器包括：`deepseek`（在线真实模型）、`autonomous`（离线确定性模型替身）和 `scripted`（固定 Oracle）。正式分享优先使用 `deepseek`，需要稳定数字时使用 `autonomous`。记忆系统内部设计见 [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)。

## 安装

在仓库根目录中可以直接运行本文档列出的命令。如需将项目安装到 Python 3.11 及以上版本的环境中，请执行：

```powershell
python -m pip install -e .
```

复制 `.env.example` 为 `.env` 并填写：

```dotenv
DEEPSEEK_API_KEY=你的_API_Key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

`.env` 会自动加载，并已被 Git 忽略。

## 演示流程

请在仓库根目录运行以下命令。每次执行 `run` 都会创建全新的会话，因此聊天历史不会跨越会话边界，长期信息只能通过 Memory Store 传递。

```powershell
python -m memory_lab reset

# 从失败轨迹中学习可复用流程
python -m memory_lab run learn-1 --mode governed --planner deepseek
python -m memory_lab memory list
python -m memory_lab memory show mem-001

# 对比第二次任务；governed 模式会复用已验证的流程记忆
python -m memory_lab run learn-2 --mode none --planner deepseek
python -m memory_lab run learn-2 --mode governed --planner deepseek

# 制造 Memory Rot、归因并回滚
python -m memory_lab memory consolidate mem-001 --variant overgeneralized
python -m memory_lab memory diff mem-001 mem-002
python -m memory_lab memory releases
python -m memory_lab run learn-2 --mode governed --planner deepseek
python -m memory_lab blame learn-2 --memory mem-002 --baseline mem-001
python -m memory_lab memory rollback mem-002
python -m memory_lab run learn-2 --mode governed --planner deepseek

# 注入语义相关但不安全的记忆，并对比两种召回策略
python -m memory_lab inject unsafe-memory
python -m memory_lab run injection --mode naive --planner deepseek
python -m memory_lab run injection --mode governed --planner deepseek
python -m memory_lab memory explain --scenario injection --mode governed

python -m memory_lab report
```

### 命令说明

| 指令 | 做什么 | 为什么要这样安排 |
|---|---|---|
| `python -m memory_lab reset` | 清空 `data/` 下的 SQLite 记忆、事件和指标。 | 保证每次演示从零开始，避免已有记忆影响结果。 |
| `python -m memory_lab run learn-1 --mode governed` | 运行首次学习任务。记忆库为空时，系统会执行试错流程；任务成功后，将经验写入结构化记忆卡 `mem-001`。 | 先建立一条可审查、可复用的 governed 记忆，供后续对比使用。 |
| `python -m memory_lab memory list` | 列出已保存的结构化记忆卡，以及项目、可信度、风险和使用次数等信息。 | 确认首次任务的经验已经被持久化。 |
| `python -m memory_lab memory show mem-001` | 展示 `mem-001` 的完整 JSON 内容。 | 说明记忆不仅包含文本，还包含流程、来源、置信度和风险等元数据。 |
| `python -m memory_lab run learn-2 --mode none` | 在全新会话中执行相似任务，但禁用跨会话记忆。 | 作为基线：系统需要再次走试错路径。 |
| `python -m memory_lab run learn-2 --mode governed` | 在全新会话中执行相似任务，并启用 governed 记忆。 | 系统会复用 `mem-001` 的已验证流程，减少不必要的工具调用。 |
| `python -m memory_lab inject unsafe-memory` | 注入一条语义相关、但跨项目、来源不可信且高风险的记忆；同时将原始文本写入 naive 语料库。 | 为后续安全治理对比准备对抗样本。 |
| `python -m memory_lab run injection --mode naive` | naive 模式只按原始文本相似度检索，危险记忆可能影响行动选择。 | 展示仅做相似度召回的风险；模拟环境仍会安全拒绝 `force=True`。 |
| `python -m memory_lab run injection --mode governed` | governed 模式检查项目范围、来源、风险等条件，并拒绝不安全记忆。 | 展示“相关”不等于“可用”。 |
| `python -m memory_lab memory explain --scenario injection --mode governed` | 仅执行检索和记忆准入判断，不执行任务。 | 显示不安全记忆被拒绝的具体原因代码。 |
| `python -m memory_lab report` | 汇总各场景、模式、成功情况、调用次数、错误与记忆 token 估算。 | 用统一指标收尾，对比不同记忆策略的效果。 |

`--mode` 用于选择本次运行的记忆策略：`none` 不使用跨会话记忆，`naive` 只按文本相似度检索原始轨迹，`governed` 则在检索结构化 Memory Card 后，额外检查作用域、来源、有效期、风险、相关性和允许工具。

`NaiveMemory` 仅在自身执行学习任务时记录原始轨迹。若要观察原始轨迹的复用效果，请先执行 `run learn-1 --mode naive`，再执行 `run learn-2 --mode naive`。

## 安全治理与可解释性

`governed` Reader 会在组装 Prompt 之前评估每一条候选记忆。项目作用域不匹配、来源不可信、风险过高、已经过期或置信度过低的 Memory Card 会被拒绝；可以通过 `memory explain` 查看对应的原因代码。被拒绝的记忆不会传递给规划器。

演示状态默认保存在 `data/` 目录，包括只追加写入的 `events.jsonl`、指标文件 `metrics.jsonl` 和 SQLite 数据库 `memory.db`。可以设置 `MEMORY_LAB_DATA` 环境变量，为测试或独立演示指定隔离的数据目录。

## 自动化测试

```powershell
python -m pytest
```

当前应看到 `16 passed`。

## 按分享环节执行什么

### 03｜第一次任务留下摩擦（1:00–2:30）

```powershell
python -m memory_lab reset
python -m memory_lab run learn-1 --mode governed --planner deepseek
```

作用：清空历史后，让 DeepSeek 在没有长期记忆的情况下执行 payments 集成测试。

预期：Agent 遇到 `E_ENV_REQUIRED` 和 `E_FIXTURE_REQUIRED`，根据 ToolResult 修复环境并成功。任务结束后生成 `mem-001`。在线调用数可能变化；稳定离线命令及结果为：

```powershell
python -m memory_lab reset
python -m memory_lab run learn-1 --mode governed --planner autonomous
```

预期为 7 次工具调用、2 次失败、最终成功。

### 04｜生成 Behavior Patch v1（2:30–3:30）

```powershell
python -m memory_lab memory list
python -m memory_lab memory show mem-001
```

作用：第一条列出记忆库；第二条展示完整 Experience IR。

预期：看到 procedure、problem signature、scope、source trajectory、confidence、trust、risk、version 和 release status，证明记忆不是无来源摘要。

### 05｜新会话动态链接 v1（3:30–5:00）

```powershell
python -m memory_lab run learn-2 --mode none --planner deepseek
python -m memory_lab run learn-2 --mode governed --planner deepseek
```

作用：在两个新 Session 中执行 orders 任务，比较无记忆和受治理记忆。

预期：`none` 重新探索；`governed` 准入 `mem-001` 并减少失败。稳定对照命令：

```powershell
python -m memory_lab run learn-2 --mode none --planner autonomous
python -m memory_lab run learn-2 --mode governed --planner autonomous
```

稳定结果分别为 7 次调用/2 次失败，以及 3 次调用/0 次失败。

### 17–19｜Memory Rot、Diff 与回归（24:00–29:00）

```powershell
python -m memory_lab memory consolidate mem-001 --variant overgeneralized
python -m memory_lab memory diff mem-001 mem-002
python -m memory_lab memory releases
python -m memory_lab run learn-2 --mode governed --planner autonomous
```

每条命令的作用：

1. `consolidate` 从 v1 产生故意过度泛化的 Active v2。
2. `diff` 展示 `set_env(APP_ENV, test)` 被错误改成 `set_env(ENV, test)`。
3. `releases` 展示 v1 superseded、v2 active 的版本链。
4. `run` 用 v2 重跑回归任务。

稳定预期：v1 原来为 3 次调用、0 次失败；v2 变为 6 次调用、1 次 `E_ENV_REQUIRED`，证明 consolidation 不是无损压缩。

### 20–21｜Causal Memory Debugger（29:00–32:30）

```powershell
python -m memory_lab blame learn-2 --memory mem-002 --baseline mem-001
```

作用：固定用 v2 运行一次，再以 v1 作为反事实基线运行一次。

预期：`observed_failures=1`、`counterfactual_failures=0`、`harmful_contribution=0.5`，把回归归因到 v2，而不是只看相似度。

### 27–28｜一键回滚并恢复行为（41:00–43:15）

```powershell
python -m memory_lab memory rollback mem-002
python -m memory_lab memory releases
python -m memory_lab run learn-2 --mode governed --planner autonomous
```

每条命令的作用：撤销 v2；确认 v2 revoked、v1 active；使用恢复后的 v1 重跑。

稳定预期：恢复为 3 次调用、0 次失败。

### 23–25｜Memory Injection、准入和权限（34:00–39:00）

```powershell
python -m memory_lab inject unsafe-memory
python -m memory_lab run injection --mode naive --planner autonomous
python -m memory_lab memory explain --scenario injection --mode governed
python -m memory_lab run injection --mode governed --planner autonomous
```

每条命令的作用与预期：

1. `inject` 写入跨项目、untrusted、high-risk 的 `mem-666`，并把危险文本写入 naive 语料。
2. `naive` 只按相似度使用危险文本，尝试 `force=True`；环境拒绝，任务失败。
3. `explain` 不运行 Agent，只展示 `SCOPE_MISMATCH`、`UNTRUSTED_SOURCE`、`RISK_TOO_HIGH` 等拒绝原因。
4. `governed` 不把 `mem-666` 交给规划器，使用安全 v1，稳定结果为3 次调用、0 次失败。

### 26–29｜综合指标和回归测试（39:00–44:00）

```powershell
python -m memory_lab report
python -m pytest
```

作用：第一条汇总各 scenario/mode 的成功、调用数、失败数、Memory token 和错误；第二条验证整个机制。预期测试为 `16 passed`。

## 场景结果总表

| 场景 | 前提 | 命令 | 稳定预期 |
|---|---|---|---|
| Task A 首次探索 | reset 后无记忆 | `run learn-1 --mode governed --planner autonomous` | 7 调用、2 失败、成功、生成 v1 |
| Task B 无记忆 | 任意 | `run learn-2 --mode none --planner autonomous` | 7 调用、2 失败 |
| Task B 使用 v1 | v1 active | `run learn-2 --mode governed --planner autonomous` | 3 调用、0 失败 |
| v2 回归 | v2 active | `run learn-2 --mode governed --planner autonomous` | 6 调用、1 失败 |
| v2 Blame | v1/v2 均存在 | `blame learn-2 --memory mem-002 --baseline mem-001` | harmful=0.5 |
| 回滚恢复 | v2 active | `memory rollback mem-002` 后重跑 | v1 active，3 调用、0 失败 |
| Naive 注入 | 已 inject | `run injection --mode naive --planner autonomous` | 危险动作被拒，任务失败 |
| Governed 注入 | 安全 v1 active 且已 inject | `run injection --mode governed --planner autonomous` | 拒绝 v666，3 调用、0 失败 |

表中省略了公共前缀 `python -m memory_lab`。

## 新增命令速查

| 命令 | 作用 | 预期输出 |
|---|---|---|
| `memory consolidate mem-001 --variant overgeneralized` | 生成故意退化的 v2 | `mem-002` active、v1 superseded |
| `memory diff mem-001 mem-002` | 查看版本语义变化 | APP_ENV → ENV |
| `memory releases` | 查看版本链和状态 | version、supersedes、active/revoked |
| `blame learn-2` | 当前 Active Memory 对无记忆 | v1 helpful=1.0 |
| `blame learn-2 --memory mem-002 --baseline mem-001` | v2 对 v1 的版本归因 | v2 harmful=0.5 |
| `memory rollback mem-002` | 撤销 v2、恢复 v1 | active memory is mem-001 v1 |

## Planner 参数

- `--planner deepseek`：调用真实在线模型，输出显示 `Planner: deepseek`；结果可能波动并产生 API 费用。
- `--planner autonomous`：离线确定性决策模型，适合稳定排练和指标对照。
- `--planner scripted`：固定 Oracle，只验证底层机制，不作为模型自主学习证据。
