#!/usr/bin/env python3
"""板块轮动检测 — 基于腾讯板块指数"""
import urllib.request, ssl, json, os
from datetime import datetime
from collections import OrderedDict

ssl._create_default_https_context = ssl._create_unverified_context

# 腾讯板块代码 (pt01801xxx 格式)
# 真实指数代码(名称=API返回名称)
SECTORS = {
    "白酒": "sz399997", "军工": "sz399959", "医药": "sz399933",
    "证券": "sz399975", "银行": "sz399986", "新能车": "sz399976",
    "传媒": "sz399971", "消费": "sz399932", "信息技术": "sz399935",
    "有色": "sz399395", "煤炭": "sz399998", "汽车": "sz399432",
    "家电": "sz399396", "环保": "sz399958", "电力": "sz399438",
    "科创50": "sh000688", "科技100": "sz399608",
    "地产": "sz399393", "钢铁": "sz399440", "建筑": "sz399359",
}

def fetch_sector_chg():
    """逐个获取板块涨跌幅"""
    results = {}
    for name, scode in SECTORS.items():
        try:
            raw = urllib.request.urlopen(
                f'https://qt.gtimg.cn/q={scode}', timeout=3
            ).read().decode('gbk')
            if 'none_match' in raw or '="' not in raw:
                continue
            header, data_part = raw.split('="', 1)
            d = data_part.rstrip('";\n').split('~')
            if len(d) > 32 and d[32]:
                results[name] = {
                    "code": scode, "chg": round(float(d[32]), 2),
                    "price": float(d[3]) if len(d) > 3 and d[3] else 0,
                }
        except:
            pass
    return results

def rank_sectors():
    """板块强弱排名"""
    data = fetch_sector_chg()
    if not data:
        return []
    
    ranked = sorted(data.items(), key=lambda x: x[1]["chg"], reverse=True)
    return ranked

def detect_rotation(days=3):
    """检测板块轮动: 最近N天最强/最弱板块变化"""
    # 简化版: 只检测当天
    ranked = rank_sectors()
    
    strong = ranked[:5]  # 今天最强5个板块
    weak = ranked[-5:]   # 今天最弱5个板块
    
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "top_sectors": [(n, d["chg"]) for n, d in strong],
        "bottom_sectors": [(n, d["chg"]) for n, d in weak],
        "total": len(ranked),
        "market_breadth": sum(1 for _, d in ranked if d["chg"] > 0)
    }
    
    # 保存到状态文件
    state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "state", "sector_rotation.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result

def get_sector_bonus(code):
    """根据股票所属板块给予加分: 如果板块今天强→+分"""
    # 获取股票所属板块
    from pipeline.risk_controls import get_sector
    sec = get_sector(code)
    
    # 读取板块轮动数据
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sf = os.path.join(base, "data", "state", "sector_rotation.json")
    if not os.path.exists(sf):
        return 0, "无板块数据"
    
    data = json.load(open(sf))
    top = [n for n, _ in data.get("top_sectors", [])]
    
    if sec in top[:3]:
        return 8, f"板块领涨(+8)"
    elif sec in top[:5]:
        return 4, f"板块强势(+4)"
    elif sec in [n for n, _ in data.get("bottom_sectors", [])[:3]]:
        return -5, f"板块领跌(-5)"
    
    return 0, "板块中性"

if __name__ == '__main__':
    r = detect_rotation()
    print(f"\n📊 板块轮动 {r['date']}")
    print(f"  上涨板块: {r['market_breadth']}/{r['total']}")
    print(f"\n🔥 最强:")
    for name, chg in r['top_sectors'][:8]:
        print(f"  {name}: {chg:+.1f}%")
    print(f"\n❄️ 最弱:")
    for name, chg in r['bottom_sectors'][:5]:
        print(f"  {name}: {chg:+.1f}%")
