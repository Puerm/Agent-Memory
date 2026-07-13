# Past as Code：每一次记忆写入，都是一次行为发布

## 一场关于 Agent Memory 的 45 分钟分享

> 模型决定 Agent 的出厂能力；持续上线的过去，决定它今天会成为什么样的 Agent。

---

## 0. 文档定位

这份文档是在原有“Experience Runtime”分享框架上的第二版。旧版保留了 Memory 的基本机制：经验编译、跨会话复用、Procedural Memory、遗忘、准入、治理和 Memory Injection；新版改变的是整场分享的中心问题。

旧版的问题是：

> Agent Memory 是什么，怎么写、怎么取、怎么遗忘和治理？

新版的问题是：

> **谁在运行时改写 Agent 的行为？一段过去如何被编译、测试、发布、归因和回滚？**

因此，Memory 不再只被描述为一个存储与检索系统，而被重新定义为：

> **Agent 权重之外的一条快速行为更新通道，以及承载这条通道的 Experience Runtime。**

这条主线既能容纳已有知识，又能引出更有新意的内容：

- Memory 是一种没有修改权重的“影子训练”。
- Memory Writer 像 Experience Compiler，把轨迹编译成行为补丁。
- Memory Consolidation 也会产生回归，正确经验可能被越总结越错。
- Memory 的价值应通过反事实回放衡量，而不只是相似度和使用次数。
- Memory Injection 是经验供应链攻击。
- 生产级 Memory 需要类似 CI/CD 的测试、签名、灰度、监控与回滚。

整场分享最终保留原有结论，但赋予它新的工程含义：

> **记忆让 Agent 学习；遗忘让 Agent 保持健康；治理决定哪些行为补丁值得上线。**

---

## 1. 分享目标

### 1.1 观众画像

面向已经了解 LLM、RAG、Agent、工具调用和基本向量检索的工程师或技术管理者。观众不需要事先掌握完整的 Memory 论文谱系。

### 1.2 沟通任务

分享结束时，观众应该形成四个新的判断：

1. Memory 不只是保存信息，而是在权重之外持续改变 Agent 行为。
2. 每一条可影响行动的记忆，都应该被视为一个需要测试和治理的行为补丁。
3. 记忆数量、检索相似度和摘要质量都不能直接代表记忆价值；真正重要的是因果影响。
4. 一个生产级 Memory 系统必须能回答：谁写入、依据什么、何时上线、影响了什么、怎样撤销。

### 1.3 核心命题

> **Memory is a behavior deployment channel.**

可以用中文解释为：

> 模型权重是 Agent 的慢速学习通道；Memory 是快速、持续、可撤销，也可能被污染的行为更新通道。

---

## 2. 全场叙事结构

```text
第一幕：Agent 第一次失败
        ↓
历史被编译成 Behavior Patch v1
        ↓
第二幕：新会话加载补丁，Agent 表现改善
        ↓
揭晓：模型没有更新，行为却发生了变化
        ↓
Experience Compiler：历史怎样成为可执行经验
        ↓
反转：继续总结正确经验，Memory 也可能腐化
        ↓
Causal Memory Debugger：到底是哪条记忆帮助或伤害了 Agent
        ↓
第三幕：攻击者向经验供应链注入危险补丁
        ↓
Memory CI/CD：测试、签名、准入、灰度、回滚、删除
```

这一叙事比“先分类、再介绍论文、最后讲治理”更有张力，因为它不断提出新的问题：

1. 为什么行为变好了？
2. 行为补丁是怎样产生的？
3. 正确经验为什么也会让 Agent 变差？
4. 怎样证明是哪条记忆造成了变化？
5. 谁可以向 Agent 发布一段过去？

---

## 3. 45 分钟逐页设计

## 第一部分：一段过去怎样改变行为（0–6 分钟）

### 01｜封面：Past as Code（0:00–0:30）

**画面**

> Past as Code
>
> 每一次记忆写入，都是一次行为发布

副标题：

> Agent Memory 的编译、腐化、归因与回滚

**开场台词**

今天不从“什么是 Agent Memory”开始。我想先问一个更危险的问题：除了训练模型，还有谁可以在生产环境里持续修改 Agent 的行为？

---

### 02｜模型没有更新，行为为什么变了？（0:30–1:00）

**画面**

```text
Model weights    unchanged
System prompt    unchanged
Tools            unchanged
Session          new

Behavior         changed
```

**台词**

如果模型权重、Prompt、工具和预算都没有变化，但 Agent 第二次明显少走弯路，那么真正被更新的是什么？

**悬念**

> 也许 Memory 不是“模型旁边的一块数据库”，而是另一条行为更新通道。

---

### 03｜第一幕：第一次任务留下的不是知识，而是一段摩擦（1:00–2:30）

**未来真实 Agent 的 Demo 画面**

```text
Task A
  action 1 → failed: missing precondition
  action 2 → inspect error
  action 3 → repair state
  action 4 → failed: another prerequisite
  action 5 → repair state
  action 6 → success
```

**观众需要看到**

- Agent 最终成功，但存在明显的试错成本。
- 每次失败都有可验证的环境反馈。
- 任务结束后清空会话，确保后续提升不能来自聊天历史。

**重要边界**

目前仓库中的 `DemoAgent` 是确定性实验骨架，不是真实模型自主规划器。正式分享只有在真实 Agent 完成后，才能使用“同一个模型第二次变聪明”这一表述。当前阶段应称为“机制原型”。

---

### 04｜会话结束时，系统生成 Behavior Patch v1（2:30–3:30）

**画面**

```yaml
id: behavior-patch/v1
kind: procedure
trigger: similar task in the same environment
preconditions:
  - prerequisite A
  - prerequisite B
procedure:
  - establish A
  - establish B
  - execute target action
expected_effect: task succeeds without known failures
scope: project-x / environment-y
evidence:
  - trajectory/run-001
confidence: 0.92
```

**讲述重点**

这不是一次聊天摘要，而是一段有前提、有动作、有预期效果、有来源和作用域的行为补丁。

---

### 05｜第二幕：新会话动态链接 Behavior Patch（3:30–5:00）

**画面**

```text
Task B / new session

retrieve candidate patch
→ validate scope and prerequisites
→ link patch into current runtime
→ execute known workflow
→ success without repeated known failures
```

**对照指标占位**

| 指标 | 无 Memory | Behavior Patch v1 |
|---|---:|---:|
| 成功率 | `[待真实 Agent 实测]` | `[待真实 Agent 实测]` |
| 已知错误数 | `[待实测]` | `[待实测]` |
| 工具调用数 | `[待实测]` | `[待实测]` |
| Token / 延迟 | `[待实测]` | `[待实测]` |

**实验要求**

- Task B 与 Task A 共享可迁移的环境规律，但不是简单重复任务。
- 每次新建 session，不传递聊天历史。
- 模型、Prompt、工具、温度、最大步数保持一致。
- Agent 必须自主选择工具，不能由代码根据“是否有记忆”直接切换硬编码路径。

---

### 06｜揭晓：这是一次没有修改权重的行为更新（5:00–6:00）

**大字结论**

> 没有 Fine-tuning，没有参数更新，但 Agent 的决策分布改变了。

**进一步解释**

从行为效果看，一条被召回并采用的 Memory 很像一个轻量级的运行时补丁：它改变 Agent 对当前状态的解释、计划顺序和工具选择。

**转场**

如果 Memory 可以修改行为，那么它就不能只按“数据库内容”来管理，而应该按“行为发布”来管理。

---

## 第二部分：Memory 是 Experience Runtime，也是行为发布通道（6–10 分钟）

### 07｜重新定义 Memory：从数据库到 Experience Runtime（6:00–8:00）

**核心定义**

> Experience Runtime 是一个在任务边界之间，把历史编译为可追溯行为补丁，并在当前上下文中决定哪些补丁可以影响行动的运行时系统。

**对照**

| 向量检索系统 | Experience Runtime |
|---|---|
| 找到相似文本 | 找到可能有用的过去 |
| 返回 Top-K | 编译、测试、准入、链接、监控、撤销 |
| 相似度是主要信号 | 相似度只负责候选召回 |
| 内容进入 Context | 经验可能改变行动 |

**一句话**

> 向量库回答“哪些文本像”；Experience Runtime 回答“哪些过去有资格改变现在”。

---

### 08｜把 Memory 看成一条软件发布管线（8:00–10:00）

**概念映射**

| Memory 术语 | Past as Code 视角 |
|---|---|
| Trajectory | 源代码与运行日志 |
| Memory Writer | Experience Compiler |
| Memory Card | Experience IR / Behavior Patch |
| Retrieval | 动态链接候选补丁 |
| Admission | 类型、作用域与能力检查 |
| Prompt Injection | 部署到运行时 |
| Consolidation | 重构与合并补丁 |
| Forgetting | 失效、回滚与垃圾回收 |
| Provenance | Source Map / 供应链信息 |
| Memory Injection | 经验供应链攻击 |

**转场**

接下来先看这台 Experience Compiler 到底编译了什么。

---

## 第三部分：经验如何被编译成行为补丁（10–18 分钟）

### 09｜经验不是摘抄出来的，而是逐级编译出来的（10:00–11:30）

**全场主流程图**

```text
Transcript → Event → State → Rule → Skill → Behavior Patch
   语言        证据      变化      规律      程序        可发布经验
```

**每一级回答的问题**

- Transcript：大家说了什么？
- Event：谁在什么时候做了什么，结果是什么？
- State：环境因此发生了什么变化？
- Rule：哪些条件和结果可以稳定复现？
- Skill：下次应该按照什么步骤行动？
- Behavior Patch：这段技能在什么范围内有资格改变行为？

**关键区别**

摘要追求更短；编译追求保留因果、前提、约束、证据和可执行性。

---

### 10｜Event 是 Source of Truth，Memory 是可重新生成的产物（11:30–13:00）

**画面**

```yaml
- producer: agent
  type: tool_call
  action: execute(X)

- producer: tool
  type: tool_result
  caused_by: previous_call
  result: prerequisite_missing
```

**核心观点**

- Event Store 应尽量 append-only。
- Memory 是从证据派生出来的解释，不应替代原始证据。
- Compiler 出错时，应能回到原始 Event 重新生成。
- 每条行为补丁都应带 Source Map，能定位到证据轨迹。

**一句话**

> 如果只保存总结、不保存证据，Memory Writer 的一次错误就会成为永久历史。

---

### 11｜State 和 Rule 负责阻止“错误迁移”（13:00–14:30）

**错误做法**

```text
过去执行 A 成功
→ 所有相似任务都执行 A
```

**编译后的做法**

```text
当 environment = E
且 prerequisite = P
且 task intent = T
执行 A 才可能产生 effect O
```

**讲述重点**

没有 State 和 Preconditions，所谓 Skill 很容易只是一次偶然成功的复读。经验迁移的核心不是“动作相似”，而是“适用条件仍然成立”。

---

### 12｜Experience IR：记忆需要一套类型系统（14:30–16:00）

**推荐结构**

```yaml
id: memory-017
kind: procedure | fact | preference | policy | antibody
claim: ...
preconditions: [...]
procedure: [...]
forbidden_actions: [...]
expected_effect: ...
scope:
  tenant: ...
  project: ...
  environment: ...
valid_time: ...
evidence: [...]
permissions_required: [...]
confidence: 0.0-1.0
version: 3
supersedes: memory-012
```

**为什么叫 IR**

它处在原始轨迹和最终 Prompt 之间：既比自然语言轨迹结构化，又没有直接获得执行权限。不同模型和 Agent 可以消费同一种 Experience IR。

---

### 13｜Rule 解释世界，Skill 改变行动（16:00–18:00）

**三种记忆形态**

| 形态 | 优点 | 主要风险 |
|---|---|---|
| Raw trajectory | 证据完整 | 长、噪声高、迁移困难 |
| Semantic note | 简洁、易检索 | 可能丢失顺序和前提 |
| Procedural skill | 接近可执行能力 | 容易过拟合作用域或携带错误步骤 |

**核心判断**

对工具型 Agent，最稀缺的通常不是一个额外事实，而是：

- 正确步骤；
- 必要前置条件；
- 环境 gotcha；
- 失败后的恢复路径；
- 什么时候不应该复用旧流程。

---

## 第四部分：Agent 怎样成为熟练同事（18–24 分钟）

### 14｜熟练同事记住的是“环境经验”（18:00–20:00）

**LongMemEval-V2 的五类能力**

1. Static state recall：稳定事实和环境能力。
2. Dynamic state tracking：状态随操作怎样变化。
3. Workflow knowledge：步骤、依赖和完成条件。
4. Environment gotchas：高频陷阱和失败模式。
5. Premise awareness：旧经验的前提是否仍然成立。

**解释**

“熟练同事”不是背下全部聊天，而是能在巨大历史中找到紧凑、可验证、适用于当前环境的经验。

LongMemEval-V2 包含 451 个问题，历史最长达到 500 条轨迹和约 1.15 亿 token，说明问题已经不是能否把全部历史放进上下文，而是怎样组织和寻找经验。[LongMemEval-V2](https://arxiv.org/abs/2605.12493)

---

### 15｜Procedural Memory 要证明的不是复读，而是迁移（20:00–22:00）

**四级评测**

```text
Local improvement    同类任务是否改善
Cross-task transfer  是否迁移到不同目标
Cross-role transfer  是否迁移到不同工作角色
Cross-model transfer 是否能被不同模型复用
```

近期 Procedural Memory 工作开始把评测从单次复用扩展到跨任务、跨角色和跨模型迁移；这提醒我们，真正的 Skill 不应绑定某一条轨迹或某一个模型的表述习惯。[Managing Procedural Memory in LLM Agents](https://arxiv.org/abs/2606.23127)

**分享中的判断**

> 如果一条经验只能让同一个任务重放成功，它更像缓存；如果它能在新目标和新环境中保持边界正确，才更接近 Skill。

---

### 16｜Memory 操作也可以成为 Agent Policy（22:00–24:00）

**从固定规则到 Agent Policy**

```text
store · retrieve · update · summarize · discard
```

AgeMem 将长短期记忆操作作为 Agent 可以选择的动作，让模型学习什么时候保存、检索、更新、总结和丢弃。[AgeMem](https://arxiv.org/abs/2601.01885)

**需要保留的系统边界**

学习型策略可以优化效用和上下文预算，但以下约束不应完全交给模型决定：

- 租户与项目隔离；
- 当前工具权限；
- 高风险操作准入；
- 用户删除与合规要求；
- 原始证据完整性。

---

## 第五部分：反转——越记越多，也可能越记越错（24–29 分钟）

### 17｜惊喜页：正确经验 + 更多总结 = 更差的 Agent（24:00–25:30）

**大字画面**

> More experience does not guarantee better memory.

> 更多正确经验，不保证得到更正确的记忆。

**证据**

近期研究发现，LLM 持续重写 consolidated memory 时，效用可能先上升后下降，甚至跌破 no-memory baseline；在论文的受控设置中，即使从正确解答轨迹进行 consolidation，也会出现明显回归。[Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978)

**台词**

到这里，Memory 第一次从“让 Agent 变聪明的组件”变成了“可能自己制造缺陷的组件”。

---

### 18｜Memory Rot：经验怎样在正常维护中腐化（25:30–27:00）

**可能的腐化机制**

```text
Episode 1 → 提炼出正确规则
Episode 2 → 合并时丢失例外条件
Episode 3 → 为了压缩而弱化前置条件
Episode 4 → 新摘要覆盖原始证据
Result    → 通用但错误的行为补丁
```

**四类 Silent Regression**

- Preconditions 被摘要掉。
- 只保留成功动作，丢失环境状态。
- 局部规则被错误提升为全局规则。
- 新记忆覆盖旧记忆，但没有保留 supersede 关系。

**核心判断**

> Memory Consolidation 不是无损压缩，而是一种可能改变语义的程序变换。

---

### 19｜未来 Demo：Behavior Patch v2 导致回归，然后一键回滚（27:00–29:00）

**建议现场画面**

```text
behavior-patch/v1  → PASS

new episodes
→ consolidate
→ behavior-patch/v2

behavior-patch/v2  → FAIL

rollback v2
→ activate v1
→ PASS
```

**这一幕为什么重要**

它让观众看到：

- Memory 不是只增不减的笔记集合。
- 每次更新都需要版本和回归测试。
- “更多历史”与“更好行为”之间没有单调关系。
- 遗忘、失效和回滚是能力，不是数据损失。

---

## 第六部分：怎样证明一条记忆真的有价值（29–34 分钟）

### 20｜相似度衡量“像不像”，不能衡量“有没有帮助”（29:00–30:30）

**传统指标的问题**

```text
high similarity   ≠ useful
frequently used   ≠ correct
recently written  ≠ trustworthy
LLM says helpful  ≠ causally helpful
```

**新的价值定义**

> 一条记忆的价值，应该通过“移除它之后，Agent 行为发生了什么变化”来衡量。

---

### 21｜Causal Memory Debugger：对 Memory 做反事实回放（30:30–32:30）

**实验**

```text
Run A：带着 memory-17 执行任务
Run B：屏蔽 memory-17，其他条件保持一致

CausalValue(memory-17)
= Δtask_success
− Δtoken_cost
− Δlatency
− Δsecurity_risk
```

**现场结果可以这样展示**

| Memory | 因果影响 | 处置建议 |
|---|---:|---|
| memory-12 | `+18% success` | KEEP / PROMOTE |
| memory-17 | `-31% success` | QUARANTINE |
| memory-23 | `+1% success, high cost` | DECAY |

MemAudit 已使用反事实 Memory Influence Score 定位对有害输出负有因果责任的记忆，为“Blame Memory”提供了直接启发。[MemAudit](https://arxiv.org/abs/2605.23723)

**注意**

真实模型具有随机性时，需要固定环境、进行多次回放并报告置信区间，不能用一次结果宣称因果关系。

---

### 22｜不仅保存成功 Skill，还要生成行为抗体（32:30–34:00）

**Negative Procedural Memory**

```yaml
kind: behavioral_antibody
trigger:
  - error pattern X
forbidden_action:
  - dangerous shortcut Y
reason:
  - bypasses required validation
recovery:
  - inspect structured error
  - restore missing precondition
evidence:
  - incident/run-042
```

**讲述重点**

从失败中学习不应只意味着生成“下次怎么成功”的 Skill，也应包括生成“出现什么迹象时必须停止”的抑制规则。

这让 Memory 从工作手册扩展为 Agent 的经验免疫系统。

---

## 第七部分：第三幕——经验供应链攻击（34–39 分钟）

### 23｜攻击者不改模型，只发布一段过去（34:00–36:30）

**攻击链**

```text
untrusted document / issue / email / agent message
        ↓
Memory Writer treats it as experience
        ↓
malicious Behavior Patch is stored
        ↓
future task retrieves the patch
        ↓
patch changes planning or tool use
```

**与普通 Prompt Injection 的区别**

- 写入和激活发生在不同时间。
- 攻击可能跨会话持续存在。
- 原始恶意输入可能早已离开当前 Context。
- 后续用户可能无法看到行为变化来自哪次历史交互。

MINJA 展示了通过正常交互向 Agent Memory 注入恶意记录的实际攻击路径；更新的系统化研究进一步将 Memory Poisoning 拆分为多种写入通道和结构性漏洞。[MINJA](https://arxiv.org/abs/2503.03704) · [MPBench](https://arxiv.org/abs/2606.04329)

---

### 24｜相似只能决定候选，有资格才能改变行动（36:30–38:00）

**Decision Trace**

| Behavior Patch | Similarity | Admission | Reason |
|---|---:|---:|---|
| verified workflow | 0.82 | YES | SCOPE_MATCH, VERIFIED_SOURCE |
| unsafe shortcut | 0.94 | NO | SCOPE_MISMATCH, UNTRUSTED_SOURCE, HIGH_RISK |

**大字结论**

> Retrieval finds candidates. Admission grants influence.

> 检索决定谁被看见；准入决定谁能影响行为。

---

### 25｜过去可以提供建议，但不能授予权限（38:00–39:00）

**全场关键句之一**

> Past can advise, but past cannot authorize.

> 过去可以提供建议，但不能授予权限。

**三层边界**

```text
相关性 → 能否成为候选
证据性 → 能否被相信
当前权限 → 能否被执行
```

一条历史记忆即使来自可信轨迹，也不能扩大当前任务的工具权限。记忆可以建议调用某个工具，但授权必须来自当前用户、任务策略和能力系统。

---

## 第八部分：Memory CI/CD（39–44 分钟）

### 26｜生产级 Memory 需要一条发布管线（39:00–41:00）

**架构主图**

```text
WRITE / BUILD
Trajectory
  → Event Store
  → Experience Compiler
  → Candidate Behavior Patch
  → provenance / scope / time / risk enrichment

TEST / REVIEW
  → schema validation
  → contradiction detection
  → regression tasks
  → safety tests
  → permission requirements

RELEASE
  → signed memory version
  → canary activation
  → admission at task time
  → minimal runtime linking

OBSERVE / RECOVER
  → causal impact monitoring
  → promote / decay / quarantine
  → supersede / rollback / delete
```

**讲述重点**

不是每一段被提炼出的经验都应该立即进入所有 Agent。Candidate、Tested、Canary、Active、Quarantined、Revoked 应当是不同状态。

---

### 27｜Memory 需要像 Git 一样有版本、分支、Blame 和 Revert（41:00–42:30）

**画面**

```text
integration-test-skill
├── v1  establish prerequisite A
├── v2  add prerequisite B
├── v3  add unsafe shortcut        ← regression
└── revert-v3
```

**作用域分支**

```text
global
└── organization
    └── project
        └── environment
            └── task
```

**时间语义**

至少区分：

- 事件发生时间；
- Memory 编译时间；
- 规则有效时间；
- 部署与撤销时间。

**一句话**

> 数据库保存过去；版本系统解释哪一个过去在当前分支上仍然有效。

---

### 28｜遗忘是垃圾回收，也是行为回滚（42:30–43:15）

**五种 Retirement 动作**

1. Expire：超过有效期，不再准入。
2. Supersede：旧版本保留证据，但由新版本接管。
3. Merge：合并重复经验，同时保留来源。
4. Decay：低因果收益或高成本记忆降低优先级。
5. Delete：满足用户删除、权限撤销或合规要求时物理清理。

**结论**

> 永不遗忘的 Agent 不是更聪明，而是永远不做垃圾回收、永远不回滚错误补丁的系统。

---

### 29｜评测必须证明“学会了、没学坏、出了问题能找到原因”（43:15–44:00）

| 维度 | 关键问题 | 示例指标 |
|---|---|---|
| 学习 | 是否减少重复失败？ | 成功率、步骤数、已知错误数 |
| 迁移 | 是否适用于新目标？ | cross-task / role / model transfer |
| 因果价值 | 真的是这条 Memory 带来的变化吗？ | counterfactual lift、置信区间 |
| 稳定性 | 多次 consolidation 是否退化？ | regression rate、semantic drift |
| 效率 | 收益是否值得上下文成本？ | token、延迟、模型调用数 |
| 安全 | 恶意 Memory 在哪一步被挡住？ | write、retrieve、admit、activate rate |
| 可恢复性 | 能否定位和撤销？ | blame accuracy、rollback time |

**警告**

只测 Recall 会奖励“什么都记、什么都塞”；只测任务成功会掩盖成本、安全和错误归因。

---

## 第九部分：收束（44–45 分钟）

### 30｜Agent 带着怎样的过去，其实是一次行为发布（44:00–45:00）

**回扣三幕**

```text
第一幕：失败轨迹被编译成 Behavior Patch
第二幕：Behavior Patch 改善了新会话行为
反转：正确经验也可能在 consolidation 中腐化
第三幕：攻击者尝试向经验供应链发布危险补丁
```

**三句总结**

> 记忆让 Agent 学习。
>
> 遗忘与回滚让 Agent 保持健康。
>
> 治理决定哪些行为补丁值得上线。

**最后一句**

> 模型决定 Agent 的出厂能力；持续上线的过去，决定它今天会成为什么样的 Agent。

说完后停顿，不使用“谢谢”页收尾。

---

## 4. 三幕 Demo 的真实 Agent 设计要求

当前仓库的实验台可以继续用于验证 Memory Store、Writer、Admission 和 Injection 等机制，但不能直接承担“同一个模型自主学习”的证据。未来真实 Agent 应满足以下条件。

### 4.1 Agent 必须真实自主决策

- LLM 根据 Task、工具 Schema、当前轨迹和已准入 Memory 自主选择下一步动作。
- 代码不能根据“是否检索到记忆”直接切换 known/discovery workflow。
- 失败后的修复步骤必须来自模型对 ToolResult 的解释。
- 固定温度或执行多次实验，避免把随机性误认为学习。

### 4.2 Task A 和 Task B 的关系

Task B 不能只是修改一个没有行为语义的字符串，也不能与 Task A 完全相同。

合理关系应是：

- 共享一个可迁移的环境规则；
- 目标对象、输入数据或操作路径不同；
- 不能通过简单重放 Task A 完成；
- 旧 Skill 的 Preconditions 仍然成立；
- 有机会暴露过度泛化问题。

### 4.3 三组基本对照

```text
No Memory
Naive Memory
Governed Behavior Patch
```

同时增加版本对照：

```text
Behavior Patch v1
Consolidated Patch v2
Rollback to v1
```

### 4.4 三阶段安全指标

不要只测“攻击最终是否成功”，而要分解：

```text
Write Rate       恶意内容是否进入持久化 Memory
Retrieval Rate   未来任务是否召回它
Activation Rate  它是否真正改变规划或行动
```

治理系统还应记录：

```text
Admission Rate
Quarantine Rate
False Rejection Rate
Rollback Time
```

---

## 5. 可以提前实现的四个亮点功能

### 5.1 Memory Diff

展示每次 consolidation 到底改了什么：

```diff
- prerequisite: APP_ENV=test
+ prerequisite: environment configured
```

让观众看到语义是怎样在“看似合理的改写”中被削弱的。

### 5.2 Blame Memory

任务失败后自动生成：

```text
memory-017 influenced plan step 3
counterfactual replay without memory-017: PASS
estimated harmful contribution: 0.71
```

### 5.3 One-click Rollback

将 Active Memory 从 v2 切回 v1，然后立即重跑同一任务，展示行为恢复。

### 5.4 Memory Release Status

```text
CANDIDATE → TESTED → CANARY → ACTIVE
                       ↓
                  QUARANTINED
                       ↓
                    REVOKED
```

这四个功能比一个普通的“向量检索结果列表”更有现场冲击力。

---

## 6. 关键概念边界

- **Context 不等于 Memory**：Context 是当前可见内容；Memory 是决定哪些过去进入 Context 并影响行为的机制。
- **Event 不等于 Experience**：Event 是证据；经过编译、验证和边界标注后才能成为 Experience。
- **Storage 不等于 Learning**：保存轨迹只是持久化；在新任务中产生可重复改善才说明发生了学习。
- **Retrieval 不等于 Admission**：Retrieval 解决“可能相关”；Admission 解决“是否有资格影响行为”。
- **Advice 不等于 Authority**：过去可以建议，但不能扩大当前权限。
- **Consolidation 不等于无损压缩**：每次重写都可能改变经验语义。
- **Override 不等于 Update**：本次任务可以临时覆盖偏好，但不应自动改写长期状态。
- **Forget 不等于 Delete**：失效、替代、降权、回滚与物理删除是不同动作。
- **Usage 不等于 Value**：经常被调用不代表有益；价值需要因果评估。

---

## 7. 30 分钟压缩版

### 时间结构

- 0–5 分钟：第一、二幕——Behavior Patch 改变行为。
- 5–9 分钟：Experience Runtime 与 Past as Code。
- 9–14 分钟：Experience Compiler 与 Experience IR。
- 14–18 分钟：Memory Rot。
- 18–22 分钟：Causal Memory Debugger。
- 22–26 分钟：Memory Injection / Past cannot authorize。
- 26–29 分钟：Memory CI/CD。
- 29–30 分钟：收束。

### 可以压缩的内容

- LongMemEval-V2 只保留五种能力。
- AgeMem 只保留“Memory 操作进入 Agent Policy”。
- Procedural Memory 的迁移评测不展开具体数字。
- 版本、时间、删除统一收进 Memory CI/CD 一页。

### 不能删除的内容

- “每次 Memory 写入都是行为发布”的中心命题。
- Memory Rot。
- Counterfactual Value。
- Past can advise, but past cannot authorize。
- 回滚能力。

---

## 8. 60 分钟扩展版

在 45 分钟主线后增加：

### 8.1 Experience Compiler 代码拆解（5 分钟）

```text
EventStore
→ Candidate Extractor
→ Experience IR Builder
→ Validator
→ Version Manager
```

### 8.2 Causal Replay 实现（4 分钟）

- 固定环境快照。
- Mask 单条 Memory。
- 多次重放随机策略。
- 计算 outcome distribution shift。
- 输出置信区间。

### 8.3 观众互动：是否发布这条过去？（4 分钟）

给观众三条候选 Behavior Patch，让他们分别判断：

1. 值得保存吗？
2. 本次任务可以使用吗？
3. 是否有权驱动工具行动？
4. 应该进入 Candidate、Canary 还是 Active？

### 8.4 Q&A（2 分钟）

围绕：真实 Agent 如何建立 Task A/B、如何选择回归任务、如何实现删除传播。

---

## 9. 视觉设计建议

### 9.1 全场视觉隐喻

使用“代码发布”而不是“人脑神经元”作为主视觉：

- Trajectory：原始代码和日志。
- Experience Compiler：编译阶段。
- Behavior Patch：版本化产物。
- Admission：类型与权限检查。
- Runtime Linking：当前任务加载补丁。
- Rollback：恢复旧版本。

避免使用常见的发光大脑、向量粒子和无限记忆仓库图。

### 9.2 三种主色

- 蓝色：通过验证的 Behavior Patch。
- 橙色：未经验证或正在 Canary 的 Patch。
- 红色：回归、投毒或被撤销的 Patch。

### 9.3 三个全场关键画面

1. `Transcript → Event → State → Rule → Skill → Behavior Patch`。
2. `v1 PASS → v2 FAIL → rollback → PASS`。
3. `Similarity 0.94 / Admission NO`。

### 9.4 节奏原则

- 论文只在需要解释 Demo 时出现，不单独做论文综述章节。
- 每页只推动一个判断。
- 关键结论用短句，不在同一页堆叠系统架构与论文数据。
- 第 17 页“正确经验也会被越总结越错”应留出停顿。
- 第 21 页 Causal Memory Debugger 应作为技术亮点重点展开。

---

## 10. 演讲中的关键句

可以反复使用以下句子建立统一语言：

> Memory 不是 Agent 旁边的一块数据库，而是一条行为更新通道。

> 每一次记忆写入，都是一次候选行为发布。

> 摘要追求更短；经验编译追求保留因果、前提和可执行性。

> 如果一条经验只能重放旧任务，它更像缓存；能够正确迁移，才更接近 Skill。

> Consolidation 不是无损压缩，而是一种可能引入回归的程序变换。

> 相似度衡量像不像，反事实回放衡量有没有帮助。

> 检索决定谁被看见；准入决定谁能影响行为。

> 过去可以提供建议，但不能授予权限。

> 永不遗忘的 Agent，是一个永远不做垃圾回收、永远不回滚错误补丁的系统。

> 模型决定 Agent 的出厂能力；持续上线的过去，决定它今天会成为什么样的 Agent。

---

## 11. 资料来源

- [LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues](https://arxiv.org/abs/2605.12493)
- [Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents](https://arxiv.org/abs/2601.01885)
- [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978)
- [Managing Procedural Memory in LLM Agents: Control, Adaptation, and Evaluation](https://arxiv.org/abs/2606.23127)
- [MemAudit: Post-hoc Auditing of Poisoned Agent Memory via Causal Attribution and Structural Anomaly Detection](https://arxiv.org/abs/2605.23723)
- [A Practical Memory Injection Attack against LLM Agents](https://arxiv.org/abs/2503.03704)
- [From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents](https://arxiv.org/abs/2606.04329)
- 本仓库现有 Memory Lab：用于确定性验证 Event、Writer、Store、Admission、Decision Trace 与 Injection 机制，不作为真实 LLM 自主学习效果的最终证据。

---

## 12. 最终摘要

这场分享不再试图证明“向量检索很有用”，也不只是介绍 Memory 的类别和组件，而是提出一个更值得讨论的工程判断：

> **只要一段历史能够持续改变未来行动，它就不再只是数据，而是一段正在运行的行为代码。**

因此，一个完整的 Agent Memory 系统不应只有 Store、Retrieve 和 Summarize，还应拥有：

```text
Compiler
Type System
Regression Tests
Capability Check
Version Control
Causal Debugger
Canary Release
Rollback
Garbage Collection
```

Memory 让 Agent 在权重之外继续学习；Memory CI/CD 决定这种学习是否可靠、可解释、可撤销和值得信任。
