#!/usr/bin/env python3
"""
量价背离检测 V3.0
检测顶背离/底背离/放量滞涨/缩量止跌 — 趋势反转早期预警
"""
import sys, os
from datetime import date, timedelta

# 依赖 a-stock-analysis 的数据能力
sys.path.insert(0, os.path.expanduser("~/dao-analyst/astock"))
os.environ.setdefault("TRADINGAGENTS_LLM_PROVIDER", "ollama")
os.environ.setdefault("TRADINGAGENTS_BACKEND_URL", "http://localhost:11434/v1")

def detect_divergence(prices, volumes, period=20):
    """
    检测量价背离
    返回: {type, confidence, signal}
    
    prices: [(date, open, high, low, close), ...] 最近N日
    volumes: [(date, vol), ...]
    """
    if len(prices) < period or len(volumes) < period:
        return {"type": "insufficient_data", "confidence": 0, "signal": "NEUTRAL"}
    
    # 取最近 period 日的数据
    recent_p = prices[-period:]
    recent_v = volumes[-period:]
    
    # 分段计算趋势
    half = period // 2
    first_half_p = recent_p[:half]
    second_half_p = recent_p[half:]
    first_half_v = recent_v[:half]
    second_half_v = recent_v[half:]
    
    # 价格趋势
    p_start_avg = sum(p[4] for p in first_half_p[-5:]) / 5  # 前段收盘均价
    p_end_avg = sum(p[4] for p in second_half_p[-5:]) / 5   # 后段收盘均价
    price_trend = (p_end_avg - p_start_avg) / p_start_avg * 100
    
    # 成交量趋势
    v_start_avg = sum(v[1] for v in first_half_v[-5:]) / 5
    v_end_avg = sum(v[1] for v in second_half_v[-5:]) / 5
    vol_trend = (v_end_avg - v_start_avg) / max(v_start_avg, 1) * 100
    
    # === 背离判断 ===
    
    # 1. 顶背离：价格创新高 但 量能递减
    p_highs = [p[2] for p in recent_p[-10:]]  # 最近10日最高价
    v_last10 = [v[1] for v in recent_v[-10:]]
    
    p_rising = price_trend > 3  # 价格涨超3%
    v_falling = vol_trend < -15  # 量缩超15%
    
    price_new_high = max(p_highs[-3:]) >= max(p_highs[:-3]) * 0.995
    vol_not_confirming = max(v_last10[-3:]) < max(v_last10[:-3]) * 0.85
    
    if p_rising and v_falling and price_new_high and vol_not_confirming:
        return {
            "type": "🔴 顶背离",
            "confidence": 85,
            "signal": "SELL",
            "detail": f"价格{price_trend:+.1f}%创新高 但量缩{abs(vol_trend):.0f}% → 上涨动力衰竭"
        }
    
    # 2. 底背离：价格创新低 但 量能放大（主力吸筹）
    p_falling = price_trend < -3
    v_rising = vol_trend > 15
    
    price_new_low = min(p_highs[-3:]) <= min(p_highs[:-3]) * 1.005
    vol_surging = min(v_last10[-5:]) > min(v_last10[:-5]) * 1.2
    
    if p_falling and v_rising and price_new_low and vol_surging:
        return {
            "type": "🟢 底背离",
            "confidence": 80,
            "signal": "BUY",
            "detail": f"价格{price_trend:+.1f}%创新低 但放量{vol_trend:+.0f}% → 主力低位吸筹"
        }
    
    # 3. 放量滞涨：量大价不涨 → 出货信号
    if vol_trend > 30 and abs(price_trend) < 1.5:
        return {
            "type": "🟠 放量滞涨",
            "confidence": 75,
            "signal": "SELL",
            "detail": f"量增{vol_trend:+.0f}% 但价格仅{price_trend:+.1f}% → 出货嫌疑"
        }
    
    # 4. 缩量止跌：价稳量缩 → 筑底信号
    if abs(price_trend) < 1.5 and vol_trend < -25 and price_trend > -1:
        return {
            "type": "🟡 缩量止跌",
            "confidence": 65,
            "signal": "WATCH",
            "detail": f"价格{price_trend:+.1f}%企稳 量缩{abs(vol_trend):.0f}% → 筑底可能"
        }
    
    # 5. 量价齐升：健康上涨
    if price_trend > 2 and vol_trend > 10:
        return {
            "type": "✅ 量价配合",
            "confidence": 60,
            "signal": "BUY",
            "detail": f"价{price_trend:+.1f}% 量{vol_trend:+.0f}% → 健康上涨"
        }
    
    # 6. 无背离
    return {
        "type": "➖ 无背离",
        "confidence": 50,
        "signal": "NEUTRAL",
        "detail": f"价{price_trend:+.1f}% 量{vol_trend:+.0f}% → 常态运行"
    }


def check_volume_price(ticker, recent_data=None):
    """
    全量量价健康度检查
    
    如果 recent_data 为空，尝试从 tradingagents 数据源获取
    """
    results = {
        "ticker": ticker,
        "divergences": [],
        "anomalies": [],
        "health_score": 100,  # 100分满分
    }
    
    if recent_data is None:
        return {
            "ticker": ticker,
            "error": "需要传入 recent_data: [(date,o,h,l,c,v), ...]",
            "health_score": 100
        }
    
    prices = [(d[0], d[1], d[2], d[3], d[4]) for d in recent_data]
    volumes = [(d[0], d[5]) for d in recent_data]
    
    # 主背离检测
    div = detect_divergence(prices, volumes)
    results["divergences"].append(div)
    
    # 异常检测
    # 天量换手：成交量超过20日均量3倍
    if len(volumes) >= 20:
        vol_20_avg = sum(v[1] for v in volumes[-21:-1]) / 20
        today_vol = volumes[-1][1]
        if today_vol > vol_20_avg * 3:
            results["anomalies"].append({
                "type": "天量成交",
                "severity": "WARNING",
                "detail": f"今日量达20日均量{today_vol/vol_20_avg:.1f}倍"
            })
            results["health_score"] -= 20
    
    # 连续缩量：连续3日量缩
    if len(volumes) >= 4:
        v3 = volumes[-4][1]
        v2 = volumes[-3][1]
        v1 = volumes[-2][1]
        v0 = volumes[-1][1]
        if v0 < v1 < v2 < v3:
            results["anomalies"].append({
                "type": "连续缩量",
                "severity": "INFO",
                "detail": "连续3日缩量，观望情绪浓"
            })
            results["health_score"] -= 5
    
    # 突然放量：今日量 > 昨日2倍
    if len(volumes) >= 2:
        if volumes[-1][1] > volumes[-2][1] * 2:
            direction = "涨" if len(prices) >= 2 and prices[-1][4] > prices[-2][4] else "跌"
            results["anomalies"].append({
                "type": "突然放量",
                "severity": "WARNING" if direction == "跌" else "INFO",
                "detail": f"放量{direction}，量增{volumes[-1][1]/volumes[-2][1]:.1f}倍"
            })
            if direction == "跌":
                results["health_score"] -= 15
    
    results["health_score"] = max(0, min(100, results["health_score"]))
    
    # 健康评级
    if results["health_score"] >= 80:
        results["grade"] = "🟢 健康"
    elif results["health_score"] >= 60:
        results["grade"] = "🟡 注意"
    elif results["health_score"] >= 40:
        results["grade"] = "🟠 警惕"
    else:
        results["grade"] = "🔴 危险"
    
    return results


# ═══════════════════════════════════
# 快速测试
# ═══════════════════════════════════
if __name__ == "__main__":
    # 模拟数据测试
    import random
    
    # 场景1: 价格涨但量缩 (顶背离)
    base_price = 10.0
    scenario1_prices = []
    scenario1_vols = []
    for i in range(25):
        d = date.today() - timedelta(days=25-i)
        if i < 12:
            p = base_price + i * 0.3 + random.uniform(-0.5, 0.5)
            v = 1000000 + random.randint(-200000, 200000)
        else:
            p = base_price + 12 * 0.3 + (i-12) * 0.4 + random.uniform(-0.3, 0.3)
            v = 1000000 - (i-12) * 40000 + random.randint(-100000, 100000)
        scenario1_prices.append((d, p-0.2, p+0.2, p-0.2, p))
        scenario1_vols.append((d, v))
    
    data1 = [(p[0], p[1], p[2], p[3], p[4], v[1]) for p, v in zip(scenario1_prices, scenario1_vols)]
    
    print("📊 V3.0 量价背离检测系统")
    print("=" * 55)
    
    print("\n场景1: 价格涨 + 量缩（模拟顶背离）")
    result1 = check_volume_price("TEST01", data1)
    for div in result1["divergences"]:
        print(f"  {div['type']}: {div.get('detail','')}")
    print(f"  健康分: {result1['health_score']}/100 {result1['grade']}")
    
    # 场景2: 价格跌但放量 (底背离)
    scenario2_prices = []
    scenario2_vols = []
    for i in range(25):
        d = date.today() - timedelta(days=25-i)
        if i < 12:
            p = base_price - i * 0.3 + random.uniform(-0.5, 0.5)
            v = 500000 + random.randint(-100000, 100000)
        else:
            p = base_price - 12 * 0.3 - (i-12) * 0.2 + random.uniform(-0.3, 0.3)
            v = 500000 + (i-12) * 60000 + random.randint(-50000, 50000)
        scenario2_prices.append((d, p-0.2, p+0.2, p-0.2, p))
        scenario2_vols.append((d, v))
    
    data2 = [(p[0], p[1], p[2], p[3], p[4], v[1]) for p, v in zip(scenario2_prices, scenario2_vols)]
    
    print("\n场景2: 价格跌 + 放量（模拟底背离）")
    result2 = check_volume_price("TEST02", data2)
    for div in result2["divergences"]:
        print(f"  {div['type']}: {div.get('detail','')}")
    print(f"  健康分: {result2['health_score']}/100 {result2['grade']}")
    
    # 场景3: 量价齐升（健康）
    scenario3_prices = [(date.today()-timedelta(days=25-i), base_price+i*0.2+random.uniform(-0.3,0.3), 
                         base_price+i*0.2+0.3, base_price+i*0.2-0.3, base_price+i*0.2+random.uniform(-0.2,0.2)) 
                        for i in range(25)]
    scenario3_vols = [(date.today()-timedelta(days=25-i), 800000+i*20000+random.randint(-100000,100000)) 
                      for i in range(25)]
    data3 = [(p[0], p[1], p[2], p[3], p[4], v[1]) for p, v in zip(scenario3_prices, scenario3_vols)]
    
    print("\n场景3: 量价齐升（模拟健康上涨）")
    result3 = check_volume_price("TEST03", data3)
    for div in result3["divergences"]:
        print(f"  {div['type']}: {div.get('detail','')}")
    print(f"  健康分: {result3['health_score']}/100 {result3['grade']}")
