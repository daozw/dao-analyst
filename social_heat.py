#!/usr/bin/env python3
"""
社交媒体热度扫描 V1.0
数据源: 东方财富人气榜 + 热搜
独立于行情数据，周末也更新
"""
import urllib.request, json, ssl, os, sys
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": "https://www.eastmoney.com/"
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return None

# ═══════════════════════════════════
# 1. 东方财富 个股人气榜
# ═══════════════════════════════════
def get_popularity_ranking(count=20):
    """个股人气榜 — 按关注度排名"""
    data = fetch(
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=20&po=1&np=1&fields=f12,f14,f3,f2,f10,f20,f9,f8&"
        "fid=f10&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fltt=2"
    )
    
    results = []
    if data and data.get("data"):
        for item in data["data"].get("diff", [])[:count]:
            code = item.get("f12", "")
            name = item.get("f14", "")
            chg = item.get("f3", 0) or 0
            price = item.get("f2", 0) or 0
            mkt_cap = (item.get("f20", 0) or 0) / 1e8
            pe = item.get("f9", 0) or 0
            
            # 关注度排序已经由API完成 (fid=f10)
            results.append({
                "code": code, "name": name, "chg": chg,
                "price": price, "mkt_cap": mkt_cap, "pe": pe
            })
    
    return results

# ═══════════════════════════════════
# 2. 板块关注度
# ═══════════════════════════════════
def get_sector_popularity(count=5):
    """板块关注度排行"""
    data = fetch(
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=10&po=1&np=1&fields=f12,f14,f3,f62,f184&"
        "fid=f184&fs=m:90+t:2&fltt=2"
    )
    
    results = []
    if data and data.get("data"):
        for item in data["data"].get("diff", [])[:count]:
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "chg": item.get("f3", 0) or 0,
                "net_inflow": (item.get("f62", 0) or 0) / 1e8,  # 主力净流入(亿)
                "attention": item.get("f184", 0)  # 关注度
            })
    return results

# ═══════════════════════════════════
# 3. 分类筛选
# ═══════════════════════════════════
def filter_main_board(stocks):
    """只保留主板(排除300/688/8开头)"""
    return [s for s in stocks if not s["code"].startswith(("300","688","8"))]

def filter_self_selected(stocks, zixuan_codes):
    """标记自选股"""
    for s in stocks:
        s["in_zixuan"] = s["code"] in zixuan_codes
    return stocks

# ═══════════════════════════════════
# 主报告
# ═══════════════════════════════════
def generate():
    now = datetime.now()
    print("=" * 55)
    print(f"  🔥 社交媒体热度排行")
    print(f"  📅 {now.strftime('%Y年%m月%d日 %H:%M')}")
    print(f"  📡 数据源: 东方财富人气榜 (实时)")
    print("=" * 55)
    
    # 个股人气 TOP20
    print(f"\n👥 **全市场人气榜 TOP20**")
    print(f"  (按关注度排名，独立于涨跌幅)")
    print(f"  {'排名':<4} {'名称':<8} {'代码':<8} {'价格':>8} {'涨跌':>6} {'市值':>8}")
    print(f"  {'-'*46}")
    
    stocks = get_popularity_ranking(20)
    
    # 标记自选股
    zixuan_csv = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output/mx_zixuan_我的自选股列表.csv")
    zixuan_codes = set()
    if os.path.exists(zixuan_csv):
        import csv
        with open(zixuan_csv, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                code = row.get("代码","").replace(".SZ","").replace(".SH","")
                if code: zixuan_codes.add(code)
    
    in_ranking = []
    for i, s in enumerate(stocks, 1):
        zx_tag = " ⭐" if s["code"] in zixuan_codes else ""
        print(f"  {i:>3}. {s['name']:<8} {s['code']:<8} {s['price']:>7.2f} {s['chg']:>+5.1f}% {s['mkt_cap']:>6.0f}亿{zx_tag}")
        if s["code"] in zixuan_codes:
            in_ranking.append(s)
    
    if in_ranking:
        print(f"\n  ⭐ 自选股上榜: {', '.join(s['name'] for s in in_ranking)}")
    
    # 主板人气 TOP10
    main_stocks = filter_main_board(stocks)
    if main_stocks:
        print(f"\n🏠 **主板人气 TOP10**:")
        for i, s in enumerate(main_stocks[:10], 1):
            zx_tag = " ⭐" if s["code"] in zixuan_codes else ""
            print(f"  {i:>2}. {s['name']:<8} {s['code']} {s['chg']:>+5.1f}%{zx_tag}")
    
    # 板块关注度
    sectors = get_sector_popularity(5)
    if sectors:
        print(f"\n📊 **板块关注度 TOP5**:")
        for i, s in enumerate(sectors, 1):
            medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            print(f"  {medal} {s['name']:<12} {s['chg']:>+5.1f}%  主力净流入{s['net_inflow']:+.1f}亿")
    
    return stocks

if __name__ == "__main__":
    generate()
