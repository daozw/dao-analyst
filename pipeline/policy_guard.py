#!/usr/bin/env python3
"""政策市适配 — 关键词→板块映射 + 措辞力度评估"""
import json, os, re
from datetime import datetime

# 政策关键词 → 受益板块映射
POLICY_MAP = {
    # 科技
    "人工智能|AI|大模型|算力|智算": {"板块": ["信息技术","科创50","科技100"], "力度": 3},
    "半导体|芯片|集成电路|光刻": {"板块": ["科创50","科技100"], "力度": 3},
    "机器人|人形机器人|具身智能": {"板块": ["科技100","汽车"], "力度": 3},
    "低空经济|飞行汽车|无人机|eVTOL": {"板块": ["科技100","军工"], "力度": 2},
    "数字经济|数据要素|数据资产": {"板块": ["信息技术","传媒"], "力度": 2},
    "6G|卫星互联网|商业航天|星链": {"板块": ["信息技术","军工"], "力度": 2},
    
    # 新能源
    "新能源汽车|电动车|充电桩|换电": {"板块": ["新能车","汽车","有色"], "力度": 2},
    "光伏|太阳能|储能|钙钛矿": {"板块": ["电力","有色"], "力度": 2},
    "风电|核能|氢能|清洁能源": {"板块": ["电力"], "力度": 2},
    "固态电池|钠电池|磷酸铁锂": {"板块": ["新能车","有色"], "力度": 2},
    
    # 消费
    "消费|内需|以旧换新|消费券|补贴": {"板块": ["消费","家电","汽车"], "力度": 2},
    "房地产|楼市|房贷|契税|保障房": {"板块": ["地产","建筑","钢铁"], "力度": 2},
    
    # 金融
    "降准|降息|LPR|MLF|逆回购|社融": {"板块": ["证券","银行"], "力度": 2},
    "资本市场|注册制|退市|分红|回购": {"板块": ["证券"], "力度": 2},
    "险资|养老金|社保基金|长期资金": {"板块": ["银行","证券"], "力度": 2},
    
    # 特殊措辞 → 力度加成
    "大力|加快|积极|着力|加大": {"加成": 1, "desc": "积极措辞+1"},
    "坚决|严格|严禁|遏制|打击": {"加成": -2, "desc": "收紧措辞-2"},
    "适度|稳健|平稳|合理": {"加成": 0, "desc": "中性措辞"},
}

# 已知利空关键词
BEARISH_KEYWORDS = {
    "反垄断|调查|立案|处罚|约谈|整改": {"level": "fatal", "desc": "监管打击"},
    "退市风险|暂停上市|终止上市": {"level": "fatal", "desc": "退市风险"},
    "减持|套现|大宗交易": {"level": "high", "desc": "股东减持"},
    "商誉减值|计提|亏损|预亏": {"level": "high", "desc": "业绩暴雷"},
    "问询函|关注函|监管函": {"level": "high", "desc": "监管关注"},
}

def scan_policy(text):
    """扫描政策文本,提取受益板块+力度"""
    results = {"sectors": {}, "tone": 0, "keywords": []}
    
    for pattern, info in POLICY_MAP.items():
        matches = re.findall(pattern, text)
        if matches:
            if "板块" in info:
                for sector in info["板块"]:
                    results["sectors"][sector] = results["sectors"].get(sector, 0) + info.get("力度", 1)
            if "加成" in info:
                results["tone"] += info.get("加成", 0)
                results["keywords"].append(f"{matches[0]}({info.get('desc','')})")
    
    # 利空扫描
    results["bearish"] = []
    for pattern, info in BEARISH_KEYWORDS.items():
        if re.search(pattern, text):
            results["bearish"].append(info)
    
    return results

def get_policy_bonus(code):
    """从缓存的政策分析中获取板块加分"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pf = os.path.join(base, "data", "state", "policy_scan.json")
        if not os.path.exists(pf):
            return 0, ""
        
        policy = json.load(open(pf))
        sectors_boosted = policy.get("sectors", {})
        
        from pipeline.risk_controls import get_sector
        sec = get_sector(code)
        
        # 模糊匹配板块
        for policy_sec, boost in sectors_boosted.items():
            if policy_sec in sec or sec in policy_sec:
                return boost * 2, f"政策利好{policy_sec}(+{boost*2})"
    except:
        pass
    return 0, ""

if __name__ == '__main__':
    # 测试: 模拟一条政策新闻
    test = "国务院常务会议提出，要加快发展人工智能，大力推动算力基础设施建设，积极发展低空经济"
    r = scan_policy(test)
    
    print(f"📜 政策扫描: \"{test[:50]}...\"")
    print(f"  基调: {r['tone']:+d}")
    print(f"  受益板块: {dict(sorted(r['sectors'].items(), key=lambda x:-x[1]))}")
    for kw in r['keywords']:
        print(f"  → {kw}")
    if r['bearish']:
        print(f"  ⚠️ 风险: {r['bearish']}")
