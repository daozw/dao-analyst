#!/usr/bin/env python3
"""市场温度计 — 判断牛/熊/震荡 自动调节策略"""
import subprocess, os, json
from datetime import datetime

MX_KEY = "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8"
ENV = {**os.environ, "MX_APIKEY": MX_KEY}

def get_index_data():
    """获取上证指数数据"""
    r = subprocess.run([
        "python3", "/Users/sound/.openclaw-autoclaw/skills/a-stock-analysis/scripts/analyze.py",
        "000001", "--json"
    ], capture_output=True, text=True, env=ENV, timeout=15)
    if r.returncode==0:
        d = json.loads(r.stdout)[0]["realtime"]
        return {"price": d["price"], "change": d["change_pct"]}
    return None

def get_market_stats():
    """获取全市场统计"""
    r = subprocess.run([
        "python3", "/Users/sound/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py",
        "A股主板 今日涨幅>0"
    ], capture_output=True, text=True, env=ENV, timeout=30)
    # 解析行数
    for line in r.stdout.split("\n"):
        if "行数:" in line:
            up_count = int(line.split(":")[-1].strip())
            break
    else:
        up_count = 0
    
    r2 = subprocess.run([
        "python3", "/Users/sound/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py",
        "A股主板 涨幅<-5%"
    ], capture_output=True, text=True, env=ENV, timeout=30)
    for line in r2.stdout.split("\n"):
        if "行数:" in line:
            down_count = int(line.split(":")[-1].strip())
            break
    else:
        down_count = 0
    
    return {"up": up_count, "down": down_count}

def thermometer():
    """市场温度计 0-100度"""
    temp = 50  # 默认中性
    
    # 1. 指数涨跌
    idx = get_index_data()
    if idx:
        if idx["change"] > 2: temp += 20
        elif idx["change"] > 0: temp += 5
        elif idx["change"] < -2: temp -= 20
        elif idx["change"] < 0: temp -= 5
    
    # 2. 涨跌家数比
    try:
        stats = get_market_stats()
        ratio = stats["up"] / max(stats["up"]+stats["down"], 1)
        temp += (ratio - 0.5) * 30
    except:
        pass
    
    temp = max(0, min(100, temp))
    
    # 判断
    if temp >= 70: phase = "🔥 牛市"
    elif temp >= 55: phase = "📈 偏多"
    elif temp >= 45: phase = "📊 震荡"
    elif temp >= 30: phase = "📉 偏空"
    else: phase = "❄️ 熊市"
    
    # 仓位建议
    if temp >= 70: allocation = 1.0
    elif temp >= 55: allocation = 0.7
    elif temp >= 45: allocation = 0.4
    elif temp >= 30: allocation = 0.2
    else: allocation = 0.0
    
    return {
        "temperature": temp,
        "phase": phase,
        "allocation": allocation,
        "advice": f"仓位{allocation*100:.0f}%",
        "time": datetime.now().strftime("%H:%M")
    }

if __name__ == "__main__":
    t = thermometer()
    print(f"🌡️ 市场温度: {t['temperature']}°C")
    print(f"   阶段: {t['phase']}")
    print(f"   仓位: {t['allocation']*100:.0f}%")
    print(f"   时间: {t['time']}")
