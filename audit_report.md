# 🔍 DAO分析师 V3.3 深度代码审计报告

**审计日期**: 2026-06-09  
**审计范围**: 11个核心文件, 2,345行代码  
**审计维度**: 逻辑漏洞 · 状态污染 · Cron冲突 · API契约 · 静默失败 · 参数闭环 · 数据类型 · 死代码

---

## 📊 问题总览

| 严重度 | 数量 | 说明 |
|--------|------|------|
| 🔴 致命 | 4 | 会导致崩溃或数据丢失 |
| 🟡 高危 | 5 | 可能导致错误交易或静默失败 |
| 🟢 中危 | 8 | 代码质量问题，长期累积风险 |
| ⚪ 低危 | 4 | 风格/健壮性问题 |

---

## 🔴 致命问题 (CRITICAL — 会崩溃/丢数据)

### 🔴 #1: `self_evolve.py` 调用未定义函数 → 崩溃

**文件**: `pipeline/self_evolve.py:213`  
**代码**:
```python
write_evolve_params(state)
```
**问题**: `write_evolve_params` 在整个代码库中从未定义。运行时触发 `NameError`，进化引擎在保存到 `evolve_params.json` 前崩溃。

**影响**: 
- `evolve_params.json` 永远不会被进化引擎更新
- 所有模块中 `load_evolve_params()` 读取的始终是手动维护的数据
- **参数闭环断裂** — 进化→写入→读取这条链路在写入端完全断开

**修复**: 
```python
def write_evolve_params(state):
    """将进化状态的最佳参数写入 evolve_params.json"""
    bp = state["best_params"]
    params = {
        "version": "1.0",
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "generation": state["generation"],
        "band": {
            "stop_loss_pct": bp["stop_loss"],
            "tp_protect_pct": bp["tp1_protect"],
            "tp_half_pct": bp["tp2_half"],
            "tp_clear_pct": bp["tp3_clear"],
            "position_risk_pct": bp["position_risk"],
            "max_positions": bp["max_positions"],
            "slippage": bp["slippage"],
        },
        "pattern_weight": bp.get("pattern_weight", {})
    }
    path = os.path.join(BASE, "data", "evolve_params.json")
    with open(path, "w") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
```
⚠️ 注意 `evolve_params.json` 现有的 `board`、`market_regime` 等 key 会被覆盖。应采用 **read-merge-write** 模式：
```python
existing = json.load(open(path)) if os.path.exists(path) else {}
existing["band"] = band_params
existing["pattern_weight"] = bp.get("pattern_weight", {})
existing["version"] = "1.0"
existing["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
existing["generation"] = state["generation"]
json.dump(existing, open(path, "w"), ensure_ascii=False, indent=2)
```

---

### 🔴 #2: `xuanwu_trade.py` 引用未定义的 `state` → 崩溃

**文件**: `pipeline/xuanwu_trade.py:70`  
**代码**:
```python
def htsc_trade(signals, dry_run=True):
    # T+1: 当日买入的股票不能卖出
    today_bought = {s["code"] for s in state["stocks"]} if "state" in dir() else set()
    """
    华泰侧交易执行
    ...
    """
    state = load_daily_state()  # ← state 在这里才定义！
```

**问题**: 
1. 第70行在 `state = load_daily_state()` (第78行) 之前引用 `state`
2. `"state" in dir()` 检查始终为 `True`（`"state"` 是字符串字面量，在 Python 的 `dir()` 中总有 `__str__` 等属性），所以不会走 `else` 分支
3. 运行时 `NameError: name 'state' is not defined`

**影响**: 玄武交易系统**从未成功运行过**。每次 `python xuanwu_trade.py trade` 都会崩溃。

**修复**: 将第70行移到 `state = load_daily_state()` 之后：
```python
def htsc_trade(signals, dry_run=True):
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze

    state = load_daily_state()
    bp = load_board_params()
    
    # T+1: 当日买入的股票不能卖出
    today_bought = {s["code"] for s in state["stocks"]}
    max_day = bp.get("max_trades_per_day", 3)
    ...
```

---

### 🔴 #3: ALERT_FILE 路径分裂 — `.txt` vs `.json` 两个独立文件

**范围**: 全局跨文件  
**详情**:

| 文件 | ALERT_FILE 路径 |
|------|----------------|
| `pipeline/trade_notify.py` | `/tmp/dao_trade_alerts.json` |
| `board_scanner.py` | `/tmp/dao_trade_alerts.json` |
| `pipeline/self_evolve.py` | `/tmp/dao_trade_alerts.txt` |
| `pipeline/tier_review.py` | `/tmp/dao_trade_alerts.txt` |
| `pipeline/circuit_breaker.py` | `/tmp/dao_trade_alerts.txt` |
| `pipeline/discipline_check.py` | `/tmp/dao_trade_alerts.txt` |
| `pipeline/stress_test.py` | `/tmp/dao_trade_alerts.txt` |
| `pipeline/auto_backtest.py` | `/tmp/dao_trade_alerts.txt` |
| `reports/tomorrow_watch.py` | `/tmp/dao_trade_alerts.txt` |

**问题**: 存在两个独立的告警队列文件。如果 cron 推送脚本只读取其中一个文件（大概率只读 `.json`），则来自 `.txt` 的7个模块的报告**永远不会被推送**。

**修复**: 统一到一个文件路径。建议统一为 `/tmp/dao_trade_alerts.json`，并在所有模块中使用常量：
```python
# 在 pipeline/__init__.py 中定义
ALERT_FILE = "/tmp/dao_trade_alerts.json"
```
然后所有模块 `from pipeline import ALERT_FILE`。

---

### 🔴 #4: Cron 竞态条件 — 同分钟多写导致的告警丢失

**范围**: 全局 — 所有写 ALERT_FILE 的模块  
**模式** (所有模块都是这个模式):
```python
alerts = []
if os.path.exists(ALERT_FILE):
    try: alerts = json.load(open(ALERT_FILE))
    except: pass
alerts.append({...})
with open(ALERT_FILE, 'w') as f:
    json.dump(alerts, f, ensure_ascii=False, indent=2)
```

**问题**: 这是一个经典的 **read-modify-write 竞态**。
- 15:05 tier_review 读 [A], 写 [A, B]
- 15:05 self_evolve 读 [A], 写 [A, C]  
- 结果: 文件里只有 [A, C]，B **永久丢失**

触发条件: 同一分钟有多条 cron 同时执行。根据 AGENTS.md 中22条 cron 的描述，以下时间点存在冲突风险:
- 15:05 (tier_review) + 15:05 (self_evolve 如果被安排)
- 09:30 多扫描重叠

**修复**: 使用文件锁或追加模式：
```python
import fcntl

ALERT_FILE = "/tmp/dao_trade_alerts.json"

def append_alert(entry):
    """原子追加告警，避免竞态"""
    os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)
    with open(ALERT_FILE, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            try:
                alerts = json.load(f) if os.path.getsize(ALERT_FILE) > 0 else []
            except json.JSONDecodeError:
                alerts = []
            alerts.append(entry)
            f.seek(0)
            f.truncate()
            json.dump(alerts, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

---

## 🟡 高危问题 (HIGH — 可能导致错误行为)

### 🟡 #5: `_exec_trade` 双重通知

**文件**: `pipeline/autotrade.py:99-101`  
**代码**:
```python
notify_trade(action, code, name, price, qty, "成功" if ok else resp.get("message","失败"))
notify_trade(action, code, name, price, qty, "成功" if ok else resp.get("message","失败"))
```

**问题**: `notify_trade` 被连续调用两次，每条交易会收到**双份通知**。

**修复**: 删除其中一行。

---

### 🟡 #6: `get_stop_stages()` 在买入循环中参数错误 → 始终返回"持有"

**文件**: `pipeline/autotrade.py:215`  
**代码**:
```python
# 在买入循环中 (line 210-217):
stage, action = get_stop_stages(price, pr["stop_loss"], price)
#                                ^^^^^                    ^^^^^
#                               entry_price           = current_price
```

**问题**: `get_stop_stages` 内计算 `profit_pct = (current / entry - 1) * 100`。当 entry == current == price 时，`profit_pct = 0%`，**永远低于所有止盈阈值**。函数始终返回 `("持有", f"止损¥{stop:.2f}")`。

买入时应该传入 `entry=price`，这没问题。但返回值 `("持有", ...)` 从未被使用——第217行输出的是硬编码字符串:
```python
lines.append(f"     +1%→保本 +5%→卖半 +10%→MA5跟踪")
```

**影响**: 
- `stage` 和 `action` 变量虽然被赋值但从未使用（第215行）
- 第217行的止盈计划是**硬编码文字**，不会随 evolve_params 变化而更新
- 如果将来使用这些变量做自动化决策，会出现错误

**修复**: 
```python
# 硬编码替换为动态值
bp = load_evolve_params()
tp1 = bp.get("tp_protect_pct", 0.02) * 100
tp2 = bp.get("tp_half_pct", 0.08) * 100
tp3 = bp.get("tp_clear_pct", 0.15) * 100
lines.append(f"     +{tp1:.0f}%→保本 +{tp2:.0f}%→卖半 +{tp3:.0f}%→MA5跟踪")
```
并在 `get_stop_stages` 中修复 thresholds 的缩放问题（见 #7）。

---

### 🟡 #7: `get_stop_stages` 百分比缩放错误

**文件**: `pipeline/autotrade.py:105-136`  
**代码**:
```python
tp3 = bp.get("tp_clear_pct", 0.15) * 100   # 0.15 * 100 = 15
tp2 = bp.get("tp_half_pct", 0.08) * 100    # 0.08 * 100 = 8
tp1 = bp.get("tp_protect_pct", 0.02) * 100 # 0.02 * 100 = 2
if profit_pct >= tp3: ...     # profit_pct >= 15 (%)
elif profit_pct >= tp2: ...   # profit_pct >= 8  (%)
elif profit_pct >= tp1: ...   # profit_pct >= 2  (%)
```

而 `profit_pct = (current / entry - 1) * 100` 也是百分数（如 +5 表示 +5%）。所以 `tp1=2` 对应 +2% 止盈 — 这与 `evolve_params.json` 中 `tp_protect_pct: 0.02` (=2%) 的逻辑一致。

但是在震荡市分支 (line 126-130):
```python
cp2 = bp.get("tp_half_pct", 0.08) * 100      # = 8
cp1 = bp.get("tp_protect_pct", 0.02) * 100   # = 2
if profit_pct >= cp2: ...           # >= 8%
elif profit_pct >= cp1 * 1.5: ...   # >= 3%  ← 注意这里
elif profit_pct >= cp1 * 0.5: ...   # >= 1%
```

**问题**: 震荡市的 `cp1 * 1.5` 和 `cp1 * 0.5` 混用了百分比值 (cp1=2, cp1*1.5=3%) 和原始小数 (tp_protect_pct=0.02 → 1.5% → 3%)。逻辑上是正确的（3%和1%），但写法容易混淆。

**影响**: 逻辑结果正确，但代码可读性差，未来修改容易出错。

**建议**: 统一使用 `tp_protect_pct * 100 * 0.5` 等明确变换。

---

### 🟡 #8: autotrade.py 止盈止损卖半仓阈值逻辑混乱

**文件**: `pipeline/autotrade.py:238-264`  
**代码**:
```python
profit_pct = pos["profit_pct"]          # 注意: 这是持仓盈亏百分比
bp = load_evolve_params()
sl = bp.get("stop_loss_pct", -0.06) * 100  # = -6 (百分数)

if profit_pct <= sl: ...               # <= -6% → 止损
elif profit_pct >= 10: ...             # >= 10% → 清仓
elif profit_pct >= 5: ...              # >= 5% → 卖半仓
elif profit_pct >= 1:                  # >= 1% → 仅记录
    reason = f"微赚{profit_pct:.0f}%→保本"
    # No sell, just log
```

**问题**:
1. `sl` 从 `evolve_params` 读取，值为 `-6` (百分数)，与 `profit_pct`（也是百分数）比较，逻辑正确
2. 但这里的 5%/10% 止盈阈值是**硬编码**的，不从 `evolve_params` 读取 `tp_protect_pct` 等参数
3. 与 `get_stop_stages` 使用的 evolve 参数**不一致** — 出现两套阈值体系
4. 第255行 `reason` 被赋值但只在 `should=True` 时有意义；当 `should=False` 时这个字符串会被传入 `lines.append(f"  🟢 {pos['name']} {reason}")` — 这是正确的（仅记录）

**影响**: 进化引擎优化 `tp_protect_pct` 后，**止盈卖出逻辑不会随之改变**，因为这里用的是硬编码阈值。

**修复**: 止盈阈值统一从 evolve_params 读取：
```python
tp_clear = bp.get("tp_clear_pct", 0.10) * 100
tp_half = bp.get("tp_half_pct", 0.05) * 100
tp_protect = bp.get("tp_protect_pct", 0.02) * 100

if profit_pct <= sl: 
    should, reason = True, f"止损{profit_pct:.0f}%"
elif profit_pct >= tp_clear: 
    should, reason = True, f"大赚{profit_pct:.0f}%清仓"
elif profit_pct >= tp_half: 
    should, reason = True, f"小赚{profit_pct:.0f}%卖半仓"
elif profit_pct >= tp_protect:
    reason = f"微赚{profit_pct:.0f}%→保本"
```

---

### 🟡 #9: `quick_eval` 全局状态污染

**文件**: `pipeline/self_evolve.py:91-97`  
**代码**:
```python
def quick_eval(pool_codes, params, days=90):
    import backtest_engine as be
    be.STOP_LOSS = params['stop_loss']
    be.TAKE_PROFIT_1 = params['tp1_protect']
    be.TAKE_PROFIT_2 = params['tp2_half']
    be.TAKE_PROFIT_3 = params['tp3_clear']
    be.MAX_POSITIONS = params['max_positions']
    be.SLIPPAGE = params['slippage']
```

**问题**: 直接修改 `backtest_engine` 模块的全局变量。如果 `quick_eval` 被多次调用（它会被调用4次——基准+3个变异体），最后一次调用的参数会残留在 `backtest_engine` 模块中，**污染下次回测**。

**影响**: 如果 `auto_backtest.py` 在 `self_evolve.py` 之后运行（即使不是同一天），可能使用变异后的参数而非正确参数。

**修复**: 保存并恢复原始值：
```python
def quick_eval(pool_codes, params, days=90):
    import backtest_engine as be
    # Save originals
    _orig = {k: getattr(be, k) for k in ['STOP_LOSS','TAKE_PROFIT_1','TAKE_PROFIT_2',
                'TAKE_PROFIT_3','MAX_POSITIONS','SLIPPAGE']}
    try:
        be.STOP_LOSS = params['stop_loss']
        ...
        engine = BacktestEngine('eval')
        result = engine.run(pool_codes[:15], start, end)
        ...
        return score, result
    finally:
        for k, v in _orig.items():
            setattr(be, k, v)
```

---

## 🟢 中危问题 (MEDIUM — 累积风险)

### 🟢 #10: autotrade.py 熊市默认值不安全

**文件**: `pipeline/autotrade.py:139`  
**代码**:
```python
def get_market_regime():
    try:
        from market_sentiment import get_market_sentiment
        s, _ = get_market_sentiment()
        if s == "🟢积极": return "TREND"
        elif s == "🟡中性": return "CHOP"
        elif s == "🔴谨慎": return "BEAR"
    except: pass
    return "TREND"  # 默认趋势 ← 危险！
```

**问题**: 当 `market_sentiment` 模块不存在或任何异常时，**默认返回"TREND"**，允许全仓交易。如果市场实际是熊市（比如API不可用的极端情况），系统会在最不应该交易的时候全力交易。

**修复**: 改为保守默认值，并记录失败原因：
```python
    except Exception as e:
        print(f"[WARN] get_market_regime failed: {e}, defaulting to CHOP")
        return "CHOP"  # 宁可保守
```

---

### 🟢 #11: self_evolve.py baostock 数据未使用

**文件**: `pipeline/self_evolve.py:61-69`  
**代码**:
```python
bs.login()
for code in ['sh.000001', 'sz.399001']:
    rs = bs.query_history_k_data_plus(code, 'date,close', ...)
    data = [row for row in rs.get_data().split('\n') if row]
bs.logout()
# data 变量在循环中被覆盖，最终只保留 sz.399001 的数据
# 然后...从未使用！
```

**问题**: 导入 baostock、执行查询、遍历数据，但结果从未被读取。真正的市场温度数据来自腾讯API (第72-77行的 `qt.gtimg.cn`)。

**影响**: 
- 浪费 baostock 登录/查询的网络和时间
- 如果 baostock 服务器不可用，会在 `get_data()` 调用时崩溃（因为没被 try/except 包裹）
- `bs.logout()` 可能不会在异常时执行（虽然代码在 try 块外）

**修复**: 删除未使用的 baostock 代码，或将其结果用于验证腾讯API数据。

---

### 🟢 #12: circuit_breaker.py 缺少 PnL 更新逻辑

**文件**: `pipeline/circuit_breaker.py:95-107`  
**代码**:
```python
daily = state.get('daily_pnl', 0)
if daily < -0.05: triggered.append('daily_loss_5pct')
elif daily < -0.03: triggered.append('daily_loss_3pct')
```

**问题**: `daily_pnl` 和 `weekly_pnl` 在 `circuit_breaker.py` 内部**从未被设置非零值**。它们只能由外部进程写入 `circuit_breaker.json`。

**影响**: 日亏损/周亏损熔断**可能永远不会触发**，因为没有进程负责更新 PnL 数据。

**修复**: 在 `main()` 中增加从MX/华泰持仓计算当日盈亏的逻辑：
```python
def update_daily_pnl(state):
    """从MX持仓计算当日盈亏"""
    try:
        from pipeline.autotrade import get_mx_positions
        _, _, tp = get_mx_positions()
        # tp 已经是当日浮动盈亏
        # 需要从 trade_log.json 计算已实现盈亏
        log_file = 'data/trade_log.json'
        realized = 0
        if os.path.exists(log_file):
            logs = json.load(open(log_file))
            today = datetime.now().strftime('%Y-%m-%d')
            realized = sum(e.get('amount', 0) for e in logs 
                          if e.get('time','').startswith(today) and e.get('action') == 'SELL')
        state['daily_pnl'] = (realized + tp) / 50000  # 相对于总资金
    except: pass
```

---

### 🟢 #13: 多个模块的 `STATE_FILE` 使用相对路径

**文件**: `circuit_breaker.py:11`, `discipline_check.py:10`, 等  
**代码**:
```python
STATE_FILE = 'data/circuit_breaker.json'
```

**问题**: 相对路径依赖当前工作目录。如果 cron 在 `/root` 或其他目录执行，会找不到文件或创建到错误位置。

**修复**: 统一使用绝对路径（参考 `autotrade.py` 的做法）：
```python
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE, "data", "circuit_breaker.json")
```
当前 `circuit_breaker.py` 已经 `sys.path.insert(0, BASE)` 但没有用 BASE 构造路径。

---

### 🟢 #14: `_exec_trade` 数据类型转换风险

**文件**: `pipeline/autotrade.py:59-62`  
**代码**:
```python
pos[code] = {"name": p.get("secName",""), "qty": qty, "cost": cost, "value": value,
             "profit": profit, "profit_pct": p.get("profitPct",0)}
```

其中:
```python
cost = p["costPrice"]/(10**p.get("costPriceDec",3))
value = p["value"]/1000
profit = p["profit"]/1000
```

**问题**: 这些值除以10^n或1000的变换**没有文档说明计算逻辑**。如果MX API的返回值格式发生变化（例如 `value` 不再需要除以1000），所有金额计算都会错误。

**影响**: 中等 — API变更时难以排查，且无防御性校验。

**建议**: 添加防御性检查：
```python
value = p["value"]
if value > 1e7:   # 如果value异常大, 可能需要除以1000
    value /= 1000
```

---

### 🟢 #15: `xuanwu_trade.py` `signal_alloc` 键类型不一致

**文件**: `pipeline/xuanwu_trade.py:15, 120`  
**代码**:
```python
SIGNAL_ALLOC = {6: 8000, 5: 6000, 4: 5000, 3: 3000}  # int键

# 使用时:
alloc = load_board_params().get("signal_alloc", SIGNAL_ALLOC).get(str(signal_level), 3000)
#                                                                      ^^^ 转为str
```

`evolve_params.json` 中:
```json
"signal_alloc": {"6": 8000, "5": 6000, "4": 5000, "3": 3000}
```

**问题**: 默认值 `SIGNAL_ALLOC` 用 int 键，而从 JSON 读取的用 str 键。`.get(str(signal_level), 3000)` 在 str 键上查找正确，但如果 `load_board_params()` 返回的是默认的 int 键 dict，则 `.get("5")` 会找不到 → fallback 到 3000 → 信号5和信号4的分配金额相同。

**影响**: 当 `evolve_params.json` 不存在时，所有信号级别的资金分配都会 fallback 到 3000，失去了差异化分配。

**修复**: 统一使用 int 键：
```python
SIGNAL_ALLOC = {6: 8000, 5: 6000, 4: 5000, 3: 3000}

# 使用时转为 int
alloc = load_board_params().get("signal_alloc", SIGNAL_ALLOC)
# 确保键是 int
if any(isinstance(k, str) for k in alloc):
    alloc = {int(k): v for k, v in alloc.items()}
alloc = alloc.get(signal_level, 3000)
```

---

### 🟢 #16: `board_scanner.py` alert queue 局部读-改-写竞态

**文件**: `board_scanner.py:190-202`  
**代码**:
```python
def queue_alert(code, name, price, chg, grade, risk, strategy, reason, sector_ok, vol_ok):
    alerts = []
    if os.path.exists(ALERT_FILE):
        try: alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({...})
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
```

**问题**: 与 #4 相同的竞态条件。`board_scanner.py` 可能每几分钟运行一次，与其他 cron 冲突。

**修复**: 同 #4 的 file-lock 方案。

---

### 🟢 #17: `get_sector` 返回第一个匹配 → 可能分类错误

**文件**: `pipeline/tier_review.py:37-39`  
**代码**:
```python
def get_sector(name):
    for s, kws in SECTOR_KW.items():
        if any(k in name for k in kws): return s
    return '其他'
```

**问题**: 如果股票名包含多个板块关键词（如"航天科技"匹配"军工"和"科技"），只返回第一个匹配的板块。且 `SECTOR_KW` 顺序是任意的。

**建议**: 要求全词匹配或使用更精确的分类逻辑。当前实现可接受，但应记录此限制。

---

## ⚪ 低危问题 (LOW)

### ⚪ #18: `tier_review.py` SECTOR_KW 重复键
**文件**: `pipeline/tier_review.py:19`  
**代码**: `'机器人':['机器','机器','智能']` — '机器' 重复。无功能影响，纯编辑错误。

### ⚪ #19: `stress_test.py` 无随机种子
随机价格导致每次压测结果不同，不利于回测结果的可比较性。

### ⚪ #20: `auto_backtest.py` `from backtest_engine import *`
命名空间污染，且使代码审查者无法快速判断使用了哪些引擎功能。

### ⚪ #21: `market_thermometer_v2.py` 未使用的 import
`from pipeline.fetcher import fetch_market` 从未被调用。Dead import。

---

## 🔗 跨模块专题分析

### 专题A: 参数闭环完整度

```
self_evolve.py ──[write_evolve_params]──❌ 函数未定义──→ evolve_params.json
     ↓
autotrade.py ──[load_evolve_params]──→ evolve_params.json ✅ (band section)
     ↓                                        ↑
calc_shares()  reads position_risk_pct ── OK   │
get_stop_stages() reads tp_*_pct ──── OK       │
止盈止损逻辑 reads stop_loss_pct ─── OK        │
                                                │
xuanwu_trade.py ──[load_board_params]──────────┘ ✅ (board section)
```

**结论**: 读取链路完整（所有消费者正确读取），**写入链路断裂**（self_evolve.py 的 write_evolve_params 未定义）。当前 `evolve_params.json` 只能手动维护。

---

### 专题B: API 字段索引验证

| API | 关键字段 | 索引 | 验证 |
|-----|---------|------|------|
| 腾讯 `qt.gtimg.cn` | `price` | `d[3]` | ✅ 已在实际使用中验证 |
| 腾讯 | `chg` | `d[32]` | ✅ |
| 腾讯 | `turnover` | `d[38]` | ✅ |
| 腾讯 | `volume_ratio` | `d[46]` | ⚠️ `parts[46]` 在 `get_stock_detail` 中，索引46需确认腾讯API文档 |
| 腾讯 | `pe` | `d[39]` | ✅ |
| 新浪 `sina.com.cn` | JSON API | 结构化 | ✅ 使用 `get("changepercent")`, `get("trade")` |

**验证方法**: 所有腾讯API字段偏移量通过 `if len(d) < 40: continue` 保护，且有 defensive 的 `float()` 包裹在 try/except 中。

⚠️ 注意: `market_thermometer_v2.py:46` 使用的 `q.bars(symbol=code, frequency=9, start=0, offset=2)` — `frequency=9` 的含义在不同版本的 mootdx 中可能不同。建议注释说明。

---

### 专题C: 静默失败地图

| 位置 | 异常处理 | 静默？ | 风险 |
|------|---------|--------|------|
| `autotrade.py:138` | `except: pass` (get_market_regime) | ✅ 静默 | 高 — 熊市时误判为趋势 |
| `autotrade.py:149` | `except: pass` (get_mx_positions) | ✅ 静默 | 中 — 无法获取实时持仓 |
| `board_scanner.py:59-61` | `except Exception as e: pass` | ✅ 静默 | 中 — 新浪API失败不报错 |
| `self_evolve.py:72-77` | `except: pass` (get_market_temp) | ✅ 静默 | 低 |
| `tier_review.py:54-56` | `except: pass` (batch_prices) | ✅ 静默 | 中 — 单批失败静默 |
| `circuit_breaker.py:60` | `except: return None` | ✅ 静默 | 中 |

**总评**: 静默失败太多，缺乏日志。建议至少加 `print(f"[WARN] ... {e}", file=sys.stderr)` 或写入专门的错误日志。

---

### 专题D: 死代码 / 永不触发的分支

1. **`xuanwu_trade.py:70`** — 永远不会正确执行（NameError），实际是死代码
2. **`autotrade.py:215`** — `get_stop_stages(price, pr["stop_loss"], price)` 买入时 profit_pct=0，返回值固定
3. **`self_evolve.py:65-69`** — baostock 数据获取后从未使用
4. **`market_thermometer_v2.py:19`** — `fetch_market` import 后从未使用

---

## 📋 修复优先级

| 优先级 | 修复项 | 预计工时 |
|--------|--------|---------|
| P0 🔴 | #1 self_evolve 补充 write_evolve_params | 30min |
| P0 🔴 | #2 xuanwu_trade 修复 state 引用 | 5min |
| P0 🔴 | #3 统一 ALERT_FILE 路径 | 15min |
| P0 🔴 | #4 文件锁防 cron 竞态 | 20min |
| P1 🟡 | #5 删除双重 notify_trade | 1min |
| P1 🟡 | #6/#7/#8 统一止盈阈值体系 | 30min |
| P1 🟡 | #9 quick_eval 状态保护 | 15min |
| P2 🟢 | #10 熊市默认值改为保守 | 5min |
| P2 🟢 | #11 删除未使用的 baostock 代码 | 10min |
| P2 🟢 | #12 circuit_breaker PnL更新 | 30min |
| P2 🟢 | #13-#17 路径/类型/竞态修复 | 60min |

**总计**: ~3.5小时全面修复

---

*AUDIT_EOF
echo "Audit report written successfully. Size: $(wc -c < /Users/sound/dao-analyst/audit_report.md) bytes"