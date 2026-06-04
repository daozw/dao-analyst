# DAO分析师 V3.1
"""工作流增强: 日结算+异常检测+买卖清单"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WATCHLIST = os.path.expanduser("~/dao-analyst/data/watchlist.json")

def daily_settlement():
    """盘后日结算: 持仓盈亏+对比大盘"""
    from pipeline.fetcher import fetch
    
    # 读取波段池+首板池
    wl = json.load(open(WATCHLIST)) if os.path.exists(WATCHLIST) else {"groups":{}}
    band = wl.get("groups",{}).get("band",{}).get("stocks",[])
    board = wl.get("groups",{}).get("board",{}).get("stocks",[])
    all_stocks = band + board
    
    if not all_stocks: return "无持仓数据"
    
    lines = ["📊 关注池表现"]
    up_count = 0; down_count = 0
    for s in all_stocks[:6]:
        d = fetch(s["code"], use_cache=False)
        if "error" in d: continue
        chg = d["chg"]
        arrow = "🔴" if chg > 0 else "🟢" if chg < 0 else "➖"
        lines.append(f"  {arrow} {d['name']:<6} ¥{d['price']:.2f} {chg:+.1f}%")
        if chg > 0: up_count += 1
        elif chg < 0: down_count += 1
    
    lines.append(f"\n  📈 {up_count}涨 📉 {down_count}跌")
    
    # 大盘对比
    try:
        from pipeline.fetcher import fetch_market
        md = fetch_market()
        idx = md.get("index",{})
        idx_chg = idx.get("chg",0)
        lines.append(f"  🆚 上证 {idx_chg:+.2f}%")
        outperform = up_count - down_count
        lines.append(f"  {'✅ 跑赢大盘' if outperform > 0 else '⚠️ 弱于大盘'}")
    except: pass
    
    return "\n".join(lines)

def check_anomalies(codes=None):
    """盘中全市场异动检测"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from market_scanner import MarketScanner
    s = MarketScanner()
    results = s.scan(timeout=45)
    
    up = [r for r in results if r['chg'] > 0][:5]
    down = [r for r in results if r['chg'] < 0][:5]
    
    alerts = []
    for r in up:
        alerts.append(f"🟢 {r['code']} {r['name']} ¥{r['price']:.2f} +{r['chg']:.1f}%")
    for r in down:
        alerts.append(f"🔴 {r['code']} {r['name']} ¥{r['price']:.2f} {r['chg']:.1f}%")
    
    return alerts if alerts else None

def generate_buy_list():
    """盘前买卖清单"""
    wl = json.load(open(WATCHLIST)) if os.path.exists(WATCHLIST) else {"groups":{}}
    band = wl.get("groups",{}).get("band",{}).get("stocks",[])
    board = wl.get("groups",{}).get("board",{}).get("stocks",[])
    
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    
    lines = ["🎯 今日操作清单"]
    
    # 波段池
    for s in band:
        d = fetch(s["code"], use_cache=False)
        if "error" in d: continue
        a = analyze(d)
        pr = a["prices"]
        sig = f"{a['g']}/{a['total']}信号"
        
        chg = d["chg"]
        action = "✅ 可建仓" if a["g"] >= 3 else "⏳ 等信号" if a["g"] >= 2 else "❌ 观望"
        
        lines.append(f"  {action} {d['name']:<6} ¥{d['price']:.2f} {chg:+.1f}% {sig}")
        lines.append(f"        建仓¥{pr['first_entry']:.2f} 止损¥{pr['stop_loss']:.2f} 止盈¥{pr['take_profit_1']:.2f}")
    
    # 首板池
    if board:
        lines.append(f"\n  👀 涨停观察:")
        for s in board:
            d = fetch(s["code"], use_cache=False)
            if "error" in d: continue
            chg = d["chg"]
            lines.append(f"  {'⚠️ 高开谨慎' if chg > 3 else '✅ 平开可观察' if chg > -2 else '❌ 低开放弃'} {d['name']}")
    
    return "\n".join(lines)


def policy_scan():
    """政策扫描: 检查政策/行业动态"""
    try:
        from pipeline.fetcher import fetch_market
        md = fetch_market()
        sector = md.get("sectors", [])[:5]
        lines = ["📰 今日政策/行业动态"]
        if sector:
            for s in sector:
                lines.append(f"  {'🔥' if s.get('hot',False) else '📌'} {s.get('name','?')} {s.get('chg',''):+.1f}%")
        else:
            lines.append("  暂无重大政策")
        return "\n".join(lines)
    except Exception as e:
        return f"政策扫描异常: {e}"

def daily_backtest():
    """每日全市场回测 (周末运行上周数据)"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from backtest_engine import FalconBacktest, StrategyParams
    from datetime import datetime, timedelta
    
    engine = FalconBacktest()
    params = StrategyParams()
    
    today = datetime.now()
    # 如果是周一，回测上周
    if today.weekday() == 0:
        start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        end = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    else:
        start = today.strftime('%Y-%m-%d')
        end = today.strftime('%Y-%m-%d')
    
    result = engine.run(params, start=start, end=end, market='mainboard', verbose=False)
    engine.save_result(result)
    
    lines = [f"🦅 猎鹰 {params.version} 回测 {result.period}"]
    lines.append(f"  {result.total_stocks}只→{result.signals}信号 {result.trades}笔")
    lines.append(f"  胜率{result.win_rate}% 盈亏{result.total_pnl:+.0f} PF{result.profit_factor}")
    if result.trades_detail:
        lines.append(f"  🏆 {result.trades_detail[0]['code']} {result.trades_detail[0]['name']} {result.trades_detail[0]['pnl']:+.0f}")
    return '\n'.join(lines)



def governor_check():
    """全栈治理健康检查"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from governor import Governor
    g = Governor()
    return g.health_check()

def governor_delist_check():
    """退市风险扫描"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from governor import Governor
    g = Governor()
    return g.check_delist()


def auto_trade_exec(dry_run="--real" not in sys.argv):
    """自动交易执行 (被 Cron 调用, 默认模拟)"""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from pipeline.autotrade import auto_trade
    text, _ = auto_trade(dry_run=dry_run)
    return text

def governor_audit():
    """全栈审计 (升级+冲突+冗余+性能+安全)"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from governor_plus import DAOGovernorPlus
    g = DAOGovernorPlus()
    return g.report()

def github_sync():
    """GitHub 仓库同步"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from github_governor import GitHubGovernor
    g = GitHubGovernor()
    return g.sync_report()

def board_scan():
    """打板扫描"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from strategy_board import FlameBoardStrategy
    return FlameBoardStrategy().report()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "settle"
    
    if cmd == "policy":
        print(policy_scan())
    elif cmd == "board":
        print(board_scan())
    elif cmd == "backtest":
        print(daily_backtest())
    elif cmd == "settle":
        print(daily_settlement())
    elif cmd == "anomaly":
        wl = json.load(open(WATCHLIST)) if os.path.exists(WATCHLIST) else {}
        all_codes = []
        for g in ["band","board","watch"]:
            for s in wl.get("groups",{}).get(g,{}).get("stocks",[]):
                all_codes.append(s["code"])
        alerts = check_anomalies(all_codes)
        if alerts:
            for a in alerts: print(a)
        else:
            print("✅ 无异常")
    elif cmd == "autotrade":
        print(auto_trade_exec(dry_run="--real" not in sys.argv))
    elif cmd == "buylist":
        print(generate_buy_list())

    elif cmd == "governor":
        print(governor_check())
    elif cmd == "github":
        print(github_sync())
    elif cmd == "audit":
        print(governor_audit())
    elif cmd == "govdelist":
        print(governor_delist_check())
