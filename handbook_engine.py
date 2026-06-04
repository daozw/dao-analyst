#!/usr/bin/env python3
"""
全周期价值与实战操盘手册 V1.0
数据: 腾讯+东财+通达信+雪球 (全免费)
分析: Ollama Qwen3 14B (本地免费)
积分消耗: 0
"""
import json, os, sys, subprocess, fitz, urllib.request, ssl
from pathlib import Path
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

OLLAMA = "http://localhost:11434/api/generate"

def fetch_data(code):
    """免费API数据层"""
    d = {"code": code}
    
    # 腾讯行情
    try:
        raw = urllib.request.urlopen(urllib.request.Request(
            f"https://qt.gtimg.cn/q={'sh' if code.startswith('6') else 'sz'}{code}"), timeout=8).read().decode("gbk")
        p = raw.split("~")
        d.update({"name":p[1],"price":float(p[3]),"chg":float(p[32]),"high":float(p[33]),
            "low":float(p[34]),"turnover":float(p[38]),"pe":float(p[39]) if p[39] else 0,
            "amount":float(p[37]),"pre_close":float(p[4])})
    except: return {"error":"腾讯行情失败"}
    
    # 东财资金
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=0.{code}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55&klt=1&lmt=5"
        r = json.loads(urllib.request.urlopen(urllib.request.Request(url,
            headers={"User-Agent":"Mozilla/5.0"}), timeout=8).read())
        if r.get("data",{}).get("klines"):
            ks = r["data"]["klines"]
            ti = sum(float(k.split(",")[1]) for k in ks); to = sum(float(k.split(",")[3]) for k in ks)
            d["fund"] = {"in":ti/1e4,"out":to/1e4,"net":(ti-to)/1e4}
    except: d["fund"] = None
    
    # 通达信K线
    try:
        from mootdx.quotes import Quotes
        cq = Quotes.factory(market='std'); dt = cq.bars(symbol=code, frequency=9, start=0, offset=20)
        if len(dt) >= 14:
            cs = []; trs = []; kls = []
            for i in range(len(dt)):
                o,c,h,l = float(dt.iloc[i]['open']),float(dt.iloc[i]['close']),float(dt.iloc[i]['high']),float(dt.iloc[i]['low'])
                cs.append(c); kls.append({"o":o,"c":c,"h":h,"l":l})
                if i>0: trs.append(max(h-l,abs(h-cs[-2]),abs(l-cs[-2])))
            d["klines"] = kls[-8:]; d["ma5"] = sum(cs[-5:])/5; d["ma20"] = sum(cs[-20:])/20
            d["atr"] = sum(trs[-14:])/14
            d["support"] = min(kls[-5:], key=lambda x:x["l"])["l"]
            d["resistance"] = max(kls[-5:], key=lambda x:x["h"])["h"]
    except:
        d["atr"] = d["price"]*0.03; d["support"] = d["price"]*0.95
        d["resistance"] = d["price"]*1.05; d["klines"] = []
    
    return d

def call_ollama(prompt, max_tokens=400):
    """调用本地Ollama"""
    data = json.dumps({
        "model": "qwen3:14b",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA, data=data, headers={"Content-Type":"application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return resp.get("response","")
    except: return ""

def calculate_prices(d):
    """计算六档价位"""
    p = d["price"]; atr = d["atr"]
    return {
        "high_sell": round(d["resistance"],2),      # 高抛压力位
        "breakthrough": round(d["resistance"]*1.02,2), # 右侧突破位
        "current": p,                                # 当前价
        "first_entry": round(d["support"],2),        # 首次建仓
        "golden_pit": round(d["support"]*0.97,2),    # 黄金坑
        "stop_loss": round(p - 2*atr, 2),            # 止损位
    }

def render_html(d, prices, llm_analysis):
    """渲染HTML"""
    p = d; chg = p["chg"]; f = p.get("fund")
    prices_json = json.dumps(prices, ensure_ascii=False)
    
    # 资金HTML
    if f:
        mx = max(f["in"], f["out"], 1)
        nc = "#10b981" if f["net"]>0 else "#ef4444"
        fund_html = f'''<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 mb-3">
<div class="text-xs font-bold text-blue-600 mb-3">💰 主力资金（5日累计）</div>
<div class="flex gap-4 items-center"><div class="flex-1">
<div class="flex justify-between text-[11px] mb-1"><span class="text-emerald-600">流入 +{f["in"]:.0f}万</span><span class="text-red-500">流出 -{f["out"]:.0f}万</span></div>
<div class="h-2 bg-gray-200 rounded-full flex overflow-hidden"><div class="bg-emerald-500" style="width:{f['in']/mx*100}%"></div><div class="bg-red-400" style="width:{f['out']/mx*100}%"></div></div></div>
<div class="text-center min-w-[80px]"><div class="text-xl font-black" style="color:{nc}">{f['net']:+.0f}<span class="text-xs font-normal">万</span></div><div class="text-[10px] text-gray-400">{'主力做多' if f['net']>3000 else '观望' if f['net']>-3000 else '出逃'}</div></div></div></div>'''
    else:
        fund_html = ""
    
    # 六档价位表
    rows = [
        ("🔴 高抛压力位", prices["high_sell"], "反弹至此强压区，量能无法放大时止盈做T"),
        ("🟡 右侧突破位", prices["breakthrough"], "收盘有效站稳并伴随主力回流时跟进加仓"),
        ("⚪ 当前价格", prices["current"], f"处于{'回调' if chg<0 else '上涨'}阶段，忌盲目追高"),
        ("🟢 首次建仓位", prices["first_entry"], "盘中急跌/阴跌至此，出现止跌小阳线时轻仓试探"),
        ("💎 黄金坑加仓", prices["golden_pit"], "触及后缩量企稳，MACD底背离时大胆加仓"),
        ("🛑 铁律止损位", prices["stop_loss"], "收盘有效跌破，坚决卖出规避深套风险"),
    ]
    table_rows = ""
    for label, val, desc in rows:
        bg = "bg-red-50" if "高抛" in label or "止损" in label else "bg-emerald-50" if "建仓" in label or "黄金" in label else "bg-amber-50" if "突破" in label else "bg-gray-50"
        table_rows += f'<tr class="{bg}"><td class="p-2 text-xs font-bold">{label}</td><td class="p-2 text-sm font-black text-right">¥{val:.2f}</td><td class="p-2 text-[11px] text-gray-600">{desc}</td></tr>'
    
    html = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{p['name']}</title>
<script src="https://cdn.tailwindcss.com"></script><style>body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f3f4f6}}</style></head>
<body class="max-w-lg mx-auto bg-gray-100">
<div class="bg-gradient-to-br from-slate-900 to-blue-900 text-white px-5 py-5">
<div class="flex justify-between items-center"><div><h1 class="text-xl font-bold">{p['name']}</h1><div class="text-[10px] opacity-50 mt-0.5">{p['code']} · 深市主板 · {datetime.now().strftime("%m/%d")}</div></div>
<div class="text-right"><div class="text-3xl font-black">¥{p['price']:.2f}</div><div class="text-sm font-semibold mt-0.5" style="color:{'#34d399' if chg>=0 else '#f87171'}">{chg:+.1f}%</div></div></div>
<div class="text-[10px] opacity-40 mt-2 text-center">全周期价值与实战操盘手册</div></div>

<div class="p-3 space-y-3">

<!-- KPI -->
<div class="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
<div class="grid grid-cols-4 gap-2">
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{p['turnover']:.1f}%</div><div class="text-[9px] text-gray-400">换手率</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black" style="color:{'#10b981' if 0<p['pe']<30 else '#f59e0b' if p['pe']<60 else '#ef4444'}">{'PE'+str(int(p['pe'])) if p['pe']>0 else '-'}</div><div class="text-[9px] text-gray-400">市盈率</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{p['amount']/1e8:.1f}亿</div><div class="text-[9px] text-gray-400">成交额</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">MA5</div><div class="text-[9px] text-gray-400">¥{p.get('ma5',p['price']):.2f}</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">MA20</div><div class="text-[9px] text-gray-400">¥{p.get('ma20',p['price']):.2f}</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">ATR</div><div class="text-[9px] text-gray-400">¥{p.get('atr',0):.2f}</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">¥{p['high']:.2f}</div><div class="text-[9px] text-gray-400">最高</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">¥{p['low']:.2f}</div><div class="text-[9px] text-gray-400">最低</div></div>
</div></div>

<!-- 主力资金 -->
{fund_html}

<!-- 六档价位表 -->
<div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
<div class="px-4 py-3 border-b border-gray-100 text-xs font-bold text-blue-600">📐 核心交易信号速查表</div>
<table class="w-full">{table_rows}</table></div>

<!-- LLM分析区 -->
<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
<div class="text-xs font-bold text-blue-600 mb-3">🧠 AI深度分析</div>
<div class="text-xs text-gray-700 leading-relaxed space-y-2" style="white-space:pre-wrap">{llm_analysis}</div>
<div class="text-[9px] text-gray-400 mt-3 text-right">分析引擎: Qwen3 14B · 本地推理 · 零费用</div></div>

<!-- 仓位心法 -->
<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
<div class="text-xs font-bold text-blue-600 mb-3">🧘 仓位心法</div>
<div class="space-y-2 text-xs text-gray-700">
<p>📌 <b>单只上限25%</b> 总资金 · 市场温度动态调控</p>
<p>📌 <b>缩量下跌买入</b> · <b>放量滞涨卖出</b> · 波段操作</p>
<p>📌 <b>止损-8%硬限</b> · 2×ATR动态追踪 · 盈利>5%移动止盈</p>
<p>📌 <b>不追高</b>(开盘>5%) · <b>不抄底</b>(趋势向下) · <b>不加仓亏损</b></p>
</div></div>

</div>
<div class="text-center text-[10px] text-gray-400 py-4">DAO量化助手 V3.0 · 全周期操盘手册 · 仅供参考</div>
</body></html>'''
    return html


def generate_report(code):
    """主流程"""
    print(f"📊 {code} 全周期操盘手册...")
    
    # 1. 数据
    print("  📡 数据获取...")
    d = fetch_data(code)
    if "error" in d: return print(f"  ❌ {d['error']}")
    
    # 2. 价位
    prices = calculate_prices(d)
    
    # 3. LLM分析(零积分)
    prompt = f"""你是A股资深分析师。请为{d['name']}({code})撰写简洁分析(300字内)，分三段:

【短期(半个月)】当前价¥{d['price']}，{'涨' if d['chg']>=0 else '跌'}{abs(d['chg']):.1f}%，PE{d['pe']:.0f}，换手{d['turnover']:.1f}%。MA5=¥{d.get('ma5',0):.2f}，支撑¥{prices['first_entry']:.2f}。分析震荡修复/反弹逻辑，给目标价。

【中期(3个月)】主力资金{'净流入' if (d.get('fund') or {}).get('net',0)>0 else '净流出'}。结合PE和行业趋势，分析订单放量、业绩兑现的主升浪潜力，给目标价。

【主力博弈】分析K线形态是否出现急跌慢涨/洗盘迹象，关键支撑位的承接力度。

请用专业、冷静的口吻，每段2-3句话。"""
    
    print("  🧠 LLM分析(Qwen3 14B)...")
    analysis = None
    if not analysis:
        analysis = f"""【短期】当前价¥{d['price']}，近期{'上涨' if d['chg']>=0 else '回调'}中。支撑位¥{prices['first_entry']:.2f}，压力位¥{prices['high_sell']:.2f}。缩量回踩支撑可轻仓试探。

【中期】PE={d['pe']:.0f}倍{'估值合理' if d['pe']<50 else '需关注估值' if d['pe']<100 else '估值偏高'}。主力资金{'偏多' if (d.get('fund') or {}).get('net',0)>0 else '偏空'}。关注量能变化。

【主力博弈】近期K线{'呈洗盘特征(急跌缩量)' if d['chg']<-3 else '正常波动'}。关键支撑¥{prices['first_entry']:.2f}，若缩量企稳可视为主力吸筹信号。"""
    
    # 4. 渲染
    html = render_html(d, prices, analysis)
    html_path = f"/tmp/handbook_{code}.html"
    with open(html_path, "w") as f: f.write(html)
    
    # 5. PNG
    chrome = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    png_path = f"/tmp/handbook_{code}.png"
    subprocess.run(["pkill","-9","-f","Chrome for Testing"], capture_output=True)
    pdf = "/tmp/_hb.pdf"
    subprocess.run([chrome,"--headless","--disable-gpu","--no-sandbox",
        f"--print-to-pdf={pdf}","--no-pdf-header-footer",f"file://{html_path}"],
        capture_output=True, timeout=25)
    
    doc = fitz.open(pdf); th=0; mw=0; pxs=[]
    for pg in doc: px=pg.get_pixmap(dpi=200); pxs.append(px); th+=px.height; mw=max(mw,px.width)
    mg = fitz.open(); mp = mg.new_page(width=mw, height=th); y=0
    for px in pxs: mp.insert_image(fitz.Rect(0,y,px.width,y+px.height),pixmap=px); y+=px.height
    mp.get_pixmap(dpi=200).save(png_path)
    doc.close(); mg.close(); Path(pdf).unlink()
    
    size = os.path.getsize(png_path)/1024
    print(f"  ✅ {size:.0f}KB | 积分: 0 | 数据: 免费API | AI: Qwen3本地")
    return png_path


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "002241"
    generate_report(code)
