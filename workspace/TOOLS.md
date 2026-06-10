# DAO分析师 快速命令

## 盘前全流程（推荐）
```bash
cd ~/dao-analyst && .venv/bin/python3 morning_routine.py          # 模拟
cd ~/dao-analyst && .venv/bin/python3 morning_routine.py --real   # 实盘
```

## 单独操作
```bash
# 清仓
cd ~/dao-analyst && .venv/bin/python3 pipeline/autotrade.py clear --real

# 自动交易
cd ~/dao-analyst && .venv/bin/python3 pipeline/autotrade.py --real

# 查询持仓
cd ~/dao-analyst && .venv/bin/python3 -c "from pipeline.autotrade import get_mx_positions; p,t,v=get_mx_positions(); print(f'持仓{len(p)}只 ¥{t:,.0f}')"

# 通知队列
cd ~/dao-analyst && .venv/bin/python3 pipeline/trade_notify.py pending
cd ~/dao-analyst && .venv/bin/python3 pipeline/trade_notify.py mark-sent N
```

## 华泰打板（独立系统）
```bash
cd ~/dao-analyst && .venv/bin/python3 pipeline/xuanwu_trade.py clear --real
echo '[{"code":"600439","name":"瑞贝卡","signal":4}]' | .venv/bin/python3 pipeline/xuanwu_trade.py trade --real
```

## 扫描
```bash
cd ~/quant-research/daily_stock_analysis && source .venv/bin/activate
python3 ~/.openclaw-autoclaw/workspace/market_scanner.py
```

## 系统架构
- 系统A: autotrade.py → MX模拟账户，波段池，状态文件 `autotrade_daily_state.json`
- 系统B: xuanwu_trade.py → 华泰实盘，打板策略，状态文件 `xuanwu_daily_state.json`
- 两个系统独立，互不干扰

## 信号捕捉
```bash
cd ~/dao-analyst && .venv/bin/python3 -c "
from signal_catcher import recent
sigs = recent(10)
for s in sigs: print(s["msg"])"
```
