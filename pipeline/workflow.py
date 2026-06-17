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
    """政策+新闻扫描: 实时财经新闻 + 政策解读 + 板块资金"""
    try:
        from pipeline.news_brief import generate_full_brief
        return generate_full_brief()
    except Exception as e:
        # 降级: 用旧版简单扫描
        try:
            from pipeline.fetcher import fetch_market
            md = fetch_market()
            sector = md.get("sectors", [])[:5]
            lines = ["📰 今日政策/行业动态 (降级模式)"]
            if sector:
                for s in sector:
                    lines.append(f"  {'🔥' if s.get('hot',False) else '📌'} {s.get('name','?')} {s.get('chg',''):+.1f}%")
            else:
                lines.append("  暂无重大政策")
            return "\n".join(lines)
        except Exception as e2:
            return f"政策扫描异常: {e} | 降级也失败: {e2}"

def daily_backtest():
    """每日全市场回测 (周末运行上周数据)"""
    import sys
    sys.path.insert(0, '/Users/sound/.openclaw-autoclaw/workspace')
    from backtest_engine import FalconBacktest, StrategyParams
    from datetime import datetime, timedelta
    
    engine = FalconBacktest()
    params = StrategyParams()
    
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    
    # 如果是周一，回测上周；非交易时段用昨天数据
    if now.weekday() == 0:
        start = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        end = (now - timedelta(days=3)).strftime('%Y-%m-%d')
    elif now.hour < 9 or (now.weekday() >= 5):
        # 盘前或周末: 用最近交易日(昨天)数据
        backdate = now - timedelta(days=1)
        if backdate.weekday() >= 5:
            backdate = backdate - timedelta(days=backdate.weekday()-4)
        start = backdate.strftime('%Y-%m-%d')
        end = start
    else:
        start = today
        end = today
    
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


def auto_trade(dry_run="--real" not in sys.argv):
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
def board_warn():
    """打板预警 V2 — akshare版, 抓+7%~+9.5% 即将封板标的"""
    from collections import defaultdict
    import numpy as np
    from datetime import datetime
    import akshare as ak
    import pandas as pd

    try:
        df = ak.stock_zh_a_spot()
    except Exception as e:
        return f'⚡ 打板预警 {datetime.now().strftime("%m-%d %H:%M")}\n  akshare获取失败: {e}'

    codes = df['代码'].astype(str)
    mask = (codes.str.match(r'^sh60[0-35-9]\d{3}$') |
            codes.str.match(r'^sz00[0-3]\d{3}$'))
    df = df[mask].copy()

    approaching = []
    for _, row in df.iterrows():
        chg = row.get('涨跌幅', 0)
        if pd.isna(chg) or not (7.0 <= chg < 9.5):
            continue
        
        code = str(row['代码'])
        pure_code = code[2:] if len(code) >= 8 else code
        name = row.get('名称', '')
        price = row.get('最新价', 0)
        high = row.get('最高', price)
        low = row.get('最低', price)
        prev_close = row.get('昨收', price)
        
        h, l, cl = float(high), float(low), float(price)
        seal_pct = (cl - l) / (h - l) * 100 if h > l else 100
        vr = 1.0
        speed = chg
        
        limit_price = round(float(prev_close) * 1.099 + 0.007, 2)
        dist_pct = round((limit_price - cl) / cl * 100, 1)
        score = (chg - 7) * 8 + min(vr * 3, 15) + min(seal_pct * 0.1, 10) + min(speed * 5, 15)
        
        approaching.append({
            'code': pure_code, 'name': name,
            'price': round(cl, 2), 'chg': round(chg, 1),
            'vr': round(vr, 1), 'seal': round(seal_pct, 1),
            'speed': round(speed, 1), 'dist': dist_pct,
            'limit': limit_price, 'score': round(score, 1)
        })

    approaching.sort(key=lambda x: -x['score'])
    now = datetime.now().strftime('%m-%d %H:%M')
    if not approaching:
        return f'⚡ 打板预警 {now}\n  暂无+7%~+9.5%逼近标的'

    lines = [f'⚡ 打板预警 {now} | {len(approaching)}只逼近']
    near = [s for s in approaching if s['chg'] >= 9]
    close = [s for s in approaching if s['chg'] < 9]
    if near:
        lines.append(f'\n🔴 极近封板(>=9%):')
        for s in near[:5]:
            lines.append(f'  {s["code"]} {s["name"]:<8} ¥{s["price"]:.2f} +{s["chg"]}% '
                       f'量{s["vr"]}x 距涨停{s["dist"]}% [{s["score"]}分]')
    if close:
        lines.append(f'\n🟠 接近封板(7-9%):')
        for s in close[:5]:
            lines.append(f'  {s["code"]} {s["name"]:<8} ¥{s["price"]:.2f} +{s["chg"]}% '
                       f'量{s["vr"]}x 距涨停{s["dist"]}% [{s["score"]}分]')
    lines.append(f'\n💡 评分=涨幅+量能+趋势+速度 | >=9%量>3x优先')
    return '\n'.join(lines)

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
        print(auto_trade(dry_run="--real" not in sys.argv))
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
    elif cmd == "board_warn":
        print(board_warn())
    elif cmd == "news":
        print(policy_scan())
    else:
        print(f"未知命令: {cmd}")
        print("可用: policy board board_warn backtest settle anomaly autotrade buylist governor github audit govdelist news")
