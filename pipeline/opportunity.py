#!/usr/bin/env python3
"""全市场实时扫描 V2 — 主板+过滤ST/创业板/科创板/ETF"""
import sys, os, json, urllib.request, ssl, http.cookiejar
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_xueqiu_hot():
    """雪球实时热榜 (全市场最活跃)"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try:
        opener.open(urllib.request.Request("https://xueqiu.com/",
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8)
        r = json.loads(opener.open(urllib.request.Request(
            "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=30&_type=12&type=12",
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8).read())
        return r.get("data",{}).get("items",[])
    except: return []

def tencent_batch(codes):
    """腾讯批量行情验证"""
    if not codes: return {}
    qcodes = ",".join(f"{'sh' if c.startswith('6') else 'sz'}{c}" for c in codes)
    try:
        raw = urllib.request.urlopen(f"https://qt.gtimg.cn/q={qcodes}", timeout=8).read().decode("gbk")
        result = {}
        for line in raw.strip().split("\n"):
            if "=" not in line: continue
            p = line.split("=")[1].strip('"').split("~")
            if len(p) < 40: continue
            code = p[2]
            result[code] = {"name":p[1],"price":float(p[3]),"chg":float(p[32]),
                "turnover":float(p[38]),"pe":float(p[39]) if p[39] else 0,"amount":float(p[37])}
        return result
    except: return {}

def is_main_board(code):
    """主板过滤: 排除创业板/科创板/北交所/ETF"""
    if code.startswith(("300","301")): return False  # 创业板
    if code.startswith(("688","689")): return False   # 科创板
    if code.startswith(("8","4")): return False        # 北交所/新三板
    if code.startswith("5"): return False              # ETF/基金
    if code.startswith("1"): return False              # 债券/ETF
    return len(code) == 6

def is_valid_stock(name, code):
    """过滤ST和异常标的"""
    if "ST" in name.upper(): return False
    if "退" in name: return False
    if name.startswith("N"): return False  # 新股
    if name.startswith("C"): return False  # 次新股
    return True

def scan_full_market():
    """全市场实时扫描"""
    # 1. 雪球热榜 (实时社区热度)
    items = get_xueqiu_hot()
    
    all_stocks = []
    for item in items:
        code = str(item.get("code","")).replace("SH","").replace("SZ","")
        name = item.get("name","")
        if not is_main_board(code): continue
        if not is_valid_stock(name, code): continue
        all_stocks.append({"code":code,"name":name,"chg_xq":item.get("percent",0)})
    
    # 2. 腾讯批量验证
    codes = [s["code"] for s in all_stocks[:25]]
    quotes = tencent_batch(codes)
    
    # 3. V3.1筛选
    results = {"buy":[],"dip":[],"watch":[],"rejected":[],"sector_heat":[],"short_term":[]}
    
    # 热点板块+政策方向
    try:
        from pipeline.sector_filter import hot_sector_scan
        sr = hot_sector_scan()
        if sr.get("sectors"):
            results["sector_heat"] = sr["sectors"][:5]
    except: pass
    
    # 批量获取资金流数据
    try:
        from pipeline.fetcher import fetch
        fund_data = {}
        for s in all_stocks[:10]:  # 只取前10只的资金
            fd = fetch(s["code"], full=True)
            if "fund" in fd and fd["fund"]:
                fund_data[s["code"]] = fd["fund"]
    except: fund_data = {}
    
    for s in all_stocks:
        code = s["code"]
        if code not in quotes: continue
        q = quotes[code]
        # 合并资金数据
        if code in fund_data:
            q["fund"] = fund_data[code]
        
        chg = q["chg"]; pe = q["pe"]; to = q["turnover"]; price = q["price"]
        
        # 排除条件
        rejected = False
        if chg < -5: 
            results["rejected"].append({**s,**q,"reason":"跌幅过大"})
            rejected = True
        if to > 18:
            results["rejected"].append({**s,**q,"reason":f"换手{to:.0f}%异常"})
            rejected = True
        if price > 300:
            results["rejected"].append({**s,**q,"reason":"单价过高"})
            rejected = True
        if pe > 200:
            results["rejected"].append({**s,**q,"reason":"PE过高"})
            rejected = True
        if rejected: continue
        
        # 资金流向评分
        fund_score = 0
        fund_tag = ""
        if 'fund' in q:
            net = q['fund']['net'] if isinstance(q.get('fund'), dict) else 0
            if net > 5000: fund_score = 3; fund_tag = "主力做多"
            elif net > 1000: fund_score = 2; fund_tag = "主力流入"
            elif net > 0: fund_score = 1; fund_tag = "小幅流入"
            elif net > -3000: fund_score = 0; fund_tag = "小幅流出"
            else: fund_score = -1; fund_tag = "主力出逃"
        
        # 信号评估
        signal = 0
        if 0 < pe < 50: signal += 1
        if 3 <= to <= 12: signal += 1
        if chg > 0: signal += 1
        if fund_score >= 2: signal += 1  # 资金面加分
        
        # 分类
        if 1.5 <= chg <= 5 and signal >= 1:
            results["buy"].append({**s,**q,"signal":signal,"fund_tag":fund_tag})
        elif -2 >= chg >= -5 and fund_score >= 0:
            results["dip"].append({**s,**q,"signal":signal,"fund_tag":fund_tag})
        else:
            results["watch"].append({**s,**q,"signal":signal})
    
    # 排序
    results["buy"].sort(key=lambda x: x["chg"], reverse=True)
    
    # 短线+游资扫描
    try:
        from pipeline.short_term import short_term_scan
        st_data = [{"code":s.get("code",""),"name":s.get("name",""),"chg":s.get("chg",0),
            "turnover":s.get("turnover",0),"pe":s.get("pe",0),"price":s.get("price",0)}
            for s in all_stocks if s.get("code") in quotes]
        results["short_term"] = short_term_scan(st_data)[:5]
    except: pass
    results["dip"].sort(key=lambda x: x["chg"])
    
    return results

def generate_report():
    results = scan_full_market()
    now = datetime.now()
    
    lines = [f"🔍 全市场实时扫描 {now.strftime('%H:%M')}"]
    lines.append(f"  雪球热榜→腾讯验证→主板过滤→V3.1筛选")
    lines.append("")
    
    total = sum(len(v) for v in results.values())
    lines.append(f"  扫描{total}只 · 过滤ST/创业板/科创板/ETF")
    
    if results["short_term"]:
        lines.append(f"\n🎯 短线+游资 ({len(results['short_term'])}只):")
        for r in results["short_term"][:5]:
            dt = " 🐉龙虎榜" if r.get("dragon_tiger") else ""
            li = f" {r['limit_info']}" if r.get("limit_info") else ""
            lines.append(f"  {r['name']:<6} {r['code']} {r['chg']:+.1f}% 换手{r['turnover']:.1f}% 游资{r['hm_score']}分{dt}{li}")
    
    if results["sector_heat"]:
        lines.append(f"\n🔥 热点板块:")
        for s in results["sector_heat"][:5]:
            pol = f" 🎯{s['policy']}" if s.get('policy') else ""
            lines.append(f"  {s['name']} {s['chg']:+.1f}%{pol}")
    
    if results["buy"]:
        lines.append(f"\n💰 可建仓 ({len(results['buy'])}只):")
        for r in results["buy"][:5]:
            ft = r.get('fund_tag','')
            fstr = f" {ft}" if ft else ""
            lines.append(f"  ✅ {r['name']:<6} {r['code']} ¥{r['price']:.2f} {r['chg']:+.1f}% PE={r['pe']:.0f} 换手{r['turnover']:.1f}%{fstr}")
    
    if results["dip"]:
        lines.append(f"\n📥 低吸机会 ({len(results['dip'])}只):")
        for r in results["dip"][:3]:
            lines.append(f"  👀 {r['name']:<6} {r['code']} ¥{r['price']:.2f} {r['chg']:+.1f}%")
    
    if not results["buy"] and not results["dip"]:
        if results["watch"]:
            lines.append(f"\n👀 待观察 ({len(results['watch'])}只):")
            for r in results["watch"][:5]:
                lines.append(f"  ·  {r['name']:<6} {r['code']} {r['chg']:+.1f}%")
        lines.append(f"\n  当前无明确机会, 继续等待")
    
    if results["rejected"]:
        lines.append(f"\n  (过滤{len(results['rejected'])}只: ST/跌幅大/换手异常/PE过高)")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_report())
