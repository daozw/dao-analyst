#!/usr/bin/env python3
"""压力测试 — 模拟极端行情下策略表现"""
import json, os, sys, random
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STRESS_LOG = DATA / "stress_log.json"

SCENARIOS = {
    "flash_crash": {"name": "闪崩", "day_change": -0.08, "volatility": 3.0, "duration_days": 1},
    "bear_week": {"name": "熊市周", "day_change": -0.03, "volatility": 2.5, "duration_days": 5},
    "bull_rush": {"name": "疯牛", "day_change": 0.05, "volatility": 2.0, "duration_days": 3},
    "sideways": {"name": "横盘震荡", "day_change": 0.0, "volatility": 1.5, "duration_days": 10},
    "gap_crash": {"name": "跳空暴跌", "day_change": -0.10, "volatility": 4.0, "duration_days": 2},
}

def load_config():
    """加载交易配置"""
    config_paths = [
        ROOT / "data" / "trade_config.json",
        Path.home() / "data" / "trade_config.json",
    ]
    for p in config_paths:
        if p.exists():
            with open(p) as f:
                return json.load(f)
    return {"position_cap": 20000, "stop_loss_pct": 0.05, "take_profit_pct": 0.08}

def simulate_scenario(config, scenario):
    """模拟单个场景"""
    capital = config.get("position_cap", 20000)
    position = 0
    cash = capital
    trades = []
    
    for day in range(scenario["duration_days"]):
        # 模拟当日涨跌（带波动）
        base_change = scenario["day_change"]
        noise = random.gauss(0, scenario["volatility"] * 0.01)
        day_return = base_change + noise
        
        # 止损检查
        if position > 0:
            position_value = position * (1 + day_return)
            loss_pct = (position_value - position) / position
            if loss_pct < -config.get("stop_loss_pct", 0.05):
                trades.append({"day": day, "action": "止损", "return": loss_pct})
                cash += position_value
                position = 0
                continue
            # 止盈检查
            if loss_pct > config.get("take_profit_pct", 0.08):
                trades.append({"day": day, "action": "止盈", "return": loss_pct})
                cash += position_value
                position = 0
                continue
        
        # 建仓（如果空仓且不是暴跌日）
        if position == 0 and day_return > -0.05:
            position = cash * 0.5
            cash -= position
            trades.append({"day": day, "action": "建仓", "amount": position})
    
    # 清仓
    if position > 0:
        final_value = position * (1 + scenario["day_change"] * 0.5)
        cash += final_value
        position = 0
    
    total_return = (cash - capital) / capital
    return {
        "scenario": scenario["name"],
        "capital": capital,
        "final_cash": round(cash, 2),
        "return_pct": round(total_return * 100, 2),
        "trades": len(trades),
        "max_drawdown": round(min([t.get("return", 0) for t in trades], default=0) * 100, 2)
    }

def run_stress_test():
    config = load_config()
    results = []
    
    print(f"🧪 压力测试 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   初始资金: ¥{config.get('position_cap', 20000):,}")
    print(f"   止损: {config.get('stop_loss_pct', 0.05):.0%} | 止盈: {config.get('take_profit_pct', 0.08):.0%}")
    print()
    
    for sid, scenario in SCENARIOS.items():
        result = simulate_scenario(config, scenario)
        results.append(result)
        emoji = "🔴" if result["return_pct"] < -5 else "🟡" if result["return_pct"] < 0 else "🟢"
        print(f"  {emoji} {result['scenario']:6s} | 收益{result['return_pct']:+.1f}% | "
              f"回撤{result['max_drawdown']:.1f}% | 交易{result['trades']}笔")
    
    # 保存结果
    DATA.mkdir(parents=True, exist_ok=True)
    log = []
    if STRESS_LOG.exists():
        with open(STRESS_LOG) as f:
            log = json.load(f)
    log.append({"time": datetime.now().isoformat(), "results": results})
    with open(STRESS_LOG, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)
    
    # 综合评分
    avg_return = sum(r["return_pct"] for r in results) / len(results)
    worst = min(results, key=lambda r: r["return_pct"])
    print(f"\n  📊 综合: 均值{avg_return:+.1f}% | 最差'{worst['scenario']}' {worst['return_pct']:+.1f}%")
    print(f"  💾 结果已保存: {STRESS_LOG}")
    
    return results

if __name__ == "__main__":
    run_stress_test()
