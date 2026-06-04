"""管道阶段3: LLM分析 — Ollama Qwen3 14B (本地免费, 可选)"""
import json, urllib.request, time

OLLAMA = "http://localhost:11434/api/generate"

def analyze(d, analysis):
    """LLM增强分析 (stock模式)"""
    p = d["price"]; pr = analysis["prices"]
    
    prompt = f"""你是A股资深分析师。请为{d['name']}({d['code']})撰写简洁分析，分三段，每段2-3句:
【短期】当前¥{p}，{'涨' if d['chg']>=0 else '跌'}{abs(d['chg']):.1f}%。支撑¥{pr['first_entry']:.2f}，压力¥{pr['high_sell']:.2f}。短期目标价。
【中期】PE{d['pe']:.0f}，主力{'净流入' if (d.get('fund') or {}).get('net',0)>0 else '资金偏弱'}。中期基本面和目标价。
【博弈】K线形态特征，洗盘/出货判断，关键支撑承接力度。"""

    try:
        req = urllib.request.Request(OLLAMA, 
            data=json.dumps({"model":"qwen3.6:27b","prompt":prompt,"stream":False,
                "options":{"temperature":0.5,"top_p":0.9,"num_predict":300}}).encode(),
            headers={"Content-Type":"application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=12).read())
        return resp.get("response","")
    except Exception as e:
        # 超时或错误 → 数据驱动回退
        return f"""【短期】当前¥{p}，{'上涨' if d['chg']>=0 else '回调'}中。支撑¥{pr['first_entry']:.2f}，压力¥{pr['high_sell']:.2f}。缩量回踩支撑可轻仓试探，目标¥{pr['take_profit_1']:.2f}。

【中期】PE={d['pe']:.0f}{'估值合理' if d['pe']<50 else '需关注估值' if d['pe']<100 else '估值偏高'}。主力资金{'偏多' if (d.get('fund') or {}).get('net',0)>0 else '偏空'}，关注量能变化。

【博弈】近5日K线{'呈洗盘特征(急跌缩量)' if d['chg']<-3 else '正常波动'}。关键支撑¥{pr['first_entry']:.2f}，若缩量企稳可视为主力吸筹。"""
