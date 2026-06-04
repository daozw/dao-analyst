#!/usr/bin/env python3
"""游资方向+短线炒作检测"""
import urllib.request, json, ssl
ssl._create_default_https_context = ssl._create_unverified_context

def detect_hot_money(code, chg, turnover, vol_ratio=1.0):
    """
    游资炒作信号检测
    
    特征: 高换手 + 快速涨跌 + 龙虎榜活跃
    返回: (score, level, reason)
    """
    score = 0
    reasons = []
    
    # 1. 换手率 (游资生命线)
    if turnover > 20: score += 25; reasons.append("超高换手")
    elif turnover > 15: score += 20; reasons.append("高换手")
    elif turnover > 10: score += 15; reasons.append("换手活跃")
    elif turnover > 5: score += 8
    
    # 2. 涨跌幅 (游资偏好)
    if 3 <= chg <= 6: score += 15; reasons.append("温和拉升")
    elif 6 < chg <= 9: score += 20; reasons.append("强势拉升")
    elif chg > 9: score += 30; reasons.append("涨停板")
    elif -3 >= chg >= -6: score += 5; reasons.append("洗盘回调")
    
    # 3. 量比 (放量=游资入场)
    if vol_ratio > 3: score += 20; reasons.append("天量")
    elif vol_ratio > 2: score += 15; reasons.append("放量")
    elif vol_ratio > 1.5: score += 10; reasons.append("温和放量")
    
    # 4. 极端波动 (游资对倒特征)
    if chg > 8 and turnover > 20: score += 10; reasons.append("游资对倒")
    
    if score >= 50: level = "🔥 游资主攻"
    elif score >= 35: level = "🟡 游资关注"
    elif score >= 20: level = "👀 短线活跃"
    else: level = ""
    
    return score, level, ", ".join(reasons[:3])

def check_dragon_tiger(code, date=None):
    """检查龙虎榜 (当日是否上榜)"""
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=0.{code}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55&klt=1&lmt=1"
        r = json.loads(urllib.request.urlopen(urllib.request.Request(url,
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8).read())
        if r.get("data",{}).get("klines"):
            k = r["data"]["klines"][0].split(",")
            main_in = float(k[1])
            main_out = float(k[3])
            net = main_in - main_out
            
            if net > 1e8: return True, f"主力净买{net/1e8:.1f}亿"
            elif net > 5e7: return True, f"主力净买{net/1e7:.0f}千万"
            elif net > 1e7: return True, "主力小幅净买"
    except: pass
    return False, ""

def limit_up_analysis(code, name, chg, turnover, board_type=""):
    """涨停板分析"""
    if chg < 9.5: return ""
    
    # 封板时间估算 (基于换手率)
    if turnover < 3: return "💎 一字板(极强)"
    elif turnover < 8: return "🥇 早盘封板(强)"
    elif turnover < 15: return "🥈 盘中封板"
    else: return "🥉 烂板(次日风险)"

def short_term_scan(stocks_data):
    """
    短线+游资 综合扫描
    
    stocks_data: [{"code","name","chg","turnover","pe","price"},...]
    返回: 排序后的短线标的
    """
    results = []
    
    for s in stocks_data:
        code = s["code"]; name = s["name"]
        chg = s["chg"]; turnover = s.get("turnover",0)
        
        # 游资检测
        hm_score, hm_level, hm_reason = detect_hot_money(code, chg, turnover)
        
        # 龙虎榜检测
        on_board, board_info = check_dragon_tiger(code)
        
        # 涨停分析
        limit_info = limit_up_analysis(code, name, chg, turnover) if chg >= 9.5 else ""
        
        if hm_score >= 20 or on_board:
            results.append({
                "code": code, "name": name,
                "chg": chg, "turnover": turnover,
                "hm_score": hm_score, "hm_level": hm_level,
                "hm_reason": hm_reason,
                "dragon_tiger": on_board,
                "board_info": board_info,
                "limit_info": limit_info,
                "pe": s.get("pe",0), "price": s.get("price",0)
            })
    
    results.sort(key=lambda x: x["hm_score"], reverse=True)
    return results

def generate_scan_report():
    """短线+游资 扫描报告"""
    from pipeline.fetcher import fetch
    import urllib.request, ssl, http.cookiejar, json
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # 获取雪球热榜
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try:
        opener.open(urllib.request.Request("https://xueqiu.com/",
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8)
        r = json.loads(opener.open(urllib.request.Request(
            "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=20&_type=12&type=12",
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8).read())
    except: return "API限流"
    
    # 收集数据
    stocks = []
    for item in r.get("data",{}).get("items",[]):
        code = str(item.get("code","")).replace("SH","").replace("SZ","")
        if len(code) != 6 or code.startswith(("300","301","688","8","4")): continue
        if "ST" in item.get("name",""): continue
        
        d = fetch(code, full=False)
        if "error" in d: continue
        stocks.append({"code":code,"name":d["name"],"chg":d["chg"],
            "turnover":d.get("turnover",0),"pe":d.get("pe",0),"price":d["price"]})
    
    # 短线扫描
    results = short_term_scan(stocks)
    
    lines = ["🎯 短线+游资扫描"]
    for r in results[:8]:
        tags = []
        if r["dragon_tiger"]: tags.append("🐉龙虎榜")
        if r["limit_info"]: tags.append(r["limit_info"])
        if r["hm_level"]: tags.append(r["hm_level"])
        
        line = f"  {r['name']:<6} {r['code']} {r['chg']:+.1f}% 换手{r['turnover']:.1f}% 游资{r['hm_score']}分"
        if tags: line += f" {' '.join(tags)}"
        lines.append(line)
    
    return "\n".join(lines) if results else "无短线标的"

if __name__ == "__main__":
    print(generate_scan_report())
