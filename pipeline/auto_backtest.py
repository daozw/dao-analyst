#!/usr/bin/env python3
"""自动回测 — 每日收盘后跑，周末跑全量"""
import sys,fcntl,os,json
from datetime import datetime, timedelta
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest_engine import *
from pipeline.evolution_report import generate_report, format_report
ALERT_FILE='/tmp/dao_trade_alerts.json'

def main(weekend=False):
    # 加载池
    wl=json.load(open('data/watchlist.json'))
    all_codes=[]
    for gn,g in wl.get('groups',{}).items():
        if gn=='exclude': continue
        for s in g.get('stocks',[]):
            if not s['code'].startswith(('300','688','8')):
                all_codes.append(s['code'])
    pool=list(dict.fromkeys(all_codes))[:20]
    
    today=datetime.now()
    if weekend:
        # 周末全量回测
        start=(today-timedelta(days=365*2)).strftime('%Y-%m-%d')
        end=today.strftime('%Y-%m-%d')
        label='📊 周末全量'
    else:
        # 平日快速回测(近90日)
        start=(today-timedelta(days=90)).strftime('%Y-%m-%d')
        end=today.strftime('%Y-%m-%d')
        label='📊 日度回测'
    
    engine=FalconBacktest()
    from backtest_engine import StrategyParams
    params = StrategyParams()
    r=engine.run(params, codes=pool, start=start, end=end)
    if not r or hasattr(r, 'error'): return
    
    lines=[]
    lines.append(f"{label} | {datetime.now().strftime('%m/%d %H:%M')}")
    lines.append(f"🤖 DAO分析师 V3.3  |  {len(pool)}只·{start[:7]}→{end[:7]}")
    lines.append("")
    lines.append(f"交易: {r.trades}笔 | 胜率: {r.win_rate:.0%}")
    lines.append(f"盈亏: ¥{r.total_pnl:+,.0f} | PF: {r.profit_factor:.2f}")
    lines.append(f"夏普: {r.sharpe:.2f} | 信号: {r.signals} | 最大赢: ¥{r.max_win:,.0f} | 最大亏: ¥{r.max_loss:,.0f}")
    lines.append(f"胜场: {r.wins} | 负场: {r.losses} | 均赢: ¥{r.avg_win:,.0f} | 均亏: ¥{r.avg_loss:,.0f}")
    
    # 判断 + 失效检测
    if r.sharpe>0.5 and r.total_return_pct>0:
        verdict='✅ 策略有效,继续执行'
    elif r.sharpe>-0.5:
        verdict='🟡 持平,观察参数'
    else:
        verdict='⚠️ 不佳,等待进化优化'
    
    # 🧬 策略失效标记: 回测偏差>20% → 标记策略失效
    if r.get('total_return_pct', 0) < -20 or r.get('max_drawdown_pct', 100) > 30:
        verdict = '🔴 策略失效(偏差>20%)'
        # 保存失效标记
        import json as _json2
        _json2.dump({"invalidated": True, "reason": verdict, "time": datetime.now().isoformat()},
                   open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    "data", "state", "strategy_invalid.json"), "w"))
    
    lines.append(f"结论: {verdict}")
    
    # 保存回测结果供进化报告使用
    try:
        import json as _json_bt
        bt_save = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "state", "backtest_latest.json")
        _json_bt.dump(r, open(bt_save, "w"), ensure_ascii=False, indent=2)
    except: pass
    
    # 🧬 生成5项进化报告
    try:
        evo_report = generate_report(r)
        evo_text = format_report(evo_report)
        lines.append("")
        lines.append("─"*20)
        lines.append(evo_text)
    except Exception as e:
        lines.append(f"")
        lines.append(f"⚠️ 进化报告生成失败: {e}")
    lines.append("")
    lines.append("─"*20)
    lines.append("以上仅供参考  股市有风险")
    
    report='\n'.join(lines)
    print(report)
    
    # 推送
    try:
        al=[]
        if os.path.exists(ALERT_FILE):
            try: al=json.load(open(ALERT_FILE))
            except: pass
        al.append({'time':datetime.now().strftime('%H:%M'),'action':'AUTO_BACKTEST',
                   'message':report,'sent':False})
        with open(ALERT_FILE,'w') as f: json.dump(al,f,ensure_ascii=False,indent=2)
    except: pass

if __name__=="__main__":
    import sys
    weekend='--weekend' in sys.argv
    main(weekend)
