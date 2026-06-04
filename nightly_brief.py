#!/usr/bin/env python3
"""
深夜情报站 V1.0 — 每日23:00 A股热度全景扫描
维度: 涨幅TOP榜 / 成交热度 / 龙虎榜 / 板块轮动 / 新闻热度 / 北向资金
"""
import subprocess, os, csv, glob, json
from datetime import datetime, date
from collections import defaultdict
import urllib.request, ssl
ssl._create_default_https_context = ssl._create_unverified_context

MX_KEY = os.environ.get("MX_APIKEY", "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8")
ENV = {**os.environ, "MX_APIKEY": MX_KEY}
XG = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py")
SEARCH = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-search/mx_search.py")
DATA = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-data/mx_data.py")
OUTPUT = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output")

def run_mx(script, query, timeout=25):
    r = subprocess.run(["python3", script, query], capture_output=True, text=True, env=ENV, timeout=timeout)
    return r.returncode == 0

def latest_csv(pattern):
    files = sorted(glob.glob(f"{OUTPUT}/*{pattern}*.csv"), key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0] if files else None

def parse_csv(path, code_col, name_col, chg_col, extra_cols=None):
    """通用CSV解析"""
    results = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                code = row.get(code_col, "").replace(".SZ","").replace(".SH","")
                name = row.get(name_col, "")
                chg = float(row.get(chg_col, "0").replace("%", ""))
                
                item = {"code": code, "name": name, "chg": chg}
                if extra_cols:
                    for k, col in extra_cols.items():
                        item[k] = row.get(col, "")
                results.append(item)
            except:
                continue
    return results

# ═══════════════════════════════════
# 维度1: 今日涨幅TOP榜 (涨停板热度)
# ═══════════════════════════════════
def scan_limit_up_hot():
    """涨停板 + 涨幅榜"""
    print("🔴 维度1: 涨停/涨幅热度...")
    
    # 涨停股
    run_mx(XG, "主板 今日涨停 换手率大于2% 非ST 按涨跌幅降序")
    f = latest_csv("涨停")
    limit_ups = []
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    code = row.get("代码","")
                    name = row.get("名称","")
                    chg = float(row.get("涨跌幅(%)", "0").replace("%",""))
                    turnover = float(row.get("换手率(%)", "0"))
                    mkt = row.get("流通市值(元)", "0")
                    mkt_v = float(mkt.replace("亿","")) if "亿" in mkt else 0
                    if chg >= 9.8 and mkt_v > 20:
                        limit_ups.append({"code": code, "name": name, "chg": chg, "turnover": turnover, "mkt": mkt_v})
                except: pass
    
    # 涨幅TOP20非涨停
    run_mx(XG, "主板 今日涨幅5%到9.5% 换手率大于2% 非ST 按涨跌幅降序")
    f2 = latest_csv("涨幅5%到9.5%")
    near_limit = []
    if f2:
        near_limit = parse_csv(f2, "代码", "名称", "涨跌幅(%)")
        near_limit = near_limit[:15]
    
    return {
        "limit_up_count": len(limit_ups),
        "top_limit_ups": limit_ups[:8],
        "near_limit": near_limit
    }

# ═══════════════════════════════════
# 维度2: 成交热度 — 天量换手
# ═══════════════════════════════════
def scan_volume_heat():
    """放量异动 — 成交热度"""
    print("🟠 维度2: 成交热度...")
    
    run_mx(XG, "主板 换手率大于15% 今日涨幅大于0 非ST 按换手率降序")
    f = latest_csv("换手率大于15%")
    hot_volume = []
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    code = row.get("代码","")
                    name = row.get("名称","")
                    turnover = float(row.get("换手率(%)","0"))
                    chg = float(row.get("涨跌幅(%)","0").replace("%",""))
                    vol_r = float(row.get("量比","0")) if row.get("量比","0").replace("-","").strip() else 0
                    price = float(row.get("最新价(元)","0"))
                    if turnover > 15 and price < 100:
                        hot_volume.append({"code": code, "name": name, "turnover": turnover, "chg": chg, "vol_ratio": vol_r})
                except: pass
    
    hot_volume.sort(key=lambda x: x["turnover"], reverse=True)
    return hot_volume[:10]

# ═══════════════════════════════════
# 维度3: 板块轮动热度
# ═══════════════════════════════════
def scan_sector_heat():
    """板块涨幅TOP"""
    print("🟡 维度3: 板块热度...")
    
    run_mx(XG, "今日 东财行业分类二级 涨幅大于2% 按涨跌幅降序")
    f = latest_csv("涨幅大于2%")
    sectors = {}
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    sector = row.get("东财行业分类二级","")
                    if not sector: continue
                    chg = float(row.get("涨跌幅(%)","0").replace("%",""))
                    if sector not in sectors:
                        sectors[sector] = {"count": 0, "total_chg": 0, "stocks": []}
                    sectors[sector]["count"] += 1
                    sectors[sector]["total_chg"] += chg
                    sectors[sector]["stocks"].append(row.get("名称",""))
                except: pass
    
    ranked = []
    for name, d in sectors.items():
        if d["count"] >= 2:
            ranked.append((name, d["count"], round(d["total_chg"]/d["count"], 1), d["stocks"][:3]))
    ranked.sort(key=lambda x: x[2], reverse=True)
    
    # 判断今日主线
    if ranked:
        top_avg = sum(r[2] for r in ranked[:3]) / min(3, len(ranked))
        if top_avg > 5:
            theme = f"🔥 强主线: {ranked[0][0]}(均{ranked[0][2]:.1f}%)"
        elif top_avg > 3:
            theme = f"📈 热点明确: {ranked[0][0]} 领涨"
        else:
            theme = "📊 轮动分化"
    else:
        theme = "❄️ 市场冷清"
    
    return {"theme": theme, "top_sectors": ranked[:6]}

# ═══════════════════════════════════
# 维度4: 龙虎榜热度
# ═══════════════════════════════════
def scan_dragon_heat():
    """龙虎榜 — 机构席位动向"""
    print("🟢 维度4: 龙虎榜...")
    
    # 搜索龙虎榜
    run_mx(SEARCH, "今日龙虎榜 机构净买入 主板")
    f = latest_csv("龙虎榜")
    
    dragon = []
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    code = row.get("代码","")
                    name = row.get("名称","")
                    # 尝试不同字段名
                    net_buy = row.get("净买额","") or row.get("净买入","") or "0"
                    if "万" in str(net_buy):
                        net_val = float(net_buy.replace("万","").replace("亿",""))
                        if "亿" in str(net_buy): net_val *= 10000
                    else:
                        net_val = 0
                    if net_val > 1000:  # >1000万
                        dragon.append({"code": code, "name": name, "net_buy": net_val})
                except: pass
    
    dragon.sort(key=lambda x: x["net_buy"], reverse=True)
    return dragon[:8]

# ═══════════════════════════════════
# 维度5: 新闻热度 — 今日大事
# ═══════════════════════════════════
def scan_news_heat():
    """今日重大新闻/政策"""
    print("🔵 维度5: 新闻热度...")
    
    # 搜索今日重要新闻
    run_mx(SEARCH, "今日A股 重要新闻 政策 行业利好")
    f = latest_csv("重要新闻")
    
    news = []
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                title = row.get("标题","") or row.get("title","")
                if title:
                    news.append(title[:60])
    
    return news[:6]

# ═══════════════════════════════════
# 维度6: 自选股热度
# ═══════════════════════════════════
def scan_zixuan_heat():
    """自选股今日表现"""
    print("🟣 维度6: 自选股热度...")
    
    zixuan_csv = f"{OUTPUT}/mx_zixuan_我的自选股列表.csv"
    if not os.path.exists(zixuan_csv):
        run_mx(os.path.expanduser("~/.openclaw-autoclaw/skills/mx-zixuan/mx_zixuan.py"), "我的自选")
    
    stocks = []
    if os.path.exists(zixuan_csv):
        with open(zixuan_csv, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                code = row.get("代码","").replace(".SZ","").replace(".SH","")
                name = row.get("名称","")
                chg_str = row.get("涨跌幅(%)","") or row.get("涨跌幅","0")
                chg = float(chg_str.replace("%","")) if chg_str else 0
                stocks.append({"code": code, "name": name, "chg": chg})
    
    up = [s for s in stocks if s["chg"] > 3]
    down = [s for s in stocks if s["chg"] < -3]
    
    up.sort(key=lambda x: x["chg"], reverse=True)
    down.sort(key=lambda x: x["chg"])
    
    return {"up": up, "down": down, "total": len(stocks)}

# ═══════════════════════════════════
# 维度8: 社交媒体热度 (零API消耗)
# ═══════════════════════════════════
def scan_social_heat():
    """东方财富人气榜 — 关注度排行"""
    print("❤️ 维度8: 社交媒体热度...")
    
    try:
        url = ("https://push2.eastmoney.com/api/qt/clist/get?"
               "pn=1&pz=20&po=1&np=1&fields=f12,f14,f3,f2,f20&"
               "fid=f10&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fltt=2")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        
        stocks = []
        if data and data.get("data"):
            for item in data["data"].get("diff", [])[:20]:
                stocks.append({
                    "code": item.get("f12",""),
                    "name": item.get("f14",""),
                    "chg": item.get("f3",0) or 0,
                    "price": item.get("f2",0) or 0,
                    "mkt_cap": (item.get("f20",0) or 0) / 1e8
                })
        
        # 分离主板
        main_board = [s for s in stocks if not s["code"].startswith(("300","688","8"))]
        return {"all": stocks, "main_board": main_board[:10]}
    except:
        return {"all": [], "main_board": []}

# ═══════════════════════════════════
# 主报告
# ═══════════════════════════════════
def generate_report():
    now = datetime.now()
    today_str = now.strftime("%Y年%m月%d日")
    
    print("=" * 55)
    print(f"  🌙 A股深夜情报站")
    print(f"  📅 {today_str} {now.strftime('%H:%M')}")
    print("=" * 55)
    
    # 6维扫描
    limit = scan_limit_up_hot()
    volume = scan_volume_heat()
    sector = scan_sector_heat()
    # dragon = scan_dragon_heat()  # 耗时，可选
    news = scan_news_heat()
    zixuan = scan_zixuan_heat()
    
    report = []
    report.append(f"🌙 **深夜情报站** {today_str}")
    report.append("")
    
    # 1. 涨停热度
    report.append(f"🔴 **涨停热度**: {limit['limit_up_count']}只涨停(主板)")
    for s in limit["top_limit_ups"][:5]:
        report.append(f"  • {s['name']} {s['code']} +{s['chg']:.1f}% 换手{s['turnover']:.0f}%")
    
    # 2. 板块主线
    report.append(f"\n📊 **今日主线**: {sector['theme']}")
    for name, cnt, avg, stocks in sector["top_sectors"][:5]:
        report.append(f"  • {name} {cnt}只 均{avg:+.1f}%")
    
    # 3. 成交热度
    report.append(f"\n🟠 **天量换手 TOP5**:")
    for v in volume[:5]:
        report.append(f"  • {v['name']} {v['code']} 换手{v['turnover']:.0f}% {v['chg']:+.1f}%")
    
    # 4. 自选股
    report.append(f"\n⭐ **自选股异动** ({zixuan['total']}只):")
    if zixuan["up"]:
        report.append("  📈 强势:")
        for s in zixuan["up"][:5]:
            report.append(f"    {s['name']} +{s['chg']:.1f}%")
    if zixuan["down"]:
        report.append("  📉 弱势:")
        for s in zixuan["down"][:5]:
            report.append(f"    {s['name']} {s['chg']:.1f}%")
    if not zixuan["up"] and not zixuan["down"]:
        report.append("  (无异常波动)")
    
    # 5. 新闻速递
    if news:
        report.append(f"\n📰 **今夜要闻**:")
        for n in news[:4]:
            report.append(f"  • {n}")
    
    # 6. 积分
    import subprocess
    pts = subprocess.run(["python3", os.path.expanduser("~/dao-analyst/points_tracker.py"), "quick"],
                        capture_output=True, text=True).stdout.strip()
    report.append(f"\n📊 {pts}")
    
    # 保存
    report_path = os.path.expanduser(f"~/.openclaw-autoclaw/workspace/reports/nightly_{today_str.replace('年','').replace('月','').replace('日','')}.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report))
    

    # ═══════════════════════════════════
    # 维度7: 板块前5 + 个股前10 排名榜
    # ═══════════════════════════════════
    print("\n👑 维度7: 排名榜...")
    run_mx(XG, "主板 今日涨幅大于3% 非ST 非新股 换手率大于1% 按涨跌幅降序")
    f_top = latest_csv("涨幅大于3%")
    top_stocks = []
    if f_top:
        with open(f_top, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    code = row.get("代码","")
                    name = row.get("名称","")
                    chg = float(row.get("涨跌幅(%)","0").replace("%",""))
                    turnover = float(row.get("换手率(%)","0"))
                    price = float(row.get("最新价(元)","0"))
                    mkt = row.get("流通市值(元)","0")
                    mkt_v = float(mkt.replace("亿","")) if "亿" in mkt else 0
                    
                    # 排除ST、新股、市值太小
                    if "ST" in name or "N" == name[:1]:
                        continue
                    if mkt_v < 20:
                        continue
                    if chg > 20:  # 排除异常值
                        continue
                    
                    top_stocks.append({
                        "code": code, "name": name, "chg": chg,
                        "turnover": turnover, "price": price, "mkt": mkt_v
                    })
                except: pass
    
    # 去重(同股不同市场)
    seen = set()
    unique_stocks = []
    for s in sorted(top_stocks, key=lambda x: x["chg"], reverse=True):
        if s["code"] not in seen:
            seen.add(s["code"])
            unique_stocks.append(s)
    
    report.append("")
    report.append("═══════════════════════════")
    report.append("  👑 今日排名榜")
    report.append("═══════════════════════════")
    
    # 板块 TOP5
    report.append(f"\n🔥 **板块 TOP5**:")
    for i, (name, cnt, avg, stocks) in enumerate(sector["top_sectors"][:5], 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        report.append(f"  {medal} {name}  {cnt}只 均{avg:+.1f}%")
    
    # 个股 TOP10
    report.append(f"\n📈 **个股 TOP10** (主板 涨幅>3% 市值>20亿):")
    for i, s in enumerate(unique_stocks[:10], 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i:>2}."
        report.append(f"  {medal} {s['name']:<6} {s['code']} +{s['chg']:.1f}%  换手{s['turnover']:.0f}%  {s['mkt']:.0f}亿")
    
    # 自选股在榜标记
    zixuan_codes = {s["code"] for s in zixuan.get("up", [])}
    in_ranking = [s for s in unique_stocks[:20] if s["code"] in zixuan_codes]
    if in_ranking:
        report.append(f"\n⭐ 自选股上榜: {', '.join(s['name'] for s in in_ranking)}")
    
    print("\n" + "\n".join(report))
    print(f"\n💾 报告已保存: {report_path}")
    
    return "\n".join(report)

if __name__ == "__main__":
    generate_report()
