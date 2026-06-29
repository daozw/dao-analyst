#!/usr/bin/env python3
"""每日AI收盘摘要 — LLM分析当日交易+信号"""
import json, os, urllib.request, subprocess
from datetime import datetime

ALERT_FILE = os.path.expanduser("~/dao-analyst/data/live/trade_alerts.json")
SIGNAL_FILE = "/tmp/dao_signals.json"
RELAY_OUT = os.path.expanduser("~/dao-analyst/data/live/relay_pending.txt")

def collect_data():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today, "index": [], "buys": [], "sells": [], "signals": []}
    try:
        raw = urllib.request.urlopen("https://qt.gtimg.cn/q=sh000001,sz399001", timeout=5).read().decode("gbk")
        for ln in raw.strip().split("\n"):
            d = ln.split("~")
            if len(d) > 32:
                data["index"].append(d[1] + " " + f"{float(d[3]):.0f}" + " " + d[32] + "%")
    except: pass
    if os.path.exists(ALERT_FILE):
        alerts = json.load(open(ALERT_FILE))
        for a in alerts:
            if a.get("time", "")[:5] < "09:00": continue
            t = {"name": a["name"], "code": a["code"], "price": str(a["price"])}
            if a["action"] == "BUY": data["buys"].append(t)
            elif a["action"] == "SELL": data["sells"].append(t)
    if os.path.exists(SIGNAL_FILE):
        sigs = json.load(open(SIGNAL_FILE))
        seen = {}
        for s in sigs:
            c = s["code"]
            if c not in seen or s["ts"] > seen[c]["ts"]:
                seen[c] = {"name": s["name"], "code": c, "chg": round(s["chg"], 1)}
        data["signals"] = sorted(seen.values(), key=lambda x: -x["chg"])[:10]
    return data

def summarize(data):
    buy_info = ", ".join(b["name"] + "(" + b["code"] + ")" for b in data["buys"][:5]) or "无"
    sell_info = ", ".join(s["name"] + "(" + s["code"] + ")" for s in data["sells"][:5]) or "无"
    sig_info = ", ".join(s["name"] + "+" + str(s["chg"]) + "%" for s in data["signals"][:6]) or "无"
    idx_info = ", ".join(data["index"]) or "数据获取失败"
    
    prompt = "你是A股分析师。根据以下数据生成收盘日报摘要(80字内):\n"
    prompt += "大盘: " + idx_info + "\n"
    prompt += "买入" + str(len(data["buys"])) + "笔: " + buy_info + "\n"
    prompt += "卖出" + str(len(data["sells"])) + "笔: " + sell_info + "\n"
    prompt += "热点: " + sig_info + "\n"
    prompt += "要求: 1行大盘判断+1行操作总结+1行明日方向。只输出正文,不要前缀。"
    
    try:
        r = subprocess.run(["/usr/local/bin/ollama", "run", "qwen2.5:3b", prompt],
                          capture_output=True, text=True, timeout=30)
        return r.stdout.strip()[:200] if r.returncode == 0 else "AI生成失败"
    except:
        return "AI服务不可用"

def run():
    data = collect_data()
    ai = summarize(data)
    
    lines = ["AI日报 | " + data["date"], "", ai, "", "━━ 明细 ━━"]
    if data["index"]: lines.append("  ".join(data["index"]))
    if data["buys"]: lines.append("买入: " + ", ".join(b["name"] + "@" + b["price"] for b in data["buys"][:5]))
    if data["sells"]: lines.append("卖出: " + ", ".join(s["name"] + "@" + s["price"] for s in data["sells"][:5]))
    lines.append("信号: " + str(len(data["signals"])) + "只活跃")
    
    msg = "\n".join(lines)
    with open(RELAY_OUT, "w") as f: f.write(msg)
    print(msg)

if __name__ == "__main__": run()
