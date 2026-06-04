#!/usr/bin/env python3
"""
三平台热度聚合 V1.0
东方财富人气榜 + 同花顺热榜 + 雪球热门 — 综合评分
"""
import urllib.request, json, ssl, re, os, sys
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url, referer="", mobile=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU OS 16_0 like Mac OS X)" if mobile 
                      else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json, text/plain, */*",
    }
    if referer: headers["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="replace")
    except:
        return None

# ═══════════════════════════════════
# 1. 东方财富
# ═══════════════════════════════════
def fetch_eastmoney():
    """东方财富人气榜"""
    results = []
    data = fetch(
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=20&po=1&np=1&fields=f12,f14,f3,f2,f20&"
        "fid=f10&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fltt=2"
    )
    if data:
        d = json.loads(data)
        for item in d.get("data",{}).get("diff",[])[:20]:
            results.append({
                "code": item.get("f12",""), "name": item.get("f14",""),
                "chg": item.get("f3",0) or 0, "price": item.get("f2",0) or 0,
                "mkt": (item.get("f20",0) or 0)/1e8, "source": "东财人气"
            })
    return results

# ═══════════════════════════════════
# 2. 同花顺
# ═══════════════════════════════════
def fetch_10jqka():
    """同花顺热度榜"""
    results = []
    
    # 尝试多个端点
    endpoints = [
        # 热度排名
        ("https://dq.10jqka.com.cn/fuyao/hotstock_v2/rank/hot/type/1/field/concept/order/desc/page/1/ajax/1/free/1/",
         "list", {"code": "code", "name": "name", "hot": "hot"}),
        # 涨幅关注
        ("https://dq.10jqka.com.cn/fuyao/hotstock_v2/rank/rise/type/1/order/desc/page/1/ajax/1/free/1/",
         "list", {"code": "code", "name": "name"}),
    ]
    
    for url, list_key, field_map in endpoints:
        raw = fetch(url, referer="https://www.10jqka.com.cn/", mobile=True)
        if not raw:
            continue
        try:
            d = json.loads(raw)
            items = d.get("data",{}).get(list_key, []) or d.get(list_key, [])
            for item in items[:20]:
                code = str(item.get(field_map["code"],""))
                name = item.get(field_map["name"],"")
                hot_val = item.get(field_map.get("hot",""), 0)
                if code and name:
                    results.append({
                        "code": code, "name": name,
                        "chg": 0, "price": 0, "mkt": 0,
                        "hot_val": hot_val, "source": "同花顺"
                    })
            if results:
                break
        except:
            continue
    
    return results

# ═══════════════════════════════════
# 3. 雪球
# ═══════════════════════════════════
def fetch_xueqiu():
    """雪球热门股票"""
    results = []
    
    # 雪球行情API
    raw = fetch("https://xueqiu.com/", referer="https://xueqiu.com/")
    if not raw:
        return results
    
    # 方法1: 从首页提取热门股票
    stock_pattern = re.findall(r'"symbol":"(SH\d+|SZ\d+)".*?"name":"([^"]+)".*?"percent":(-?[\d.]+)', raw)
    for symbol, name, chg_str in stock_pattern[:15]:
        code = symbol.replace("SH","").replace("SZ","")
        results.append({
            "code": code, "name": name,
            "chg": float(chg_str) if chg_str else 0,
            "price": 0, "mkt": 0, "source": "雪球"
        })
    
    # 方法2: 如果方法1失败，尝试搜索热股API
    if not results:
        raw2 = fetch(
            "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=20&_type=11&type=11",
            referer="https://xueqiu.com/"
        )
        if raw2:
            try:
                d = json.loads(raw2)
                for item in d.get("data",{}).get("items",[])[:20]:
                    code = str(item.get("code","")).replace("SH","").replace("SZ","")
                    name = item.get("name","")
                    if code and name:
                        results.append({
                            "code": code, "name": name,
                            "chg": item.get("percent",0) or 0,
                            "price": 0, "mkt": 0, "source": "雪球"
                        })
            except:
                pass
    
    return results

# ═══════════════════════════════════
# 4. 综合聚合
# ═══════════════════════════════════
def aggregate():
    """三平台数据聚合并打分"""
    all_data = {}
    
    # 收集各平台数据
    sources = [
        ("eastmoney", fetch_eastmoney()),
        ("10jqka", fetch_10jqka()),
        ("xueqiu", fetch_xueqiu()),
    ]
    
    platform_stats = {}
    for pname, items in sources:
        platform_stats[pname] = len(items)
        for i, item in enumerate(items):
            code = item["code"]
            if code not in all_data:
                all_data[code] = {
                    "name": item["name"], "code": code,
                    "chg": item.get("chg",0), "mkt": item.get("mkt",0),
                    "platforms": [], "score": 0
                }
            # 分数: 东财排名(20-i) + 同花顺(15分) + 雪球(15分)
            if pname == "eastmoney":
                all_data[code]["score"] += (20 - i)
                all_data[code]["platforms"].append("东财")
            elif pname == "10jqka":
                all_data[code]["score"] += 15
                all_data[code]["platforms"].append("同花顺")
            elif pname == "xueqiu":
                all_data[code]["score"] += 15
                all_data[code]["platforms"].append("雪球")
    
    # 排序
    ranked = sorted(all_data.values(), key=lambda x: x["score"], reverse=True)
    return ranked, platform_stats

# ═══════════════════════════════════
# 5. 输出
# ═══════════════════════════════════
def display():
    ranked, pstats = aggregate()
    now = datetime.now()
    
    print("=" * 60)
    print(f"  🔥 三平台热度聚合")
    print(f"  📅 {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  📡 东财({pstats['eastmoney']}条) 同花顺({pstats['10jqka']}条) 雪球({pstats['xueqiu']}条)")
    print("=" * 60)
    
    # TOP15 综合榜
    print(f"\n👑 综合热度 TOP15")
    print(f"  {'排名':<4} {'名称':<8} {'代码':<8} {'涨跌':>6} {'综合分':>5} {'共振平台'}")
    print(f"  {'-'*46}")
    for i, s in enumerate(ranked[:15], 1):
        platforms = "+".join(s["platforms"])
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i:>2}."
        print(f"  {medal} {s['name']:<8} {s['code']:<8} {s['chg']:>+5.1f}% {s['score']:>4}分  [{platforms}]")
    
    # 多平台共振
    multi = [s for s in ranked if len(s["platforms"]) >= 2]
    if multi:
        print(f"\n🎯 多平台共振 ({len(multi)}只 ≥2平台):")
        for s in multi[:8]:
            print(f"  • {s['name']:<8} {s['code']} {s['chg']:>+5.1f}% [{'+'.join(s['platforms'])}]")
    
    # 三平台全上榜
    triple = [s for s in ranked if len(s["platforms"]) >= 3]
    if triple:
        print(f"\n💎 三平台全上榜 ({len(triple)}只):")
        for s in triple:
            print(f"  💎 {s['name']:<8} {s['code']} {s['chg']:>+5.1f}%  {s['score']}分")
    
    # 主板过滤
    main_board = [s for s in ranked[:30] if not s["code"].startswith(("300","688","8","4"))]
    if main_board:
        print(f"\n🏠 主板热度 TOP10:")
        for i, s in enumerate(main_board[:10], 1):
            print(f"  {i:>2}. {s['name']:<8} {s['code']} {s['chg']:>+5.1f}% [{'+'.join(s['platforms'])}]")
    
    # 数据来源状态
    missing = [k for k, v in pstats.items() if v == 0]
    if missing:
        print(f"\n⚠️ 未获取到数据的平台: {', '.join(missing)}")
        print(f"   (非交易日属正常现象，开盘后恢复)")
    
    return ranked

if __name__ == "__main__":
    display()
