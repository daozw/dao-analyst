#!/usr/bin/env python3
"""盘前新闻简报 V2 — 实时财经新闻 + 利好/利空标注 + 板块映射"""
import json, os, re, sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ═══════════════════════════════════════
# 利好/利空关键词 → (板块, 方向, 权重)
# ═══════════════════════════════════════
SIGNAL_RULES = [
    # === 政策利好 ===
    (r"国常会.*(?:加快|推进|支持|鼓励)", "政策受益", "利好", 3),
    (r"(?:降准|降息|LPR下调|MLF下调|逆回购|放水|宽松)", "大金融/地产", "利好", 3),
    (r"(?:国务院|发改委|工信部).*(?:支持|鼓励|加快|推进)", "政策受益", "利好", 2),
    (r"证监会.*(?:改革|开放|注册制|分红|回购|长期资金)", "证券/银行", "利好", 2),
    
    # === 行业利好 ===
    (r"(?:人工智能|\bAI\b|大模型|ChatGPT|GPT-|Claude|DeepSeek|智算)", "AI/信创", "利好", 3),
    (r"(?:算力|数据中心|GPU|英伟达|NVIDIA|芯片|半导体|光刻|集成电路|chip)", "芯片/算力", "利好", 3),
    (r"(?:机器人|具身智能|人形机器人|Figure\\s+AI|特斯拉.*机器人)", "机器人/智造", "利好", 2),
    (r"(?:低空经济|飞行汽车|无人机|eVTOL|空管)", "低空经济", "利好", 2),
    (r"(?:新能源.*政策|光伏.*补贴|风电.*规划|储能.*支持|氢能)", "新能源/电力", "利好", 2),
    (r"(?:固态电池|钠电池|磷酸铁锂|电池.*突破)", "新能车/电池", "利好", 2),
    (r"(?:新能源汽车.*销量|电动车.*增长|充电桩|换电)", "新能车/汽车", "利好", 2),
    (r"(?:消费.*补贴|以旧换新|消费券|内需|促消费)", "消费/家电", "利好", 2),
    (r"(?:房地产.*(?:放松|松绑|取消限购|降低首付|契税|保障房))", "地产/建筑", "利好", 2),
    (r"(?:基建.*投资|专项债|重大项目|新基建|水利)", "基建/建材", "利好", 2),
    (r"(?:电力改革|电价.*上调|电网.*投资|特高压)", "电力/电网", "利好", 2),
    (r"(?:军工.*订单|国防.*预算|航天.*发射|卫星)", "军工/航天", "利好", 2),
    (r"(?:医药.*创新|创新药.*获批|中药.*利好|集采.*(?:缓和|结束))", "医药", "利好", 2),
    (r"(?:数字经济|数据要素|数据资产|数字人民币)", "数字经济", "利好", 2),
    (r"(?:6G|5G.*(?:商用|建设)|卫星互联网|商业航天)", "通信/航天", "利好", 2),
    (r"(?:稀土.*(?:管制|涨价|出口限制|反制))", "稀土/有色", "利好", 2),
    (r"(?:航运.*涨价|BDI.*上涨|运价.*上调)", "航运/港口", "利好", 2),
    
    # === 行业利空 ===
    (r"(?:反垄断.*调查|立案.*调查|约谈|处罚|整改.*(?:平台|互联网))", "互联网/平台", "利空", 3),
    (r"(?:集采.*降价|医保.*控费|带量采购)", "医药", "利空", 2),
    (r"(?:房地产税|房产税|楼市.*调控.*加码|限购.*升级)", "地产", "利空", 2),
    (r"(?:新能源.*过剩|光伏.*过剩|产能过剩|价格战)", "光伏/新能车", "利空", 2),
    (r"(?:芯片.*限制|出口管制.*芯片|制裁.*半导体|实体清单)", "芯片/半导体", "利空", 2),
    (r"(?:关税.*加征|贸易.*摩擦|贸易战|反倾销)", "出口/外贸", "利空", 2),
    (r"(?:煤炭.*限价|煤价.*下跌|控煤)", "煤炭", "利空", 2),
    (r"(?:原油.*下跌|油价.*暴跌|OPEC.*增产)", "石油/化工", "利空", 1),
    (r"(?:钢材.*下跌|铁矿石.*下跌|钢价.*下行)", "钢铁", "利空", 1),
    (r"(?:猪肉.*下跌|猪价.*下行|生猪.*过剩)", "农牧", "利空", 1),
    
    # === 异动公告 ===（涨幅异动+公司澄清+停牌核查）
    (r"(?:异常波动|涨幅异动|交易异动|股价异动|严重异常)", "📢异动公告", "提示", 3),
    (r"(?:停牌核查|停牌.*公告|临时停牌)", "📢异动公告", "提示", 2),
    (r"(?:澄清公告|澄清.*传闻|辟谣|未涉及.*业务|不涉及)", "📢异动公告", "提示", 2),
    (r"(?:连续.*涨停|连板|\d+连板|\d+个涨停)", "📢异动公告", "提示", 2),
    (r"(?:风险提示.*公告|股票交易.*风险提示)", "📢异动公告", "提示", 2),
    
    # === 个股利空（仅保留减持+业绩暴雷，退市不推送）===
    (r"(?:大股东.*减持|高管.*减持|控股股东.*减持|%以上股东.*减持)", "📢异动公告", "提示", 1),
    (r"(?:减持.*计划|拟减持|减持.*完毕)", "📢异动公告", "提示", 1),
    (r"(?:业绩.*预告.*(?:亏损|下降|下滑)|预亏|业绩.*变脸)", "📢异动公告", "提示", 1),
    
    # === 宏观利好 ===
    (r"(?:GDP.*(?:超预期|增长|回升)|PMI.*(?:回升|扩张))", "宏观", "利好", 2),
    (r"(?:社融.*(?:超预期|大增)|信贷.*增长|M2.*增长)", "宏观/金融", "利好", 2),
    (r"(?:出口.*(?:增长|超预期)|贸易顺差.*扩大)", "出口", "利好", 2),
    (r"(?:人民币.*升值|汇率.*走强|人民币.*反弹)", "宏观/金融", "利好", 2),
    (r"(?:外资.*流入|北向.*净买入|北上.*加仓)", "宏观/金融", "利好", 2),
    (r"(?:美联储.*降息|美国.*降息|Fed.*cut)", "宏观/全球", "利好", 3),
    
    # === 宏观利空 ===
    (r"(?:美联储.*加息|美国.*加息|Fed.*hike)", "宏观/全球", "利空", 2),
    (r"(?:人民币.*贬值|汇率.*走弱|人民币.*下跌)", "宏观/金融", "利空", 2),
    (r"(?:外资.*流出|北向.*净卖出|北上.*减仓)", "宏观/金融", "利空", 2),
    (r"(?:地缘.*冲突|战争|军事.*冲突|导弹.*袭击)", "宏观/避险", "利空", 3),
    (r"(?:疫情.*反弹|病毒.*变异|封锁|封城)", "宏观/消费", "利空", 2),
]

def fetch_em_news():
    """从东方财富获取实时财经新闻"""
    try:
        import akshare as ak
        df = ak.stock_info_global_em()
        news = []
        for _, row in df.iterrows():
            news.append({
                "title": str(row.get("标题", "")),
                "summary": str(row.get("摘要", ""))[:300],
                "url": str(row.get("链接", ""))
            })
            if len(news) >= 100:
                break
        return news
    except Exception as e:
        return [{"title": f"新闻获取异常: {e}", "summary": "", "url": ""}]

def analyze_news_item(title, summary=""):
    """分析单条新闻: 返回 (板块, 方向, 权重, 匹配词)"""
    text = title + " " + summary
    for pattern, sector, direction, weight in SIGNAL_RULES:
        m = re.search(pattern, text)
        if m:
            return (sector, direction, weight, m.group(0)[:30])
    return None

def classify_and_tag(news_list):
    """分类+标注所有新闻"""
    tagged = []
    stats = defaultdict(lambda: defaultdict(int, {"利好": 0, "利空": 0, "提示": 0, "items": []}))
    
    for news in news_list:
        result = analyze_news_item(news["title"], news.get("summary", ""))
        if result:
            sector, direction, weight, keyword = result
            news["sector"] = sector
            news["direction"] = direction
            news["weight"] = weight
            news["keyword"] = keyword
            stats[sector][direction] += weight
            stats[sector]["items"].append(news)
            tagged.append(news)
        else:
            # 未匹配的归入其他
            news["sector"] = "其他"
            news["direction"] = "中性"
            news["weight"] = 0
    
    return tagged, stats

def generate_brief(tagged_news, stats):
    """生成完整简报"""
    lines = []
    lines.append("📰 今日新闻与政策解读")
    lines.append("═" * 40)
    
    # ═══ 板块影响总览 ═══
    lines.append("\n📊 【板块影响总览】")
    lines.append("─" * 30)
    
    # 利好板块排序
    bullish = [(sec, data) for sec, data in stats.items() 
               if data["利好"] > data["利空"] and sec not in ("其他", "个股风险")]
    bullish.sort(key=lambda x: -(x[1]["利好"] - x[1]["利空"]))
    
    if bullish:
        lines.append("  🟢 利好板块:")
        for sec, data in bullish[:8]:
            net = data["利好"] - data["利空"]
            bar = "█" * min(net, 5)
            lines.append(f"    {bar} {sec} (利好+{data['利好']})")
    
    # 利空板块排序
    bearish = [(sec, data) for sec, data in stats.items() 
               if data["利空"] > data["利好"] and sec not in ("其他", "个股风险")]
    bearish.sort(key=lambda x: -(x[1]["利空"] - x[1]["利好"]))
    
    if bearish:
        lines.append("\n  🔴 利空板块:")
        for sec, data in bearish[:5]:
            net = data["利空"] - data["利好"]
            bar = "█" * min(net, 5)
            lines.append(f"    {bar} {sec} (利空-{data['利空']})")
    
    # ═══ 重点新闻 ═══
    lines.append(f"\n📋 【重点新闻】({len(tagged_news)}条)")
    lines.append("─" * 30)
    
    # 按权重排序：利好在前，利空在后
    bullish_news = [n for n in tagged_news if n.get("direction") == "利好"]
    bearish_news = [n for n in tagged_news if n.get("direction") == "利空"]
    alert_news = [n for n in tagged_news if n.get("direction") == "提示"]
    neutral_news = [n for n in tagged_news if n.get("direction") not in ("利好", "利空", "提示")]
    
    bullish_news.sort(key=lambda x: -x.get("weight", 0))
    bearish_news.sort(key=lambda x: -x.get("weight", 0))
    alert_news.sort(key=lambda x: -x.get("weight", 0))
    
    if bullish_news:
        lines.append("\n  🟢 利好消息:")
        for n in bullish_news[:12]:
            tag = f"[{n.get('sector','?')}]"
            lines.append(f"  {tag} {n['title'][:70]}")
    
    if bearish_news:
        lines.append(f"\n  🔴 利空消息:")
        for n in bearish_news[:8]:
            tag = f"[{n.get('sector','?')}]"
            lines.append(f"  {tag} {n['title'][:70]}")
    
    if alert_news:
        lines.append(f"\n  📢 【异动公告/澄清】({len(alert_news)}条)")
        for n in alert_news[:10]:
            tag = f"[{n.get('sector','?')}]"
            lines.append(f"  {tag} {n['title'][:70]}")
    
    if neutral_news:
        lines.append(f"\n  ⚪ 其他要闻 ({len(neutral_news)}条)")
        for n in neutral_news[:5]:
            lines.append(f"  • {n['title'][:70]}")
    
    # ═══ 操作建议 ═══
    lines.append(f"\n💡 【操作建议】")
    lines.append("─" * 30)
    
    if bullish:
        top3 = [sec for sec, _ in bullish[:3]]
        lines.append(f"  ✅ 关注: {', '.join(top3)}")
    if bearish:
        top3 = [sec for sec, _ in bearish[:3]]
        lines.append(f"  ⚠️ 规避: {', '.join(top3)}")
    
    # 异动公告统计
    alert_items = stats.get("📢异动公告", {}).get("items", [])
    if alert_items:
        lines.append(f"  📢 异动公告: {len(alert_items)}条, 详见下方")
    
    return "\n".join(lines)

def format_sector_flow():
    """板块资金流向"""
    try:
        import akshare as ak
        df = ak.stock_sector_fund_flow_rank(indicator="今日")
        lines = ["\n💰 【板块资金TOP5】"]
        for _, row in df.head(5).iterrows():
            name = str(row.get("名称", ""))
            chg = float(row.get("涨跌幅", 0) or 0)
            flow = float(row.get("主力净流入-净额", 0) or 0) / 1e8
            arrow = "🔴" if flow > 0 else "🟢"
            lines.append(f"  {arrow} {name:<8} {chg:+.1f}% 主力{flow:+.1f}亿")
        return "\n".join(lines) if len(lines) > 1 else "\n💰 【板块资金】暂无交易数据"
    except:
        return "\n💰 【板块资金】暂无交易数据"

def generate_full_brief():
    """主入口"""
    print("📡 获取实时新闻...")
    news = fetch_em_news()
    print(f"  {len(news)} 条")
    
    print("🔍 分析利好/利空...")
    tagged, stats = classify_and_tag(news)
    matched = len([n for n in tagged if n.get("direction") != "中性"])
    print(f"  标注 {matched} 条 (利好{sum(1 for n in tagged if n.get('direction')=='利好')} 利空{sum(1 for n in tagged if n.get('direction')=='利空')})")
    
    brief = generate_brief(tagged, stats)
    brief += format_sector_flow()
    
    return brief

if __name__ == "__main__":
    print(generate_full_brief())
