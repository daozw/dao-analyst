#!/usr/bin/env python3
"""短线·热点·打板 三位一体扫描器"""
import subprocess, json, sys
from datetime import datetime

MX_APIKEY = "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8"
API = "https://mkapi2.dfcfs.com/finskillshub"

def mx_query(query):
    """调用妙想选股"""
    script = "/Users/sound/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py"
    env = {"MX_APIKEY": MX_APIKEY, "PATH": "/usr/bin:/usr/local/bin"}
    r = subprocess.run(["python3", script, query], capture_output=True, text=True, 
                       env={**__import__('os').environ, **env}, timeout=20)
    return r.stdout

def scan_limit_up():
    """打板扫描：今日涨停股"""
    print("🔴 涨停板扫描...")
    out = mx_query("今日涨停 非ST 主板 换手率大于2% 封单量")
    
    # 尝试从CSV读取
    import glob
    files = sorted(glob.glob("/Users/sound/.openclaw-autoclaw/workspace/mx_data/output/mx_xuangu_*涨停*.csv"), 
                   key=lambda x: __import__('os').path.getmtime(x), reverse=True)
    
    boards = []
    if files:
        import csv
        with open(files[0], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    name = row.get("名称","").strip()
                    code = row.get("代码","")
                    chg = float(row.get("涨跌幅(%)", "0").replace("%",""))
                    price = float(row.get("最新价(元)", "0"))
                    turnover = float(row.get("换手率(%)", "0"))
                    mkt = row.get("流通市值(元)", "0")
                    mkt_v = float(mkt.replace("亿","")) if "亿" in mkt else 0
                    
                    # 只保留主板+市值>30亿
                    if chg >= 9.8 and mkt_v > 30:
                        boards.append({
                            "code": code, "name": name, "price": price,
                            "chg": chg, "turnover": turnover, "mkt": mkt_v
                        })
                except: pass
    
    return boards

def scan_hot_sectors():
    """热点板块扫描"""
    print("🔥 热点板块扫描...")
    out = mx_query("今日涨幅最大行业板块 主板 涨幅大于3%")
    
    import glob, csv
    files = sorted(glob.glob("/Users/sound/.openclaw-autoclaw/workspace/mx_data/output/mx_xuangu_*涨幅最大*板块*.csv"),
                   key=lambda x: __import__('os').path.getmtime(x), reverse=True)
    
    sectors = {}
    if files:
        with open(files[0], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    sector = row.get("东财行业分类二级", "")
                    if not sector: continue
                    chg = float(row.get("涨跌幅(%)", "0").replace("%",""))
                    if chg < 3: continue
                    if sector not in sectors:
                        sectors[sector] = {"count": 0, "total_chg": 0, "stocks": []}
                    sectors[sector]["count"] += 1
                    sectors[sector]["total_chg"] += chg
                    sectors[sector]["stocks"].append(row.get("名称","").strip())
                except: pass
    
    return sectors

def scan_short_term():
    """短线标的扫描：放量+低位+即将突破"""
    print("⚡ 短线扫描...")
    
    # 低位放量：价格在60日低位 今日放量上涨
    out = mx_query("主板 股价小于30元 今日涨幅3%到8% 换手率大于5% 量比大于1.5")
    
    import glob, csv
    files = sorted(glob.glob("/Users/sound/.openclaw-autoclaw/workspace/mx_data/output/mx_xuangu_*股价小于30*换手率大于5*量比大于*.csv"),
                   key=lambda x: __import__('os').path.getmtime(x), reverse=True)
    
    shorts = []
    if files:
        with open(files[0], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    name = row.get("名称","").strip()
                    code = row.get("代码","")
                    chg = float(row.get("涨跌幅(%)", "0").replace("%",""))
                    price = float(row.get("最新价(元)", "0"))
                    turnover = float(row.get("换手率(%)", "0"))
                    vol_ratio = float(row.get("量比", "0"))
                    mkt = row.get("流通市值(元)", "0")
                    mkt_v = float(mkt.replace("亿","")) if "亿" in mkt else 0
                    
                    # 主板+市值30-500亿(中小盘)
                    if 3 <= chg <= 8 and vol_ratio > 1.5 and 30 < mkt_v < 500:
                        short_score = chg * 0.4 + turnover * 0.3 + vol_ratio * 0.3
                        shorts.append({
                            "code": code, "name": name, "price": price,
                            "chg": chg, "turnover": turnover, "vol_ratio": vol_ratio,
                            "mkt": mkt_v, "score": round(short_score, 1)
                        })
                except: pass
    
    shorts.sort(key=lambda x: x["score"], reverse=True)
    return shorts[:15]

# === 主程序 ===
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    now = datetime.now().strftime("%H:%M")
    
    print(f"🔍 短线·热点·打板扫描  {now}")
    print("="*55)
    
    if mode in ("all", "limit"):
        boards = scan_limit_up()
        print(f"\n🔴 今日涨停板 ({len(boards)}只 主板 市值>30亿):")
        for b in boards[:10]:
            print(f"  {b['name']:<6} {b['code']}  ¥{b['price']:<6} +{b['chg']:.1f}%  换手{b['turnover']:.0f}%  {b['mkt']:.0f}亿")
    
    if mode in ("all", "hot"):
        sectors = scan_hot_sectors()
        ranked = sorted(sectors.items(), key=lambda x: x[1]["total_chg"]/x[1]["count"], reverse=True)
        print(f"\n🔥 热点板块 TOP8:")
        for name, d in ranked[:8]:
            if d["count"] >= 2:
                avg = d["total_chg"] / d["count"]
                stocks_str = ",".join(d["stocks"][:3])
                print(f"  {name:<12} {d['count']:>2}只 均{avg:+.1f}%  [{stocks_str}]")
    
    if mode in ("all", "short"):
        shorts = scan_short_term()
        print(f"\n⚡ 短线标的 ({len(shorts)}只 放量+低位+待突破):")
        for s in shorts:
            print(f"  {s['name']:<6} {s['code']}  ¥{s['price']:<6} +{s['chg']:.1f}%  换手{s['turnover']:.0f}%  量比{s['vol_ratio']:.1f}  得分{s['score']}")
