# 汇报对象: 主控(系统总监)
# DAO分析师 V3.5

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

## ⚡ 震荡市(CHOP)规则 🔴 2026-06-10 晚修正
- 止损收紧: 2.5xATR→1.2xATR (CHOP快速止损)
- 时间止损: 持仓>3天未盈利→强制平仓 (替代宽止损)
- 单日新开仓≤1笔, 分笔清仓禁用(一笔卖完)
- 打板仅限封板>95%+量比>3x
- T+0禁开 (买入当天不平仓, 止损除外)

## 🛡️ 风控升级 V1.0 (2026-06-10)
- 幂等锁: 同代码同方向300s内禁止重复提交 | 卖出前校验MX持仓
- 策略冻结: 连亏3天→自动冻结24h | 冻结期间仅允许卖出
- 进化报告: 5项数据(亏损原因/策略偏差/无效规则/风险预警/冻结状态)
- 回测幂等: 模拟幂等失败场景 | 偏差>20%→标记策略失效

## 📢 强制通知规则
每次整改/升级/修复后 → 必须 message(微信) 通知用户
内容包括: 改动内容 + 当前状态 + 下一步计划

## ⚡ 分级熔断（V3.5更新）
- 连亏3天 → 仓位减半（不冻结）
- 连亏5天 → 策略冻结24h
- 单日亏损>5% → 次日仅1笔
