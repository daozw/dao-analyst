#!/usr/bin/env python3
"""
热点板块+政策方向筛选器
优先选: 热门板块 + 政策支撑 + 市场热度高的标的
"""
import urllib.request, json, ssl
ssl._create_default_https_context = ssl._create_unverified_context

# 2026年政策支撑方向
POLICY_SECTORS = {
    "新能源": ["电力","光伏","风电","储能","电网","核能","氢能"],
    "人工智能": ["AI","算力","半导体","芯片","通信","光模块"],
    "新质生产力": ["自动化","机器人","智能","工业母机","高端装备"],
    "消费复苏": ["食品","白酒","家电","汽车","零售","旅游"],
    "数字经济": ["数据","信创","软件","云计算","大数据"],
    "低空经济": ["飞行","无人机","航空","航天"],
}

def fetch_hot_sectors():
    """实时热门板块"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=15&po=1&np=1&fields=f12,f14,f3,f62&fid=f3&fs=m:90+t:2&fltt=2"
        data = json.loads(urllib.request.urlopen(urllib.request.Request(url,
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8).read())
        sectors = []
        for item in data["data"]["diff"]:
            sectors.append({
                "name": item["f14"], "chg": item["f3"],
                "inflow": (item.get("f62",0) or 0) / 1e8
            })
        return sectors
    except:
        return []

def get_policy_support(sector_name):
    """检查板块是否有政策支撑"""
    for policy, tags in POLICY_SECTORS.items():
        if any(t in sector_name for t in tags):
            return policy
    return None

def score_stock(code, name, stock_chg, stock_pe, hot_sectors):
    """
    综合评分: 板块热度 + 政策支撑 + 市场热度
    
    hot_sectors: fetch_hot_sectors() 返回值
    返回: (score, reasons)
    """
    score = 0
    reasons = []
    
    # 1. 板块热度 (0-30分)
    # 个股需要先知道属于哪个板块——这里用简化逻辑:
    # 如果个股涨幅和某个热门板块涨幅方向一致，加分
    for sector in hot_sectors[:5]:
        if stock_chg * sector["chg"] > 0:  # 同方向
            score += min(abs(sector["chg"]) * 2, 10)
    
    # 2. 政策支撑 (0-20分)
    policy_matched = []
    for policy, tags in POLICY_SECTORS.items():
        if any(t in name for t in tags):
            policy_matched.append(policy)
    if policy_matched:
        score += 20
        reasons.append(f"🎯政策: {','.join(policy_matched[:2])}")
    
    # 3. PE估值 (0-20分)
    if 0 < stock_pe < 20: score += 20; reasons.append("PE低估")
    elif 0 < stock_pe < 40: score += 15; reasons.append("PE合理")
    elif 0 < stock_pe < 60: score += 10
    elif 0 < stock_pe < 100: score += 5
    
    # 4. 涨幅动量 (0-15分)
    if 1.5 <= stock_chg <= 5: score += 15; reasons.append("温和上涨")
    elif 0 < stock_chg < 1.5: score += 8
    elif stock_chg > 5: score += 5; reasons.append("涨幅偏高")
    
    # 5. 热门板块共振 (0-15分)
    top_sector = hot_sectors[0]["name"] if hot_sectors else ""
    if any(t in (name or "") for t in ["电力","能源","科技","电子","汽车"]):
        score += 15; reasons.append(f"板块共振")
    
    return score, reasons

def hot_sector_scan():
    """热点板块+政策 综合扫描"""
    sectors = fetch_hot_sectors()
    if not sectors:
        return {"error": "API限流(盘后正常)", "sectors": []}
    
    result = {"sectors": [], "policy_hot": []}
    
    for i, s in enumerate(sectors[:10], 1):
        policy = get_policy_support(s["name"])
        score = s["chg"] * 3 + s["inflow"] * 2
        
        item = {"rank": i, "name": s["name"], "chg": s["chg"], 
                "inflow": s["inflow"], "policy": policy, "score": score}
        result["sectors"].append(item)
        
        if policy:
            result["policy_hot"].append(item)
    
    return result

if __name__ == "__main__":
    r = hot_sector_scan()
    if "error" in r:
        print(f"⚠️ {r['error']}")
    else:
        print("🔥 热点板块 × 政策方向")
        for s in r["sectors"][:8]:
            pol_tag = f" 🎯{s['policy']}" if s["policy"] else ""
            print(f"  {s['name']:<10} {s['chg']:>+4.1f}% {s['inflow']:>+5.1f}亿 {s['score']:.0f}分{pol_tag}")
        
        if r["policy_hot"]:
            print(f"\n📋 政策支撑+热门共振:")
            for s in r["policy_hot"]:
                print(f"  🎯 {s['name']} — {s['policy']}")
