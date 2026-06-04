#!/usr/bin/env python3
"""
报告引擎 V3.0 — 数据/UI分离 + Tailwind + SVG图表 + Bento布局
核心理念: JSON数据驱动, 模板引擎渲染, 参数化样式
"""
import json, os, sys, subprocess, fitz
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class StockDataFetcher:
    """统一数据层 — 输出标准化JSON"""
    
    @staticmethod
    def fetch(code: str) -> Dict:
        import urllib.request, ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        data = {"code": code, "timestamp": datetime.now().isoformat()}
        
        # 腾讯行情
        try:
            req = urllib.request.Request(f"https://qt.gtimg.cn/q={'sh' if code.startswith('6') else 'sz'}{code}")
            raw = urllib.request.urlopen(req, timeout=8).read().decode("gbk")
            p = raw.split("~")
            data["name"] = p[1]
            data["price"] = float(p[3]) if p[3] else 0
            data["change_pct"] = float(p[32]) if p[32] else 0
            data["high"] = float(p[33]) if p[33] else 0
            data["low"] = float(p[34]) if p[34] else 0
            data["turnover"] = float(p[38]) if p[38] else 0
            data["pe"] = float(p[39]) if p[39] else 0
            data["amount"] = float(p[37]) if p[37] else 0
            data["pre_close"] = float(p[4]) if p[4] else 0
        except Exception as e:
            data["error"] = str(e)
            return data
        
        # 东财资金流向
        try:
            url = f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=0.{code}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55&klt=1&lmt=5"
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.eastmoney.com/"})
            d = json.loads(urllib.request.urlopen(req, timeout=8).read())
            if d.get("data",{}).get("klines"):
                ks = d["data"]["klines"]
                data["fund_flow"] = {
                    "inflow": sum(float(k.split(",")[1]) for k in ks)/1e4,
                    "outflow": sum(float(k.split(",")[3]) for k in ks)/1e4,
                    "net": (sum(float(k.split(",")[1]) for k in ks) - sum(float(k.split(",")[3]) for k in ks))/1e4,
                    "daily": [{"date": k.split(",")[0], "main_in": float(k.split(",")[1]), "main_out": float(k.split(",")[3])} for k in ks]
                }
        except:
            data["fund_flow"] = None
        
        # 通达信K线
        try:
            from mootdx.quotes import Quotes
            client = Quotes.factory(market='std')
            dt = client.bars(symbol=code, frequency=9, start=0, offset=20)
            if len(dt) >= 14:
                klines = []
                closes = []; trs = []
                for i in range(len(dt)):
                    o,c,h,l = float(dt.iloc[i]['open']),float(dt.iloc[i]['close']),float(dt.iloc[i]['high']),float(dt.iloc[i]['low'])
                    closes.append(c)
                    klines.append({"open":o,"close":c,"high":h,"low":l})
                    if i > 0: trs.append(max(h-l, abs(h-closes[-2]), abs(l-closes[-2])))
                
                data["klines"] = klines[-8:]
                data["ma5"] = sum(closes[-5:])/5
                data["ma20"] = sum(closes[-20:])/20
                data["atr"] = sum(trs[-14:])/14
                data["support"] = min(klines[-5:], key=lambda x:x["low"])["low"]
                data["resistance"] = max(klines[-5:], key=lambda x:x["high"])["high"]
        except:
            data["klines"] = []
            data["atr"] = data["price"] * 0.03
            data["ma5"] = data["price"]
            data["ma20"] = data["price"]
            data["support"] = data["price"] * 0.95
            data["resistance"] = data["price"] * 1.05
        
        return data


class SignalEngine:
    """信号计算引擎 — 输入JSON, 输出信号数组"""
    
    @staticmethod
    def analyze(data: Dict) -> Dict:
        p = data["price"]; chg = data["change_pct"]
        pe = data.get("pe",0); turnover = data.get("turnover",0)
        ma5 = data.get("ma5",p); ma20 = data.get("ma20",p)
        atr = data.get("atr", p*0.03)
        fund = data.get("fund_flow")
        
        signals = []
        
        # PE
        if 0 < pe < 30: signals.append({"id":"pe","icon":"✅","label":"PE估值","value":f"{pe:.0f}","tag":"低估值","level":"positive"})
        elif 30 <= pe < 60: signals.append({"id":"pe","icon":"⚠️","label":"PE估值","value":f"{pe:.0f}","tag":"合理","level":"neutral"})
        elif pe >= 60: signals.append({"id":"pe","icon":"❌","label":"PE估值","value":f"{pe:.0f}","tag":"偏高","level":"negative"})
        else: signals.append({"id":"pe","icon":"—","label":"PE估值","value":"-","tag":"无数据","level":"neutral"})
        
        # 趋势
        if chg >= 3: signals.append({"id":"trend","icon":"✅","label":"价格趋势","value":f"{chg:+.1f}%","tag":"强势","level":"positive"})
        elif chg >= 0: signals.append({"id":"trend","icon":"⚠️","label":"价格趋势","value":f"{chg:+.1f}%","tag":"震荡","level":"neutral"})
        else: signals.append({"id":"trend","icon":"❌","label":"价格趋势","value":f"{chg:+.1f}%","tag":"走弱","level":"negative"})
        
        # 换手
        if 3 <= turnover <= 8: signals.append({"id":"turnover","icon":"✅","label":"换手率","value":f"{turnover:.1f}%","tag":"活跃","level":"positive"})
        elif turnover > 15: signals.append({"id":"turnover","icon":"❌","label":"换手率","value":f"{turnover:.1f}%","tag":"异常","level":"negative"})
        else: signals.append({"id":"turnover","icon":"⚠️","label":"换手率","value":f"{turnover:.1f}%","tag":"正常","level":"neutral"})
        
        # MA5
        if p > ma5: signals.append({"id":"ma5","icon":"✅","label":"MA5均线","value":f"¥{ma5:.2f}","tag":"短多","level":"positive"})
        else: signals.append({"id":"ma5","icon":"❌","label":"MA5均线","value":f"¥{ma5:.2f}","tag":"短空","level":"negative"})
        
        # MA20
        if p > ma20: signals.append({"id":"ma20","icon":"✅","label":"MA20均线","value":f"¥{ma20:.2f}","tag":"中多","level":"positive"})
        else: signals.append({"id":"ma20","icon":"⚠️","label":"MA20均线","value":f"¥{ma20:.2f}","tag":"中空","level":"neutral"})
        
        # 主力资金
        if fund:
            net = fund["net"]
            if net > 5000: signals.append({"id":"fund","icon":"✅","label":"主力资金","value":f"+{net:.0f}万","tag":"做多","level":"positive"})
            elif net > 0: signals.append({"id":"fund","icon":"⚠️","label":"主力资金","value":f"+{net:.0f}万","tag":"小幅流入","level":"neutral"})
            elif net > -5000: signals.append({"id":"fund","icon":"⚠️","label":"主力资金","value":f"{net:.0f}万","tag":"小幅流出","level":"neutral"})
            else: signals.append({"id":"fund","icon":"❌","label":"主力资金","value":f"{net:.0f}万","tag":"出逃","level":"negative"})
        else:
            signals.append({"id":"fund","icon":"—","label":"主力资金","value":"-","tag":"待更新","level":"neutral"})
        
        # 汇总
        pos = sum(1 for s in signals if s["level"]=="positive")
        neg = sum(1 for s in signals if s["level"]=="negative")
        
        if pos >= 4 and neg == 0: verdict, vc = "强烈推荐", "#059669"
        elif pos >= 3: verdict, vc = "推荐关注", "#2563eb"
        elif pos >= 2: verdict, vc = "谨慎观望", "#d97706"
        else: verdict, vc = "暂不建议", "#dc2626"
        
        # 价位计算
        sl = round(p - 2*atr, 2)
        tp1 = round(p * 1.08, 2)
        tp2 = round(p * 1.15, 2)
        ea = round(p * 1.02, 2)
        
        return {
            "signals": signals,
            "verdict": verdict, "verdict_color": vc,
            "positive_count": pos, "negative_count": neg, "total_count": len(signals),
            "prices": {
                "stop_loss": sl, "stop_loss_pct": round((sl-p)/p*100,1),
                "entry_dip": round(data["support"],2),
                "entry_now": p,
                "entry_add": ea,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
            }
        }


# ═══════════════════════════════════
# Tailwind HTML 模板引擎
# ═══════════════════════════════════
TAILWIND_CDN = '<script src="https://cdn.tailwindcss.com"></script>'

def render_stock_report(data: Dict, analysis: Dict) -> str:
    """JSON数据 → Tailwind HTML"""
    d = data; a = analysis; p = a["prices"]
    chg = d["change_pct"]
    
    # Sparkline SVG
    spark = ""
    if d.get("klines"):
        c8 = [k["close"] for k in d["klines"][-8:]]
        mn, mx = min(c8), max(c8)
        rg = mx - mn if mx > mn else 1
        w, h = 200, 40
        pts = " ".join(f"{i*(w/(len(c8)-1)):.0f},{h-(c-mn)/rg*h:.0f}" for i,c in enumerate(c8))
        area_pts = f"0,{h} " + " ".join(f"{i*(w/(len(c8)-1)):.0f},{h-(c-mn)/rg*h:.0f}" for i,c in enumerate(c8)) + f" {w},{h}"
        sc = "#10b981" if c8[-1] >= c8[0] else "#ef4444"
        spark = f'''<svg viewBox="0 0 {w} {h}" class="w-full h-10">
<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{sc}" stop-opacity="0.2"/><stop offset="100%" stop-color="{sc}" stop-opacity="0"/></linearGradient></defs>
<polygon points="{area_pts}" fill="url(#sg)"/>
<polyline points="{pts}" fill="none" stroke="{sc}" stroke-width="1.5" stroke-linecap="round"/></svg>'''
    
    # 信号行
    sig_rows = ""
    for s in a["signals"]:
        colors = {"positive":"bg-emerald-50 border-emerald-200","neutral":"bg-amber-50 border-amber-200","negative":"bg-red-50 border-red-200"}
        dots = {"positive":"bg-emerald-500","neutral":"bg-amber-500","negative":"bg-red-500"}
        sig_rows += f'''<div class="flex items-center gap-3 px-3 py-2 border-b border-gray-100 last:border-0 {colors[s['level']]}">
<span class="w-2.5 h-2.5 rounded-full {dots[s['level']]} flex-shrink-0"></span>
<span class="text-xs font-semibold text-gray-700 w-16">{s['label']}</span>
<span class="text-xs font-bold text-gray-900">{s['value']}</span>
<span class="ml-auto text-[10px] text-gray-500">{s['tag']}</span></div>'''
    
    # 主力资金区
    fund_html = ""
    if d.get("fund_flow") and d["fund_flow"]:
        f = d["fund_flow"]
        mx = max(f["inflow"], f["outflow"], 1)
        net_color = "text-emerald-600" if f["net"] > 0 else "text-red-600"
        fund_html = f'''<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 mb-3">
<div class="text-xs font-bold text-blue-600 mb-3">💰 主力资金（5日）</div>
<div class="flex gap-4 items-center">
<div class="flex-1">
<div class="flex justify-between text-[11px] mb-1"><span class="text-emerald-600">流入 +{f["inflow"]:.0f}万</span><span class="text-red-500">流出 -{f["outflow"]:.0f}万</span></div>
<div class="h-2 bg-gray-200 rounded-full flex overflow-hidden">
<div class="bg-emerald-500" style="width:{f['inflow']/mx*100}%"></div>
<div class="bg-red-400" style="width:{f['outflow']/mx*100}%"></div></div></div>
<div class="text-center min-w-[80px]"><div class="text-xl font-black {net_color}">{f['net']:+.0f}<span class="text-xs font-normal">万</span></div>
<div class="text-[10px] text-gray-400">{'主力做多' if f['net']>3000 else '主力观望' if f['net']>-3000 else '主力出逃'}</div></div></div></div>'''
    else:
        fund_html = '<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100 mb-3"><div class="text-xs text-gray-400">💰 主力资金数据获取中</div></div>'
    
    # 价位卡片
    price_cards = ""
    for label, val, pct, border, bg, color in [
        ("🛡️ 止损", p["stop_loss"], f'{p["stop_loss_pct"]:+.1f}%', "border-red-300", "bg-red-50", "text-red-600"),
        ("📥 低吸", p["entry_dip"], "支撑位", "border-blue-300", "bg-blue-50", "text-blue-600"),
        ("📈 现价", p["entry_now"], "当前价", "border-gray-200", "bg-white", "text-gray-800"),
        ("🚀 加仓", p["entry_add"], "+2%确认", "border-purple-300", "bg-purple-50", "text-purple-600"),
        ("🎯 止盈1", p["take_profit_1"], "+8% 卖50%", "border-emerald-300", "bg-emerald-50", "text-emerald-600"),
        ("🎯 止盈2", p["take_profit_2"], "+15% 清仓", "border-emerald-300", "bg-emerald-50", "text-emerald-600"),
    ]:
        price_cards += f'''<div class="text-center p-2.5 rounded-lg border {border} {bg}">
<div class="text-[9px] text-gray-500 uppercase tracking-wide">{label}</div>
<div class="text-base font-black {color} mt-0.5">¥{val:.2f}</div>
<div class="text-[10px] font-semibold {color}">{pct}</div></div>'''
    
    vc = a["verdict_color"]
    html = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{d['name']}</title>{TAILWIND_CDN}
<style>body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f3f4f6}}</style>
<script>tailwind.config={{theme:{{extend:{{}}}}}}</script></head>
<body class="max-w-lg mx-auto bg-gray-100 min-h-screen">
<div class="bg-gradient-to-br from-slate-900 to-blue-900 text-white px-5 py-5 flex justify-between items-center">
<div><h1 class="text-xl font-bold">{d['name']}</h1><div class="text-[10px] opacity-50 mt-0.5">{d['code']} · 深市主板</div></div>
<div class="text-right"><div class="text-3xl font-black tracking-tight">¥{d['price']:.2f}</div>
<div class="text-sm font-semibold mt-0.5" style="color:{'#34d399' if chg>=0 else '#f87171'}">{chg:+.1f}%</div></div></div>

<div class="p-3 space-y-3">

<!-- KPI Bento Grid -->
<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
<div class="grid grid-cols-4 gap-2 mb-3">
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">¥{d['high']:.2f}</div><div class="text-[9px] text-gray-400">最高</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">¥{d['low']:.2f}</div><div class="text-[9px] text-gray-400">最低</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{d['turnover']:.1f}%</div><div class="text-[9px] text-gray-400">换手率</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black" style="color:{'#10b981' if 0<d['pe']<30 else '#f59e0b' if d['pe']<60 else '#ef4444'}">{'PE'+str(int(d['pe'])) if d['pe']>0 else '-'}</div><div class="text-[9px] text-gray-400">市盈率</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{d['amount']/1e8:.1f}亿</div><div class="text-[9px] text-gray-400">成交额</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{'MA5' if d['price']>d.get('ma5',0) else 'MA5↓'}</div><div class="text-[9px] text-gray-400">¥{d.get('ma5',0):.2f}</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">{'MA20' if d['price']>d.get('ma20',0) else 'MA20↓'}</div><div class="text-[9px] text-gray-400">¥{d.get('ma20',0):.2f}</div></div>
<div class="text-center p-2 bg-gray-50 rounded-lg"><div class="text-sm font-black">ATR</div><div class="text-[9px] text-gray-400">¥{d.get('atr',0):.2f}</div></div>
</div>
{spark}
<div class="text-[10px] text-gray-400 text-center">8日走势 · {'上涨趋势' if chg>=0 else '下跌趋势'}</div>
</div>

<!-- 主力资金 -->
{fund_html}

<!-- 信号系统 -->
<div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
<div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
<span class="text-xs font-bold text-blue-600">🎯 多维信号</span>
<div class="flex gap-1.5 text-[10px]">
<span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded font-semibold">🟢 {a['positive_count']}</span>
<span class="px-2 py-0.5 bg-red-50 text-red-700 rounded font-semibold">🔴 {a['negative_count']}</span>
</div></div>
{sig_rows}</div>

<!-- 结论 -->
<div class="rounded-xl p-4 text-center font-black text-lg tracking-wide border-2" style="color:{vc};background:{vc}11;border-color:{vc}">
{a['verdict']}
<div class="text-xs font-normal text-gray-500 mt-1">综合信号 {a['positive_count']}/{a['total_count']}</div></div>

<!-- 价位卡片 -->
<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
<div class="text-xs font-bold text-blue-600 mb-3">📐 关键价位</div>
<div class="grid grid-cols-3 gap-2">{price_cards}</div></div>

<!-- 操作策略 -->
<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
<div class="text-xs font-bold text-blue-600 mb-3">📋 操作策略</div>
<div class="space-y-2">
<div class="flex items-center gap-2.5 p-2.5 bg-emerald-50 rounded-lg text-xs"><span class="w-5 h-5 bg-emerald-500 text-white rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0">1</span><b>低吸入场</b> 回踩 ¥{p['entry_dip']:.2f} 缩量企稳 → 建仓</div>
<div class="flex items-center gap-2.5 p-2.5 bg-red-50 rounded-lg text-xs"><span class="w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0">2</span><b>止损纪律</b> 跌破 ¥{p['stop_loss']:.2f} (2×ATR) → 无条件出局</div>
<div class="flex items-center gap-2.5 p-2.5 bg-amber-50 rounded-lg text-xs"><span class="w-5 h-5 bg-amber-500 text-white rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0">3</span><b>分批止盈</b> +8%卖50%锁利润 · +15%清仓 · 高点回落5%全卖</div>
<div class="flex items-center gap-2.5 p-2.5 bg-gray-100 rounded-lg text-xs"><span class="w-5 h-5 bg-gray-500 text-white rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0">4</span><b>仓位管理</b> 单只≤25% · 温度动态 · 盈利>5%移动止盈</div></div></div>

</div>
<div class="text-center text-[10px] text-gray-400 py-4">DAO量化助手 V3.0 · 仅供参考</div>
</body></html>'''
    return html


def render_png(html_path: str, output_path: str):
    """HTML → PNG 长图"""
    chrome = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    subprocess.run(["pkill","-9","-f","Chrome for Testing"], capture_output=True)
    pdf = "/tmp/_rpt_v3.pdf"
    subprocess.run([chrome,"--headless","--disable-gpu","--no-sandbox",
        f"--print-to-pdf={pdf}","--no-pdf-header-footer",f"file://{html_path}"],
        capture_output=True, timeout=25)
    
    doc = fitz.open(pdf); th=0; mw=0; pxs=[]
    for pg in doc: px=pg.get_pixmap(dpi=200); pxs.append(px); th+=px.height; mw=max(mw,px.width)
    mg = fitz.open(); mp = mg.new_page(width=mw, height=th); y=0
    for px in pxs: mp.insert_image(fitz.Rect(0,y,px.width,y+px.height),pixmap=px); y+=px.height
    mp.get_pixmap(dpi=200).save(output_path)
    doc.close(); mg.close(); Path(pdf).unlink()


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "002241"
    print(f"📊 生成 {code} 报告...")
    
    # 数据层
    data = StockDataFetcher.fetch(code)
    # 信号层
    analysis = SignalEngine.analyze(data)
    # 渲染层
    html = render_stock_report(data, analysis)
    
    html_path = f"/tmp/stock_v3_{code}.html"
    png_path = f"/tmp/stock_v3_{code}.png"
    with open(html_path, "w") as f: f.write(html)
    
    render_png(html_path, png_path)
    size = os.path.getsize(png_path)/1024
    print(f"✅ {size:.0f}KB")
