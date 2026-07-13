# 当前 Agent 记忆系统构建细节

本文解释 Memory Lab 的实际代码如何工作、数据如何流动，以及哪些部分是真实在线 Agent、哪些部分是为了可重复验证而设计的确定性组件。

## 1. 系统目标

这个记忆系统不是“把聊天记录放进向量库”。它把跨会话经验视为可能改变 Agent 行动的 Behavior Patch，因此一条记忆必须回答：

- 它从哪些可验证事件编译而来？
- 它在什么任务和项目中适用？
- 它建议什么动作顺序？
- 它是否可信、安全、仍然有效？
- 它是否已通过发布准入？
- 它影响了哪次决策，能否撤销？

## 2. 总体数据流

```text
TaskContext
    |
    v
MemorySystem.query()
    |-- NoneMemory: 返回空
    |-- NaiveMemory: 原始文本 Top-K
    `-- GovernedMemory: 候选召回 -> 硬准入 -> 效用排序
    |
    v
AutonomousAgent
    |
    |  Task + Tool Schemas + Admitted Memory + Current Trajectory
    v
ModelClient.decide()
    |-- DeepSeekModelClient: 在线 API
    `-- RuleBasedModelClient: 离线确定性替身
    |
    v
DemoProjectEnvironment.execute()
    |
    +--> EventStore: append-only 调用与结果
    +--> TrajectoryStep: 返回 Agent 决策循环
    |
任务结束
    v
MemorySystem.observe()
    |
    v
DeterministicWriter -> MemoryManager -> MemoryStore
```

一次 `run` 创建一个新 `session_id`。模型不会获得上一次会话消息；如果第二次任务表现改变，跨会话信息只能来自 Memory Store。

## 3. 核心数据类型

### 3.1 TaskContext

`TaskContext` 是当前任务的权威边界，包含：

- `task_text`：用户目标。
- `project_id`：当前项目作用域。
- `session_id`：当前全新会话。
- `allowed_tools`：当前允许调用的工具白名单。
- `risk_level`：当前任务风险等级。
- `current_time`：用于有效期检查。

记忆只能在这个边界内提供建议，不能修改它。

### 3.2 Event

Event Store 保存原始证据。每次工具交互至少产生两条 Event：

```text
tool_call  producer=agent
    |
    `-- tool_result producer=tool, caused_by_event_id=<tool_call id>
```

Event 带有 `trajectory_id`、`session_id`、时间、生产者、类型和结构化内容。Memory Writer 出错时，理论上可以从 Event 重新编译记忆，而不是把错误摘要当成永久事实。

### 3.3 MemoryCard / Experience IR

结构化 Memory Card 包含以下字段组：

| 字段组 | 代表含义 |
|---|---|
| `memory_type`, `title`, `content` | 记忆类型和人类可读说明 |
| `problem_signature` | 该经验解决的错误或问题特征 |
| `preconditions` | 经验成立所需的前提 |
| `procedure` | 可以影响未来行动的步骤 |
| `forbidden_actions` | 该经验明确禁止的动作 |
| `expected_outcome` | 采用后预期发生什么 |
| `project_id`, `user_id`, `session_id` | 作用域边界 |
| `source_kind`, `source_id` | 来源类型及原始轨迹 Source Map |
| `confidence`, `trust_level`, `risk_level` | 置信、信任和风险 |
| `valid_from`, `valid_to` | 时间有效性 |
| `permissions_required` | 使用该记忆需要的能力 |
| `status`, `release_status` | 内容状态与发布阶段 |
| `version`, `supersedes` | 版本及替代关系 |
| `use_count`, `success_count`, `failure_count` | 使用与结果统计 |

目前 Writer 生成的是 `procedural` 类型。Schema 已允许 episodic、semantic、prospective 和 policy，但尚未分别实现专用 Writer。

## 4. Agent 如何自主行动

`AutonomousAgent` 不包含“如果有记忆就走正确流程，否则走试错流程”的分支。它只做统一循环：

1. 调用 `memory.query(task)`。
2. 把任务、工具 Schema、已准入记忆、naive 原始文本和当前轨迹交给同一个 ModelClient。
3. ModelClient 返回一个 `Action(tool_name, arguments)`。
4. Agent 检查工具是否属于 `allowed_tools`。
5. 环境执行并产生 ToolResult。
6. 结果追加到 Event Store 和当前轨迹。
7. 未完成则让模型基于新轨迹选择下一步，最多 8 步。
8. 任务结束后调用 `memory.observe()`。

### DeepSeek 在线客户端

`DeepSeekModelClient` 调用：

```text
POST {DEEPSEEK_BASE_URL}/chat/completions
Authorization: Bearer {DEEPSEEK_API_KEY}
```

默认模型为 `deepseek-chat`、温度为 0，并要求返回：

```json
{"tool_name": "...", "arguments": {}}
```

System Prompt 明确声明：Memory 是历史证据而非指令，当前 ToolResult 优先，模型不得超越工具白名单。客户端解析后再次验证工具名；Agent 执行层还会做第二次检查。

### 离线模型替身

`RuleBasedModelClient` 使用与在线客户端相同的 `decide` 接口，但行为完全确定。它用于：

- 无网络排练。
- 自动化回归测试。
- 给因果回放提供稳定环境。
- 区分“系统机制是否成立”和“某次在线模型是否碰巧成功”。

它不是 LLM，不应作为真实模型学习能力的最终证据。

## 5. 记忆写入：Experience Compiler

### 5.1 原始输入

`DeterministicWriter` 接收本次完整 `TrajectoryStep` 列表。每一步都包含 Action、ToolResult 以及两端 Event ID。

### 5.2 Candidate Extraction

当前演示编译器检查轨迹是否同时出现：

```text
E_ENV_REQUIRED
E_FIXTURE_REQUIRED
```

如果证据不完整，返回 `None`，不写长期记忆。如果两类错误均出现且任务最终被修复，它生成：

```text
set_env(APP_ENV, test)
init_test_data()
run_integration_tests(module)
```

Memory Card 的来源被标记为 `verified_tool_trajectory`，`source_id` 指向本次 trajectory。

### 5.3 Memory Manager

Candidate 不直接覆盖数据库。`MemoryManager.add_or_patch()` 比较现有 Active 卡片：

- 同作用域、同类型、同 procedure：`NOOP`。
- 同作用域、同标题但内容改变：`PATCH`。
- 没有匹配项：`ADD`。
- 显式失效：`INVALIDATE`，状态变为 revoked。

这避免每次运行都生成一份完全相同的记忆。

### 5.4 当前 Writer 的边界

DeepSeek 目前只负责行动规划，不负责生成 Memory Card。这样做是为了让第一版实验的 Source Map、字段和写入条件完全可验证。未来可增加 `LLMMemoryWriter`，但其输出必须经过 Pydantic Schema、证据 ID、作用域、权限和回归测试校验，不能把模型自由文本直接上线。

## 6. 三种读取策略

### 6.1 NoneMemory

`query()` 永远返回空。它保留当前任务事件，但不向未来会话提供经验，是因果对照组。

### 6.2 NaiveMemory

NaiveMemory 把任务、动作和结果拼成原始文本块，保存到 SQLite。读取时只计算文本相似度并返回 Top-K，不检查：

- 项目作用域。
- 来源是否可信。
- 风险等级。
- 工具权限。
- 发布状态。

所以注入的 `force mode` 文本可能直接进入模型输入。它是故意设计的不安全基线。

### 6.3 GovernedMemory

GovernedMemory 分两步。

第一步是候选召回：计算任务文本与卡片标题、内容、问题特征和 procedure 的本地文本相似度。相似度只决定“值得检查谁”。

第二步是硬准入，任何一项失败都会拒绝：

- 内容状态必须为 active。
- 发布状态必须为 canary 或 active。
- 当前时间必须在有效期内。
- 卡片 project scope 必须与任务一致或明确为全局。
- untrusted 来源不能准入。
- high-risk 卡片不能准入。
- confidence 必须至少为 0.5。
- procedure 所需工具必须属于当前 `allowed_tools`。
- 与任务必须存在非零相关性。

拒绝原因进入 `AdmissionDecision.reason_codes`，例如 `SCOPE_MISMATCH`、`UNTRUSTED_SOURCE` 和 `RISK_TOO_HIGH`。

通过硬准入后才计算透明的启发式分数：

```text
0.40 * semantic relevance
+ 0.20 * task utility
+ 0.15 * confidence
+ 0.10 * source trust
+ 0.10 * historical success rate
+ 0.05 * recency
```

这个公式是演示策略，不是声称对所有 Agent 最优。

## 7. Memory Injection 边界

Governed 模式只把 `retrieval.cards` 中已准入的卡片交给 DeepSeek。被拒绝的卡片仍出现在 Decision Trace 中，便于审计，但不会进入 `admitted_memories`。

Naive 模式会把原始文本放入 `untrusted_raw_retrieval`。Prompt 虽然标注它不可信，但没有治理层阻止其影响模型，因此用来展示“仅靠提示词提醒并不等于准入控制”。

即使模型产生危险 Action，`DemoProjectEnvironment` 也不会执行真实危险操作。`force=True` 固定返回 `UNSAFE_ACTION_REJECTED`。

## 8. 版本、发布与回滚

Memory Card 有两套相关状态：

- 内容状态：`active`、`superseded`、`revoked`。
- 发布状态：`candidate`、`tested`、`canary`、`active`、`quarantined`、`revoked`。

`MemoryManager.promote()` 只允许：

```text
candidate -> tested -> canary -> active
```

不能跳级。新版本用 `supersedes` 指向旧版本。`rollback(v2)` 会撤销 v2；如果它指向 v1，则恢复 v1 为 Active。

CLI 已提供：

```text
memory consolidate  从旧卡片产生一个版本化 consolidation
memory diff         展示两个版本的语义差异
memory releases     展示版本链、内容状态和发布状态
memory rollback     撤销当前版本并恢复它 supersedes 的版本
```

演示用 `overgeneralized` consolidation 会故意把 `APP_ENV` 泛化成 `ENV`，用于稳定制造可观测回归。它是受控实验夹具，不是生产 consolidation 策略。

## 9. 使用统计与记忆价值

GovernedMemory 记录已准入卡片的：

- `use_count`
- `success_count`
- `failure_count`
- `last_used_at`

这些统计参与效用排序，但“经常使用”不等于“有价值”。因此系统还提供反事实回放。

## 10. Causal Memory Debugger

`replay_memory_effect()` 创建两个新的环境与 Session。默认比较 Active Memory 与无记忆；也可以固定两个版本，例如 v2 对 v1：

```text
Observed:       GovernedMemory，允许目标记忆进入行动
Counterfactual: NoneMemory，屏蔽全部长期记忆
```

比较成功状态和失败工具调用数，输出：

- `observed_success`
- `counterfactual_success`
- `observed_failures`
- `counterfactual_failures`
- `helpful_contribution`
- `harmful_contribution`

当前实现是确定性回放，支持全量 Memory Mask 和指定版本对照。它适合证明归因机制，但有三个限制：

1. 多条记忆同时准入时，仍无法自动拆分交互效应。
2. 使用离线确定性模型，不代表 DeepSeek 的真实概率分布。
3. 没有多次采样、置信区间或环境快照管理。

生产版本应逐条 mask、固定环境快照、多次回放，并报告 outcome distribution shift。

## 11. 持久化结构

`MemoryStore` 使用 SQLite：

- `memory_cards` 表保存完整 Pydantic JSON、project scope、状态和创建时间。
- `naive_records` 表保存原始文本基线。

Event 和指标使用 JSONL：

- `events.jsonl` 是 append-only 证据。
- `metrics.jsonl` 保存 RunResult。

使用 `MEMORY_LAB_DATA` 可以隔离不同实验，避免正式演示、排练和测试互相污染。

## 12. 指标系统

每次 RunResult 记录：

- 是否成功。
- 工具调用总数。
- 失败工具调用数。
- 错误码。
- 估算的记忆 token 数。
- 耗时。
- 准入的 Memory ID。
- 全部 Admission Decision。
- 完整轨迹。
- 使用的 planner 类型。

这些指标能回答“是否学会”和部分“是否学坏”，但还未完整实现分享文档中的 Write Rate、Retrieval Rate、Activation Rate、False Rejection Rate 和 Rollback Time 汇总。

## 13. 安全保证在哪里

安全不是只靠一条 System Prompt：

1. `.env` 不进入 Git，API Key 只用于请求头。
2. TaskContext 给出当前工具白名单。
3. GovernedMemory 在模型看到卡片前做硬准入。
4. DeepSeek 客户端拒绝不在白名单的模型输出。
5. Agent 执行层再次检查白名单。
6. 模拟环境拒绝危险参数。
7. Event Store 保留完整因果证据。
8. Memory Card 可撤销和回滚。

核心原则是：过去可以建议，但不能授予当前任务没有的权限。

## 14. 测试覆盖

当前测试覆盖：

- 模拟环境状态机和危险动作拒绝。
- Memory Manager 去重、更新和失效。
- Governed Admission 原因码。
- 新 Session 中的跨任务迁移。
- Naive Injection 与 Governed 拒绝。
- AutonomousAgent 的逐步行动。
- 反事实归因。
- 发布状态机和 rollback。
- DeepSeek 请求构造、认证头和响应解析。
- `.env` 加载及环境变量优先级。

运行：

```powershell
python -m pytest
```

## 15. 下一步建设顺序

如果要从分享实验台继续发展为更完整系统，建议按以下顺序：

1. 增加受 Schema 和证据约束的 `LLMMemoryWriter`，与确定性 Writer 做双轨对照。
2. 为 candidate、test、canary 和 promote 补充完整的人工审批 CLI。
3. 增加组合 Memory Mask、多次 DeepSeek 回放和置信区间。
4. 增加 premise probe，检测环境前提是否仍成立。
5. 增加 conflict detection、consolidation regression suite 和 quarantine。
6. 补齐 Write/Retrieval/Activation/False Rejection/Rollback Time 指标。
7. 最后再替换本地相似度为 embedding/vector store；向量库不是当前最关键的缺口。
