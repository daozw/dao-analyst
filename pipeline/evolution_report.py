#!/usr/bin/env python3
"""进化报告 V1.0 — 每日5项数据: 亏损原因+策略偏差+无效规则+风险预警+冻结状态"""
import json, os, sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE, "data", "state")
REPORT_FILE = os.path.join(STATE_DIR, "evolution_report.json")

def generate_report(backtest_result=None):
    """生成5项进化报告"""
    report = {
        "generated_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "items": {}
    }
    
    # ── 1. 亏损原因 ──
    pnl_file = os.path.join(STATE_DIR, "daily_pnl.json")
    loss_reasons = []
    try:
        if os.path.exists(pnl_file):
            pnl_data = json.load(open(pnl_file))
            recent = sorted(pnl_data, key=lambda r: r.get("date", ""), reverse=True)[:10]
            
            loss_days = [r for r in recent if r.get("pnl", 0) < 0]
            total_loss = sum(r.get("pnl", 0) for r in loss_days)
            
            for r in loss_days[:5]:
                loss_reasons.append({
                    "date": r["date"],
                    "pnl": round(r["pnl"], 2),
                    "trades": r.get("trades", 0)
                })
            
            loss_reasons_summary = {
                "loss_days_10d": len(loss_days),
                "total_loss_10d": round(total_loss, 2),
                "details": loss_reasons,
                "primary_cause": "连亏超阈值" if len(loss_days) >= 3 else (
                    "单日大亏" if total_loss < -500 else "正常波动"
                )
            }
        else:
            loss_reasons_summary = {"status": "无数据", "details": []}
    except Exception as e:
        loss_reasons_summary = {"status": f"读取失败: {e}", "details": []}
    
    report["items"]["亏损原因"] = loss_reasons_summary
    
    # ── 2. 策略偏差 ──
    try:
        ep_file = os.path.join(BASE, "data", "evolve_params.json")
        if os.path.exists(ep_file):
            ep = json.load(open(ep_file))
            bp = ep.get("band", {})
            
            deviations = []
            # 检查关键参数是否偏离默认
            defaults = {"stop_loss_pct": -0.06, "tp_protect_pct": 0.02, 
                       "tp_half_pct": 0.08, "tp_clear_pct": 0.15, "position_risk_pct": 0.02}
            for key, default in defaults.items():
                current = bp.get(key, default)
                deviation_pct = abs(current - default) / abs(default) * 100 if default != 0 else 0
                if deviation_pct > 10:
                    deviations.append({
                        "param": key,
                        "current": current,
                        "default": default,
                        "deviation_pct": round(deviation_pct, 1)
                    })
            
            strategy_deviation = {
                "generation": ep.get("generation", 0),
                "last_updated": ep.get("updated", "未知"),
                "deviations": deviations,
                "has_deviation": len(deviations) > 0
            }
        else:
            strategy_deviation = {"status": "无进化参数"}
    except Exception as e:
        strategy_deviation = {"status": f"读取失败: {e}"}
    
    report["items"]["策略偏差"] = strategy_deviation
    
    # ── 3. 无效规则 ──
    try:
        invalid_rules = []
        
        # 检查止盈≤止损
        if bp.get("tp_protect_pct", 0.02) <= abs(bp.get("stop_loss_pct", -0.06)):
            invalid_rules.append("止盈≤止损: 保护性止盈未覆盖止损")
        
        # 检查进化天数
        if ep.get("updated"):
            try:
                days = (datetime.now() - datetime.strptime(ep["updated"][:10], "%Y-%m-%d")).days
                if days > 3:
                    invalid_rules.append(f"进化参数{days}天未更新, 可能过期")
            except: pass
        
        # 检查回测结果
        if backtest_result:
            if backtest_result.get("sharpe", 0) < -0.5:
                invalid_rules.append(f"夏普比率{backtest_result.get('sharpe')}< -0.5, 策略可能失效")
            if backtest_result.get("win_rate_pct", 50) < 30:
                invalid_rules.append(f"胜率{backtest_result.get('win_rate_pct')}%< 30%")
        
        invalid_rules_summary = {
            "count": len(invalid_rules),
            "rules": invalid_rules,
            "has_invalid": len(invalid_rules) > 0
        }
    except Exception as e:
        invalid_rules_summary = {"status": f"分析失败: {e}"}
    
    report["items"]["无效规则"] = invalid_rules_summary
    
    # ── 4. 风险预警 ──
    try:
        from pipeline.freeze_guard import get_recent_pnl, check_consecutive_losses
        
        records = get_recent_pnl(10)
        total_10d = sum(r.get("pnl", 0) for r in records)
        has_losses, n_loss, loss_reason = check_consecutive_losses()
        
        warnings = []
        if has_losses:
            warnings.append({"level": "🔴", "msg": f"连亏{n_loss}天 -> {loss_reason}"})
        if total_10d < -500:
            warnings.append({"level": "🔴", "msg": f"近10日总亏损 ¥{total_10d:,.0f}"})
        if total_10d < -200:
            warnings.append({"level": "🟡", "msg": f"近10日小幅亏损 ¥{total_10d:,.0f}"})
        
        # 熔断检查
        breaker_file = "/tmp/circuit_breaker_state.json"
        if os.path.exists(breaker_file):
            cb = json.load(open(breaker_file))
            if cb.get("triggered"):
                warnings.append({"level": "🔴", "msg": f"熔断已触发: 跌停{cb.get('limit_down',0)}只"})
        
        risk_warning = {
            "has_warnings": len(warnings) > 0,
            "warnings": warnings,
            "recent_10d_pnl": round(total_10d, 2),
            "consecutive_loss_days": n_loss
        }
    except Exception as e:
        risk_warning = {"status": f"分析失败: {e}"}
    
    report["items"]["风险预警"] = risk_warning
    
    # ── 5. 冻结状态 ──
    try:
        from pipeline.freeze_guard import get_freeze_status
        fs = get_freeze_status()
        freeze_status = {
            "is_frozen": fs.get("is_frozen", False),
            "reason": fs.get("reason", ""),
            "frozen_until": fs.get("frozen_until"),
            "frozen_at": fs.get("frozen_at"),
            "consecutive_loss_days": fs.get("consecutive_loss_days", 0)
        }
    except Exception as e:
        freeze_status = {"status": f"读取失败: {e}"}
    
    report["items"]["冻结状态"] = freeze_status
    
    # 保存报告
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(report, open(REPORT_FILE, "w"), ensure_ascii=False, indent=2)
    
    return report

def format_report(report):
    """格式化进化报告为文本"""
    lines = ["📊 进化报告 V1.0", f"📅 {report['date']}", "=" * 40, ""]
    
    for item_name, item_data in report.get("items", {}).items():
        lines.append(f"## {item_name}")
        
        if item_name == "亏损原因":
            ld = item_data.get("loss_days_10d", 0)
            tl = item_data.get("total_loss_10d", 0)
            pc = item_data.get("primary_cause", "未知")
            lines.append(f"  近10日亏损天数: {ld}天 | 总亏损: ¥{tl:,.0f}")
            lines.append(f"  主要原因: {pc}")
            for d in item_data.get("details", [])[:3]:
                lines.append(f"    {d.get('date','')} ¥{d.get('pnl',0):+,.0f} ({d.get('trades',0)}笔)")
        
        elif item_name == "策略偏差":
            if item_data.get("has_deviation"):
                for d in item_data.get("deviations", []):
                    lines.append(f"  ⚠️ {d['param']}: {d['current']} vs 默认{d['default']} (偏差{d['deviation_pct']:.0f}%)")
            else:
                lines.append(f"  ✅ 无偏差 (第{item_data.get('generation',0)}代)")
        
        elif item_name == "无效规则":
            if item_data.get("has_invalid"):
                for r in item_data.get("rules", []):
                    lines.append(f"  ❌ {r}")
            else:
                lines.append(f"  ✅ 规则有效")
        
        elif item_name == "风险预警":
            if item_data.get("has_warnings"):
                for w in item_data.get("warnings", []):
                    lines.append(f"  {w['level']} {w['msg']}")
            else:
                lines.append(f"  🟢 无风险预警")
        
        elif item_name == "冻结状态":
            if item_data.get("is_frozen"):
                lines.append(f"  🔴 已冻结: {item_data.get('reason','')}")
                lines.append(f"  冻结至: {item_data.get('frozen_until','')}")
            else:
                lines.append(f"  🟢 正常运行 (连亏{item_data.get('consecutive_loss_days',0)}天)")
        
        lines.append("")
    
    lines.append("=" * 40)
    lines.append("以上为自动生成  仅供参考")
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "format":
        if os.path.exists(REPORT_FILE):
            report = json.load(open(REPORT_FILE))
            print(format_report(report))
        else:
            print("📊 无进化报告数据")
    else:
        # Generate and print
        bt_result = None
        # Try to load backtest result
        bt_file = os.path.join(STATE_DIR, "backtest_latest.json")
        if os.path.exists(bt_file):
            try:
                bt_result = json.load(open(bt_file))
            except: pass
        
        report = generate_report(bt_result)
        print(format_report(report))
