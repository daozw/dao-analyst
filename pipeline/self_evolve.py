#!/usr/bin/env python3
"""自我进化管道 — 基于回测结果自动优化策略参数"""
import json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVOLVE_LOG = DATA / "evolve_log.json"

def load_evolve_log():
    if EVOLVE_LOG.exists():
        with open(EVOLVE_LOG) as f:
            return json.load(f)
    return []

def save_evolve_log(log):
    DATA.mkdir(parents=True, exist_ok=True)
    with open(EVOLVE_LOG, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)

def sync_evolve_params(changes, metrics):
    """同步写入 evolve_params.json（daily_health 期望格式）"""
    ep_path = DATA / "evolve_params.json"
    params = {
        "generation": 1,
        "updated": datetime.now().isoformat(),
        "band": {
            "tp_clear_pct": 15.0,
            "stop_loss_pct": 5.0,
            "atr_multiplier": 2.5,
            "position_cap": 20000,
        },
        "strategy": "猎鹰v2.6T",
        "metrics": {
            "win_rate": round(metrics.get("win_rate", 0) * 100, 1),
            "sharpe": round(metrics.get("sharpe", 0), 2),
            "max_dd": round(metrics.get("max_drawdown", 0) * 100, 1),
        },
        "last_changes": changes,
    }
    with open(ep_path, 'w') as f:
        json.dump(params, f, ensure_ascii=False, indent=2, default=str)

def check_backtest_results():
    """读取最近回测结果"""
    results = []
    bt_dir = ROOT / "backtest"
    if bt_dir.exists():
        for f in sorted(bt_dir.glob("*.json"), reverse=True)[:5]:
            try:
                with open(f) as fh:
                    results.append(json.load(fh))
            except:
                pass
    return results

def evolve():
    """进化主逻辑：基于回测指标微调参数"""
    log = load_evolve_log()
    now = datetime.now().isoformat()
    
    results = check_backtest_results()
    if not results:
        entry = {
            "time": now,
            "action": "skip",
            "reason": "无回测数据",
            "params_changed": {}
        }
        log.append(entry)
        save_evolve_log(log)
        sync_evolve_params({}, {})
        print("⏭️ 无回测数据，跳过进化")
        return

    latest = results[0]
    metrics = latest.get("metrics", {})
    win_rate = metrics.get("win_rate", 0)
    sharpe = metrics.get("sharpe", 0)
    max_dd = metrics.get("max_drawdown", 0)
    
    changes = {}
    
    if win_rate < 0.4:
        changes["min_gain_pct"] = "+0.5%"
        changes["reason"] = f"胜率{win_rate:.1%}<40%，收紧涨幅门槛"
    elif abs(max_dd) > 0.1:
        changes["position_cap"] = "-10%"
        changes["reason"] = f"最大回撤{max_dd:.1%}>10%，降低仓位上限"
    elif sharpe > 1.5 and win_rate > 0.5:
        changes["status"] = "stable"
        changes["reason"] = f"夏普{sharpe:.2f} 胜率{win_rate:.1%}，参数稳定"
    
    entry = {
        "time": now,
        "action": "evolved" if changes else "stable",
        "metrics_snapshot": {"win_rate": win_rate, "sharpe": sharpe, "max_dd": max_dd},
        "params_changed": changes
    }
    log.append(entry)
    save_evolve_log(log)
    sync_evolve_params(changes, metrics)
    
    status = "🔄 已进化" if changes.get("reason") else "✅ 参数稳定"
    print(f"{status} | 胜率{win_rate:.1%} 夏普{sharpe:.2f} 回撤{max_dd:.1%}")
    if changes:
        print(f"  调整: {changes}")

if __name__ == "__main__":
    evolve()
