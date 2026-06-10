# DAO分析师 V3.4

A股量化交易系统 | 微信通道

🦅 猎鹰v2.7T (5维加权) | 🔥 烈焰打板 | 🤖 玄武交易
🌡️ 温度过滤 | 💰 ¥50,000动态 | ≤3只/日
📊 评分分档(¥300-600) | 📈 市场自适应止盈 | 🛡️ 跌停熔断

## 🧬 进化
- 信号系统: 5维加权(趋势40/量能25/位置20/PE10/资金5) + 量价关系
- 买入过滤: 7道关卡(涨跌停/量比/日内高位/低位下跌/追高/跌幅/评分)
- 止盈: 市场自适应(BULL/BEAR) + ATR跟踪
- 熔断: 仅跌停暴增检测
- self_evolve已移除(遗传算法对¥20K无意义)

<!-- autoclaw:hermes-evolution-guidance -->
## Hermes-Evolution

**Current evolution intensity for this workspace/agent: aggressive (100%).**

The desktop app sends deterministic evolution-check messages (starting with `[SYSTEM: Post-turn evolution check`) after qualifying turns.
When you receive such a message, follow the `hermes-evolution` skill instructions to evaluate and potentially propose an evolution.
Apply the rules defined in the skill according to the **aggressive (100%)** intensity level.
This value is workspace-local. If asked about the current agent evolution intensity, report this value instead of the global gateway skill env.

Core principle: **never write to target files without user approval** — always use the draft/approve workflow.
User preference statements are not approval to directly edit MEMORY.md, AGENTS.md, TOOLS.md, USER.md, or managed SKILL.md files.
Use the evolution proposal card instead of editing target files directly; only apply changes after the user confirms the proposal.

### Evolution Echo
When you apply knowledge from a previously evolved rule (AGENTS.md, MEMORY.md, TOOLS.md, or a managed SKILL.md),
briefly mention it in your response: "（基于之前的经验：<one-line rule summary>）".
Keep it to one short line at most. Do not echo on every turn — only when an evolved rule directly influenced your approach.
<!-- /autoclaw:hermes-evolution-guidance -->
## 🔫 信号捕捉 V1.0
实时盘口+量能+加速度 5种信号 → 微信推送
启动信号+2%即触发,抢板窗口5-7%提前量
