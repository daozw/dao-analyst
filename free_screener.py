#!/usr/bin/env python3
"""
免费API统一筛选器 V2.0
数据源: 东财人气+妙想选股+腾讯行情+雪球热榜+通达信K线 — 全免费
"""
import urllib.request, json, ssl, csv, os, sys, subprocess, http.cookiejar
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

MX_KEY = "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8"
XG = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py")
OUTPUT = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output")

# 雪球 session 复用
_xq_opener = None
def get_xueqiu():
    global _xq_opener
    if _xq_opener: return _xq_opener
    cj = http.cookiejar.CookieJar()
    _xq_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try:
        _xq_opener.open(urllib.request.Request("https://xueqiu.com/",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}), timeout=10)
    except: pass
    return _xq_opener

def fetch_east(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except: return None

def fetch_tencent(codes):
    try:
        qcodes = ",".join(f"{'sh' if c.startswith('6') else 'sz'}{c}" for c in codes)
        req = urllib.request.Request(f"https://qt.gtimg.cn/q={qcodes}")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("gbk", errors="replace")
    except: return None

# ═══════════════════════════════════
# 源1: 东方财富人气榜
# ═══════════════════════════════════
def east_popularity():
    data = fetch_east("https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&fields=f12,f14,f3,f2,f20,f9,f10,f62&fid=f10&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fltt=2")
    results = {}
    if data:
        for i, item in enumerate(data.get("data",{}).get("diff",[])):
            code = item.get("f12","")
            results[code] = {"name": item.get("f14",""), "chg": item.get("f3",0) or 0,
                "price": item.get("f2",0) or 0, "mkt_cap": (item.get("f20",0) or 0)/1e8,
                "pe": item.get("f9",0) or 0, "pop_rank": i+1,
                "net_inflow": (item.get("f62",0) or 0)/1e8}
    return results

# ═══════════════════════════════════
# 源2: 雪球 A股热榜
# ═══════════════════════════════════
def xueqiu_hot():
    try:
        opener = get_xueqiu()
        req = urllib.request.Request(
            "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=20&_type=12&type=12",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://xueqiu.com/"})
        resp = opener.open(req, timeout=10)
        data = json.loads(resp.read())
        results = {}
        for i, item in enumerate(data.get("data",{}).get("items",[])):
            code = str(item.get("code","")).replace("SH","").replace("SZ","")
            if len(code) == 6:
                results[code] = {"name": item.get("name",""), "chg": item.get("percent",0) or 0, "xq_rank": i+1}
        return results
    except: return {}

# ═══════════════════════════════════
# 源3: 妙想 V2.1波段
# ═══════════════════════════════════
def mx_screen_band():
    import glob
    env = {**os.environ, "MX_APIKEY": MX_KEY}
    subprocess.run(["python3", XG, "主板 市盈率小于25 市净率小于2.5 今日涨幅1.5%到8% 换手率大于2% 按涨跌幅降序"],
                   capture_output=True, text=True, env=env, timeout=30)
    files = sorted(glob.glob(f"{OUTPUT}/mx_xuangu_*市盈率小于25*市净率小于2.5*.csv"),
                   key=lambda x: os.path.getmtime(x), reverse=True)
    results = {}
    if files:
        with open(files[0], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    code = row.get("代码","").replace(".SZ","").replace(".SH","")
                    chg = float(row.get("涨跌幅(%)","0").replace("%",""))
                    pe = float(row.get("市盈率(动)(倍)","0")) if row.get("市盈率(动)(倍)","0").replace("-","").strip() else 0
                    turnover = float(row.get("换手率(%)","0"))
                    if 1.5<=chg<=8 and turnover>2:
                        results[code] = {"name": row.get("名称",""), "chg": chg, "pe": pe,
                            "turnover": turnover, "price": float(row.get("最新价(元)","0"))}
                except: pass
    return results

# ═══════════════════════════════════
# 源4: 腾讯行情验证
# ═══════════════════════════════════
def tencent_verify(codes):
    raw = fetch_tencent(codes)
    results = {}
    if raw:
        for line in raw.strip().split("\n"):
            if "=" not in line: continue
            try:
                parts = line.split("=")[1].strip('"').split("~")
                if len(parts) < 39: continue
                code = parts[2]
                results[code] = {"name": parts[1], "price": float(parts[3]) if parts[3] else 0,
                    "chg": float(parts[32]) if parts[32] else 0, "turnover": float(parts[38]) if parts[38] else 0,
                    "pe": float(parts[39]) if parts[39] else 0}
            except: pass
    return results

# ═══════════════════════════════════
# 源5: 通达信K线验证
# ═══════════════════════════════════
def mootdx_verify(codes):
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        results = {}
        for code in codes[:10]:
            try:
                data = client.bars(symbol=code, frequency=9, start=0, offset=2)
                if len(data) > 0:
                    results[code] = {"verified": True, "bars": len(data)}
            except: pass
        return results
    except: return {}

# ═══════════════════════════════════
# 统一评分
# ═══════════════════════════════════
def unified_score(east_data, xq_data, mx_data, tencent_data, mootdx_data):
    all_stocks = {}
    
    # 妙想V2.1 (30分)
    for code, d in mx_data.items():
        all_stocks[code] = {"name": d["name"], "code": code, "score": 30, "reasons": ["V2.1波段✅"],
            "chg": d["chg"], "pe": d.get("pe",0), "turnover": d.get("turnover",0), "price": d.get("price",0)}
    
    # 东财人气(20分) + 主力资金(20分)
    for code, d in east_data.items():
        if code not in all_stocks:
            all_stocks[code] = {"name": d["name"], "code": code, "score": 0, "reasons": [], "chg": d.get("chg",0)}
        rank = d["pop_rank"]
        pop_s = max(0, 20 - int(rank * 0.4))
        all_stocks[code]["score"] = round(all_stocks[code]["score"] + pop_s, 1)
        all_stocks[code]["pop_rank"] = rank
        if pop_s >= 10: all_stocks[code]["reasons"].append(f"人气TOP{rank}")
        
        inflow = d.get("net_inflow", 0)
        fund_s = min(20, max(0, inflow * 20))
        all_stocks[code]["score"] = round(all_stocks[code]["score"] + fund_s, 1)
        all_stocks[code]["net_inflow"] = inflow
        if fund_s >= 10: all_stocks[code]["reasons"].append(f"主力{inflow:.1f}亿")
        all_stocks[code]["mkt_cap"] = d.get("mkt_cap", 0)
    
    # 雪球热榜(15分)
    for code, d in xq_data.items():
        if code not in all_stocks:
            all_stocks[code] = {"name": d["name"], "code": code, "score": 0, "reasons": [], "chg": d.get("chg",0)}
        xq_s = max(0, 15 - int(d.get("xq_rank", 20) * 0.75))
        all_stocks[code]["score"] = round(all_stocks[code]["score"] + xq_s, 1)
        if xq_s >= 8: all_stocks[code]["reasons"].append(f"雪球TOP{d['xq_rank']}")
    
    # 腾讯验证(10分)
    for code, d in tencent_data.items():
        if code in all_stocks:
            all_stocks[code]["score"] = round(all_stocks[code]["score"] + 10, 1)
            all_stocks[code]["reasons"].append("腾讯✅")
    
    # 通达信验证(5分)
    for code in mootdx_data:
        if code in all_stocks:
            all_stocks[code]["score"] = round(all_stocks[code]["score"] + 5, 1)
    
    # 只保留主板
    filtered = {c: d for c, d in all_stocks.items() if not c.startswith(("300","301","688","8","4"))}
    return sorted(filtered.values(), key=lambda x: x["score"], reverse=True)

# ═══════════════════════════════════
# 主程序
# ═══════════════════════════════════
def run():
    now = datetime.now()
    print("=" * 60)
    print(f"  🎯 免费API统一筛选 V2.0")
    print(f"  📅 {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  📡 东财+雪球+妙想+腾讯+通达信 → 五源综合")
    print("=" * 60)
    
    print("\n📡 获取数据...")
    
    print("  1/5 东方财富人气榜...")
    east = east_popularity()
    print(f"      {len(east)}只")
    
    print("  2/5 雪球A股热榜...")
    xq = xueqiu_hot()
    print(f"      {len(xq)}只")
    
    print("  3/5 妙想V2.1波段...")
    mx = mx_screen_band()
    print(f"      {len(mx)}只符合")
    
    candidates = set(list(mx.keys())[:30] + list(east.keys())[:30] + list(xq.keys())[:20])
    tx_codes = list(candidates)[:20]
    
    print(f"  4/5 腾讯行情({len(tx_codes)}只)...")
    tencent = tencent_verify(tx_codes)
    print(f"      {len(tencent)}只验证")
    
    print(f"  5/5 通达信K线...")
    mdx = mootdx_verify(tx_codes)
    print(f"      {len(mdx)}只")
    
    print("\n📊 综合评分...")
    ranked = unified_score(east, xq, mx, tencent, mdx)
    
    print(f"\n🏆 五源综合评分 TOP20 (主板)")
    print(f"  {'排名':<4} {'名称':<8} {'代码':<8} {'涨跌':>6} {'PE':>5} {'总分':>5} {'入选理由'}")
    print(f"  {'-'*65}")
    
    for i, s in enumerate(ranked[:20], 1):
        pe_str = f'{s.get("pe",0):.0f}' if s.get("pe",0) > 0 else "-"
        reasons = ", ".join(s.get("reasons", [])[:3])
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i:>2}."
        print(f"  {medal} {s['name']:<8} {s['code']:<8} {s.get('chg',0):>+5.1f}% {pe_str:>4} {s['score']:>4}分  {reasons:<36}")
    
    mscore = {"东财人气(20)": 20, "主力资金(20)": 20, "雪球热榜(15)": 15, "妙想V2.1(30)": 30, "腾讯验证(10)": 10, "通达信(5)": 5}
    print(f"\n📋 评分: {'+'.join(f'{v}' for k,v in mscore.items())} = 100分")
    print(f"📡 调用: 5次免费API, 0消耗妙想积分")

if __name__ == "__main__":
    run()
