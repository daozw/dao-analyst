"""管道阶段2: 加权信号 V2.0 — 趋势权重高,确定性优先"""
import math

def analyze(d, atr_mult=2.0):
    """加权评分 0-100: 趋势40 + 量能25 + 位置20 + 估值10 + 资金5"""
    p = d["price"]; chg = d["chg"]; pe = d.get("pe", 0)
    ma5 = d.get("ma5", p); ma20 = d.get("ma20", p)
    atr = d.get("atr", p * 0.03)
    fund = d.get("fund")
    high = d.get("high", p); low = d.get("low", p)
    pre_close = d.get("pre_close", p)
    turnover = d.get("turnover", 0)
    
    score = 0
    signals = []
    
    # ─── 趋势 (0-40分) ───
    trend_pts = 0
    if p > ma5:
        trend_pts += 15
        signals.append({"label": "MA5", "val": f"¥{ma5:.2f}", "tag": "短多+15", "lv": "g"})
    else:
        trend_pts -= 10
        signals.append({"label": "MA5", "val": f"¥{ma5:.2f}", "tag": "短空-10", "lv": "r"})
    
    if p > ma20:
        trend_pts += 15
        signals.append({"label": "MA20", "val": f"¥{ma20:.2f}", "tag": "中多+15", "lv": "g"})
    else:
        trend_pts -= 5
        signals.append({"label": "MA20", "val": f"¥{ma20:.2f}", "tag": "中空-5", "lv": "y"})
    
    # MA20斜率 (用当前价与20日前比较)
    ma20_slope = (p - ma20) / ma20 * 100
    if ma20_slope > 5:
        trend_pts += 10
        signals.append({"label": "趋势强度", "val": f"+{ma20_slope:.1f}%", "tag": "强趋势+10", "lv": "g"})
    elif ma20_slope > 1:
        trend_pts += 5
        signals.append({"label": "趋势强度", "val": f"+{ma20_slope:.1f}%", "tag": "温和+5", "lv": "y"})
    elif ma20_slope < -5:
        trend_pts -= 10
        signals.append({"label": "趋势强度", "val": f"{ma20_slope:.1f}%", "tag": "弱势-10", "lv": "r"})
    else:
        signals.append({"label": "趋势强度", "val": f"{ma20_slope:.1f}%", "tag": "横盘", "lv": "n"})
    
    score += max(0, trend_pts)  # 趋势分不低于0
    
    # ─── 量能 (0-25分) ───
    vol_pts = 0
    # 日内强度: 收盘vs开盘
    if pre_close > 0:
        intraday_strength = (p - pre_close) / pre_close * 100
        if intraday_strength > 2:
            vol_pts += 10
            signals.append({"label": "日内强度", "val": f"+{intraday_strength:.1f}%", "tag": "强势+10", "lv": "g"})
        elif intraday_strength > 0:
            vol_pts += 5
            signals.append({"label": "日内强度", "val": f"+{intraday_strength:.1f}%", "tag": "收阳+5", "lv": "y"})
        elif intraday_strength > -2:
            signals.append({"label": "日内强度", "val": f"{intraday_strength:.1f}%", "tag": "微跌", "lv": "y"})
        else:
            vol_pts -= 5
            signals.append({"label": "日内强度", "val": f"{intraday_strength:.1f}%", "tag": "弱势-5", "lv": "r"})
    
    # 换手率: 活跃度
    if 2 <= turnover <= 8:
        vol_pts += 8
        signals.append({"label": "换手率", "val": f"{turnover:.1f}%", "tag": "活跃+8", "lv": "g"})
    elif 1 <= turnover < 2:
        vol_pts += 4
        signals.append({"label": "换手率", "val": f"{turnover:.1f}%", "tag": "温和+4", "lv": "y"})
    elif turnover > 15:
        vol_pts -= 3
        signals.append({"label": "换手率", "val": f"{turnover:.1f}%", "tag": "异常-3", "lv": "r"})
    else:
        signals.append({"label": "换手率", "val": f"{turnover:.1f}%", "tag": "清淡", "lv": "n"})
    
    # 量比 (从腾讯API获取, fetcher暂时没有, 用当日涨跌幅接近高位判断)
    if high > 0 and low > 0:
        day_range = (high - low) / pre_close * 100 if pre_close > 0 else 0
        close_pos = (p - low) / (high - low) if high > low else 0.5
        if close_pos > 0.7 and day_range > 3:
            vol_pts += 7
            signals.append({"label": "收盘位置", "val": f"高位{close_pos:.0%}", "tag": "强势收盘+7", "lv": "g"})
        elif close_pos < 0.3 and day_range > 3:
            vol_pts -= 5
            signals.append({"label": "收盘位置", "val": f"低位{close_pos:.0%}", "tag": "弱势收盘-5", "lv": "r"})
    
    # ─── 量价关系检测 ───
    vol_ratio = d.get('vol_ratio', 1.0)
    if chg > 1 and vol_ratio > 1.5:
        vol_pts += 8
        signals.append({"label": "量价关系", "val": f"量比{vol_ratio:.1f}x", "tag": "量增价涨+8", "lv": "g"})
    elif chg > 0 and vol_ratio > 2:
        vol_pts += 5
        signals.append({"label": "量价关系", "val": f"量比{vol_ratio:.1f}x", "tag": "放量上涨+5", "lv": "y"})
    elif chg < -1 and vol_ratio > 2:
        vol_pts -= 8
        signals.append({"label": "量价关系", "val": f"量比{vol_ratio:.1f}x", "tag": "放量下跌-8", "lv": "r"})
    elif chg < -1 and vol_ratio < 0.7:
        vol_pts += 3
        signals.append({"label": "量价关系", "val": f"量比{vol_ratio:.1f}x", "tag": "缩量止跌+3", "lv": "y"})
    elif vol_ratio > 3:
        signals.append({"label": "量价关系", "val": f"量比{vol_ratio:.1f}x", "tag": "异常放量⚠️", "lv": "y"})
    
    score += max(0, vol_pts)
    
    # ─── 位置 (0-20分) ───
    pos_pts = 0
    support = d.get("support", p * 0.95)
    resistance = d.get("resistance", p * 1.05)
    
    # 距离支撑位
    dist_to_support = (p - support) / atr if atr > 0 else 5
    dist_to_resist = (resistance - p) / atr if atr > 0 else 5
    
    if dist_to_support < 1.5:
        pos_pts += 12
        signals.append({"label": "支撑距离", "val": f"{dist_to_support:.1f}ATR", "tag": "近支撑+12", "lv": "g"})
    elif dist_to_support < 3:
        pos_pts += 6
        signals.append({"label": "支撑距离", "val": f"{dist_to_support:.1f}ATR", "tag": "适中+6", "lv": "y"})
    else:
        pos_pts -= 5
        signals.append({"label": "支撑距离", "val": f"{dist_to_support:.1f}ATR", "tag": "远离-5", "lv": "r"})
    
    if dist_to_resist > 3:
        pos_pts += 8
        signals.append({"label": "上涨空间", "val": f"{dist_to_resist:.1f}ATR", "tag": "空间大+8", "lv": "g"})
    elif dist_to_resist > 1:
        pos_pts += 3
        signals.append({"label": "上涨空间", "val": f"{dist_to_resist:.1f}ATR", "tag": "有空间+3", "lv": "y"})
    else:
        pos_pts -= 3
        signals.append({"label": "上涨空间", "val": f"{dist_to_resist:.1f}ATR", "tag": "近阻力", "lv": "y"})
    
    score += max(0, pos_pts)
    
    # ─── 估值 (0-10分) — PE分档+分位调整+戴维斯 ───
    val_pts = 0
    if 0 < pe < 10:
        val_pts += 10; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "深度低估+10", "lv": "g"})
    elif 10 <= pe < 20:
        val_pts += 7; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "低估+7", "lv": "g"})
    elif 20 <= pe < 35:
        val_pts += 3; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "合理+3", "lv": "y"})
    elif 35 <= pe < 60:
        val_pts += 0; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "中性", "lv": "n"})
    elif 60 <= pe < 100:
        val_pts -= 3; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "偏高-3", "lv": "r"})
    elif pe >= 100 or pe < 0:
        val_pts -= 5; signals.append({"label": "PE估值", "val": f"{pe:.0f}", "tag": "泡沫/亏损-5", "lv": "r"})
    else:
        signals.append({"label": "PE估值", "val": "-", "tag": "无数据", "lv": "n"})
    
    # PE分位调整(从估值缓存读取)
    try:
        vc = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "state", "valuation_cache.json")))
        vs = vc.get("stocks", {}).get(code, {})
        if vs.get("pe_pct") is not None:
            pct = vs["pe_pct"]
            if pct <= 10: val_pts += 3; signals.append({"label": "PE分位", "val": f"{pct:.0f}%", "tag": "极低分位+3", "lv": "g"})
            elif pct >= 90: val_pts -= 5; signals.append({"label": "PE分位", "val": f"{pct:.0f}%", "tag": "极高分位-5", "lv": "r"})
        ds = vs.get("davis_signal", "")
        if ds in ("双杀💀", "杀估值⚠️"):
            val_pts -= 3; signals.append({"label": "戴维斯", "val": ds, "tag": "-3", "lv": "r"})
    except: pass
    
    score += max(-5, val_pts)
    
    # ─── 板块轮动加分 (0-8分) ───
    try:
        from pipeline.sector_rotation import get_sector_bonus
        bonus, reason = get_sector_bonus(code)
        if bonus != 0:
            score += bonus
            signals.append({"label": "板块", "val": reason, "tag": f"{bonus:+d}", "lv": "g" if bonus > 0 else "r"})
    except: pass
    
    # ─── 资金 (0-5分) ───
    fund_pts = 0
    if fund:
        net = fund["net"]
        if net > 5000:
            fund_pts += 5
            signals.append({"label": "主力资金", "val": f"+{net:.0f}万", "tag": "做多+5", "lv": "g"})
        elif net > 0:
            fund_pts += 2
            signals.append({"label": "主力资金", "val": f"+{net:.0f}万", "tag": "流入+2", "lv": "y"})
        elif net > -5000:
            signals.append({"label": "主力资金", "val": f"{net:.0f}万", "tag": "流出", "lv": "y"})
        else:
            fund_pts -= 2
            signals.append({"label": "主力资金", "val": f"{net:.0f}万", "tag": "出逃-2", "lv": "r"})
    else:
        signals.append({"label": "主力资金", "val": "-", "tag": "待更新", "lv": "n"})
    score += max(0, fund_pts)
    
    # ─── 判定 ───
    score = min(100, max(0, score))
    
    if score >= 65:
        verdict, vc = "强烈推荐", "#dc2626"
    elif score >= 50:
        verdict, vc = "推荐关注", "#2563eb"
    elif score >= 35:
        verdict, vc = "谨慎观望", "#d97706"
    else:
        verdict, vc = "暂不建议", "#059669"
    
    # 计算价位
    sl = round(p - atr_mult * atr, 2)
    tp1 = round(p * 1.08, 2)
    tp2 = round(p * 1.15, 2)
    
    # 旧版兼容: g/r计数(for autotrade信号阈值)
    g_count = sum(1 for s in signals if s["lv"] == "g")
    r_count = sum(1 for s in signals if s["lv"] == "r")
    
    return {
        "signals": signals,
        "verdict": verdict,
        "verdict_color": vc,
        "score": score,       # 新: 加权分数0-100
        "g": g_count,         # 兼容旧版信号计数
        "r": r_count,
        "total": len(signals),
        "prices": {
            "high_sell": round(resistance, 2),
            "breakthrough": round(resistance * 1.02, 2),
            "current": p,
            "first_entry": round(support, 2),
            "golden_pit": round(support * 0.97, 2),
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
        }
    }
