"""管道阶段4: HTML渲染 — 卡片布局重设计"""
from datetime import datetime
TW = '<script src="https://cdn.tailwindcss.com"></script>'

def _spark(klines):
    if not klines: return ""
    cs=[k["c"] for k in klines[-8:]]; mn,mx=min(cs),max(cs)
    rg=mx-mn if mx>mn else 1; sc="#ef4444" if cs[-1]>=cs[0] else "#10b981"
    w,h=200,28; pts=" ".join(f"{int(i*w/max(len(cs)-1,1))},{int(h-(c-mn)/rg*h)}" for i,c in enumerate(cs))
    return f'<div class="mt-1.5"><svg viewBox="0 0 {w} {h}" class="w-full h-7"><defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{sc}" stop-opacity="0.1"/><stop offset="100%" stop-color="{sc}" stop-opacity="0"/></linearGradient></defs><polygon points="0,{h} {pts} {w},{h}" fill="url(#sg)"/><polyline points="{pts}" fill="none" stroke="{sc}" stroke-width="1.5"/></svg></div>'

def stock(d, a, llm):
    p=d; chg=p["chg"]; pr=a["prices"]; f=p.get("fund")
    t=datetime.now().strftime("%m/%d %H:%M")
    rc="#ef4444" if chg>=0 else "#10b981"
    vc=a["verdict_color"]
    
    # ── 头部 ──
    html=f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{p["name"]}</title>{TW}
<style>body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;margin:0}}
.card{{background:#fff;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:10px;overflow:hidden}}
.card-head{{padding:12px 16px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:700;color:#1d4ed8;display:flex;align-items:center;gap:6px}}
.card-body{{padding:12px 16px}}
.kpi{{text-align:center;padding:10px 4px;background:#f8fafc;border-radius:10px}}
.kpi-val{{font-size:14px;font-weight:800}}
.kpi-sub{{font-size:10px;color:#94a3b8;margin-top:2px}}
.price-row{{display:flex;align-items:center;padding:9px 12px;border-bottom:1px solid #f8fafc;font-size:12px}}
.price-row:last-child{{border-bottom:none}}
.price-label{{font-weight:700;min-width:80px}}
.price-val{{font-weight:800;text-align:right;min-width:70px}}
.price-desc{{color:#64748b;margin-left:auto;font-size:11px}}
.sig-row{{display:flex;align-items:center;gap:10px;padding:7px 12px;border-bottom:1px solid #f8fafc;font-size:12px}}
.sig-row:last-child{{border-bottom:none}}
.sig-dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0}}
.sig-label{{font-weight:600;color:#334155;min-width:65px;font-size:12px}}
.sig-val{{font-weight:700;font-size:12px}}
.sig-tag{{margin-left:auto;font-size:10px;color:#94a3b8}}
.header-top{{background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;padding:50px 18px 16px}}
.verdict-box{{text-align:center;padding:14px;border-radius:12px;font-size:16px;font-weight:800;margin-bottom:10px;border:2px solid}}
@page{{size:600px 4000px;margin:0}}</style></head><body class="max-w-[600px] mx-auto">
<div class="header-top">
<div style="display:flex;justify-content:space-between;align-items:flex-end">
<div><div style="font-size:21px;font-weight:700">{p["name"]}</div><div style="font-size:11px;opacity:.5;margin-top:2px">{p["code"]} · 深市 · {t}</div></div>
<div style="text-align:right"><div style="font-size:28px;font-weight:800;letter-spacing:-1px">¥{p["price"]:.2f}</div><div style="font-size:13px;font-weight:600;margin-top:2px;color:{rc}">{chg:+.1f}%</div></div>
</div></div>
<div style="padding:0 12px 20px">'''
    
    # ── KPI卡片 ──
    html+='<div class="card"><div class="card-head">📊 实时行情</div><div class="card-body">'
    kpis=[("{:.1f}%".format(p["turnover"]),"换手率",""),(("PE"+str(int(p["pe"])) if p["pe"]>0 else "-"),"市盈率","color:#ef4444" if 0<p["pe"]<30 else ("color:#d97706" if p["pe"]<60 else "color:#10b981")),("{:.0f}亿".format(p["amount"]/1e8*10000),"成交额",""),("¥{:.2f}".format(p.get("ma5",p["price"])),"MA5","color:#ef4444" if p["price"]>p.get("ma5",0) else "color:#10b981"),("¥{:.2f}".format(p.get("ma20",p["price"])),"MA20","color:#ef4444" if p["price"]>p.get("ma20",0) else "color:#d97706"),("¥{:.2f}".format(p.get("atr",0)),"ATR",""),("¥{:.2f}".format(p["high"]),"最高",""),("¥{:.2f}".format(p["low"]),"最低","")]
    html+='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">'
    for v,l,c in kpis: html+=f'<div class="kpi"><div class="kpi-val" style="{c}">{v}</div><div class="kpi-sub">{l}</div></div>'
    html+='</div>'+_spark(p.get("klines",[]))+'</div></div>'
    
    # ── 资金卡片 ──
    if f:
        mx=max(f["in"],f["out"],1); nc="#ef4444" if f["net"]>0 else "#10b981"
        html+=f'<div class="card"><div class="card-head">💰 主力资金 (近5日)</div><div class="card-body"><div style="display:flex;gap:12px;align-items:center"><div style="flex:1"><div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px"><span style="color:#ef4444">流入 +{f["in"]:.0f}万</span><span style="color:#10b981">流出 -{f["out"]:.0f}万</span></div><div style="height:7px;background:#e2e8f0;border-radius:4px;display:flex;overflow:hidden"><div style="width:{f["in"]/mx*100:.0f}%;background:#ef4444"></div><div style="width:{f["out"]/mx*100:.0f}%;background:#10b981"></div></div></div><div style="text-align:center;min-width:70px"><div style="font-size:18px;font-weight:800;color:{nc}">{f["net"]:+.0f}<span style="font-size:10px;font-weight:400">万</span></div><div style="font-size:10px;color:#94a3b8">{"做多" if f["net"]>3000 else "观望" if f["net"]>-3000 else "出逃"}</div></div></div></div></div>'
    
    # ── 价位表 ──
    html+='<div class="card"><div class="card-head">📐 六档价位</div><div class="card-body" style="padding:0">'
    for l,v,desc,bg,tc in [("🔴 高抛",pr["high_sell"],"量能不足止盈","#fef2f2","#dc2626"),("🟡 突破",pr["breakthrough"],"站稳+回流跟进","#fffbeb","#d97706"),("⚪ 现价",pr["current"],"忌盲目追高","#f8fafc","#475569"),("🟢 建仓",pr["first_entry"],"止跌阳线试探","#f0fdf4","#059669"),("💎 黄金坑",pr["golden_pit"],"缩量企稳加仓","#f0fdf4","#059669"),("🛑 止损",pr["stop_loss"],"破位坚决离场","#fef2f2","#dc2626")]:
        html+=f'<div class="price-row" style="background:{bg}"><span class="price-label">{l}</span><span class="price-val" style="color:{tc}">¥{v:.2f}</span><span class="price-desc">{desc}</span></div>'
    html+='</div></div>'
    
    # ── 信号 ──
    html+='<div class="card"><div class="card-head">🎯 技术信号 <span style="margin-left:auto;font-size:10px;display:flex;gap:4px"><span style="background:#fef2f2;color:#dc2626;padding:1px 6px;border-radius:4px">🟢{}</span><span style="background:#f0fdf4;color:#059669;padding:1px 6px;border-radius:4px">🔴{}</span></span></div><div class="card-body" style="padding:0">'.format(a["g"],a["r"])
    for s in a["signals"]:
        bg2={"g":"#fef2f2","r":"#f0fdf4","y":"#fffbeb"}.get(s["lv"],"")
        dot={"g":"#ef4444","r":"#10b981","y":"#d97706"}.get(s["lv"],"#cbd5e1")
        html+=f'<div class="sig-row" style="background:{bg2}"><span class="sig-dot" style="background:{dot}"></span><span class="sig-label">{s["label"]}</span><span class="sig-val">{s["val"]}</span><span class="sig-tag">{s["tag"]}</span></div>'
    html+='</div></div>'
    
    # ── 结论 ──
    html+=f'<div class="verdict-box" style="color:{vc};background:{vc}11;border-color:{vc}">{a["verdict"]}<div style="font-size:11px;font-weight:400;color:#64748b;margin-top:2px">{a["g"]}/{a["total"]} 信号</div></div>'
    
    # ── 操作建议 ──
    html+=f'<div class="card"><div class="card-head">📋 操作建议</div><div class="card-body" style="font-size:12px;color:#334155;line-height:1.8"><p>📥 <b>建仓:</b> 回踩 ¥{pr["first_entry"]:.2f} 缩量企稳</p><p>🛡️ <b>止损:</b> 跌破 ¥{pr["stop_loss"]:.2f} 无条件出局</p><p>💰 <b>止盈:</b> ¥{pr["take_profit_1"]:.2f}(+8%)卖50% · ¥{pr["take_profit_2"]:.2f}(+15%)清仓</p><p>📊 <b>仓位:</b> 单只≤25% · 温度动态 · 缩量跌买/放量涨卖</p></div></div>'
    
    html+='</div><div style="text-align:center;font-size:10px;color:#94a3b8;padding:12px">DAO V3 · 免费API · 仅供参考</div></body></html>'
    return html

def market(data):
    d=data; now=datetime.now().strftime("%m/%d %H:%M")
    idx=d.get("index",{}); ic=idx.get("chg",0); idx_c="#ef4444" if ic>=0 else "#10b981"
    html=f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>市场全景</title>{TW}<style>body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;margin:0}}.card{{background:#fff;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:10px;overflow:hidden}}.card-head{{padding:12px 16px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:700;color:#1d4ed8}}@page{{size:600px 4000px;margin:0}}</style></head><body class="max-w-[600px] mx-auto">
<div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;padding:50px 18px 16px;text-align:center">
<div style="font-size:21px;font-weight:700">📊 市场全景</div><div style="font-size:11px;opacity:.5;margin-top:4px">{now}</div>
<div style="display:flex;justify-content:center;gap:24px;margin-top:12px"><div><div style="font-size:24px;font-weight:800">{idx.get("price",0):.0f}</div><div style="font-size:10px;opacity:.6">上证</div></div><div><div style="font-size:18px;font-weight:700;color:{idx_c}">{ic:+.2f}%</div><div style="font-size:10px;opacity:.6">涨跌</div></div></div></div>
<div style="padding:0 12px 20px">'''
    if d.get("hot"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{h["name"]}</td><td style="padding:8px 12px;text-align:right;font-size:12px;font-weight:700;color:{"#ef4444" if h.get("chg",0)>=0 else "#10b981"}">{h.get("chg",0):+.1f}%</td></tr>' for i,h in enumerate(d["hot"][:10],1))
        html+=f'<div class="card"><div class="card-head">🔥 社区热度 TOP10</div><table width="100%">{rows}</table></div>'
    html+='</div><div style="text-align:center;font-size:10px;color:#94a3b8;padding:12px">DAO V3</div></body></html>'
    return html

def nightly(data):
    d=data; now=datetime.now().strftime("%m/%d %H:%M")
    idx=d.get("index",{}); ic=idx.get("chg",0); idx_c="#ef4444" if ic>=0 else "#10b981"
    # 成交额：腾讯API返回万元，/1e4转亿
    amt = idx.get("amount",0) / 1e4
    html=f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>深夜情报</title>{TW}<style>body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;margin:0}}.card{{background:#fff;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:10px;overflow:hidden}}.card-head{{padding:12px 16px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:700;color:#1d4ed8}}@page{{size:600px 4000px;margin:0}}</style></head><body class="max-w-[600px] mx-auto">
<div style="background:linear-gradient(135deg,#1e1b4b,#0f172a);color:#fff;padding:50px 18px 16px;text-align:center"><div style="font-size:21px;font-weight:700">🌙 深夜情报站</div><div style="font-size:11px;opacity:.5;margin-top:4px">{now}</div></div>
<div style="padding:0 12px 20px">'''
    # 指数概览卡片
    html+=f'<div class="card" style="text-align:center;padding:20px 16px">'
    html+=f'<div style="font-size:36px;font-weight:800;color:#1e1b4b">{idx.get("price",0):.0f}</div>'
    html+=f'<div style="font-size:18px;font-weight:700;color:{idx_c};margin:6px 0">{ic:+.2f}%</div>'
    html+=f'<div style="display:flex;justify-content:space-around;margin-top:14px;padding-top:12px;border-top:1px solid #f1f5f9">'
    html+=f'<div><div style="font-size:11px;color:#94a3b8">最高</div><div style="font-size:14px;font-weight:600;color:#ef4444">{idx.get("high",0):.0f}</div></div>'
    html+=f'<div><div style="font-size:11px;color:#94a3b8">最低</div><div style="font-size:14px;font-weight:600;color:#10b981">{idx.get("low",0):.0f}</div></div>'
    html+=f'<div><div style="font-size:11px;color:#94a3b8">成交额</div><div style="font-size:14px;font-weight:600">{amt:.0f}亿</div></div>'
    html+=f'</div></div>'
    # 深证/创业
    html+=f'<div style="display:flex;gap:10px;margin-bottom:10px">'
    for k in ["sz_index","cy_index"]:
        if d.get(k):
            idx2=d[k]; ic2=idx2.get("chg",0); c2="#ef4444" if ic2>=0 else "#10b981"
            html+=f'<div class="card" style="flex:1;text-align:center;padding:12px 8px">'
            html+=f'<div style="font-size:10px;color:#94a3b8">{idx2["name"]}</div>'
            html+=f'<div style="font-size:16px;font-weight:800;margin:4px 0">{idx2["price"]:.0f}</div>'
            html+=f'<div style="font-size:12px;font-weight:700;color:{c2}">{ic2:+.2f}%</div></div>'
    html+=f'</div>'
    # 概念人气（换手率榜）
    if d.get("concept_hot"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{s["name"]}<span style="font-size:10px;color:#94a3b8;margin-left:4px">{s.get("code","")}</span></td><td style="padding:8px 10px;text-align:right;font-size:11px;font-weight:600">{s.get("turnover",0):.1f}<span style="font-size:9px;color:#94a3b8">%</span></td><td style="padding:8px 12px;text-align:right;font-size:12px;font-weight:700;color:{"#ef4444" if s.get("chg",0)>=0 else "#10b981"}">{s.get("chg",0):+.1f}%</td></tr>' for i,s in enumerate(d["concept_hot"][:8],1))
        html+=f'<div class="card"><div class="card-head">💬 概念人气 (换手率)</div><table width="100%">{rows}</table></div>'
    # 人气排行
    if d.get("popular_stocks"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{s["name"]}<span style="font-size:10px;color:#94a3b8;margin-left:4px">{s.get("code","")}</span></td><td style="padding:8px 10px;text-align:right;font-size:11px;font-weight:600">{s.get("vol",0):.0f}<span style="font-size:9px;color:#94a3b8">万手</span></td><td style="padding:8px 12px;text-align:right;font-size:12px;font-weight:700;color:{"#ef4444" if s.get("chg",0)>=0 else "#10b981"}">{s.get("chg",0):+.1f}%</td></tr>' for i,s in enumerate(d["popular_stocks"][:10],1))
        html+=f'<div class="card"><div class="card-head">📈 人气排行 (成交量)</div><table width="100%">{rows}</table></div>'
    # 今日热度股
    if d.get("hot_stocks"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{s["name"]}</td><td style="padding:8px 12px;text-align:right;font-size:11px;font-weight:600;color:#ef4444">{"涨停" if s.get("chg",0)>=19.9 else str(round(s.get("chg",0),1))+"%"}</td></tr>' for i,s in enumerate(d["hot_stocks"][:8],1))
        html+=f'<div class="card"><div class="card-head">🔥 雪球热榜</div><table width="100%">{rows}</table></div>'
    # 行业板块
    if d.get("hot"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{h["name"]}</td><td style="padding:8px 12px;text-align:right;font-size:12px;font-weight:700;color:{"#ef4444" if h.get("chg",0)>=0 else "#10b981"}">{h.get("chg",0):+.1f}%</td></tr>' for i,h in enumerate(d["hot"][:10],1))
        html+=f'<div class="card"><div class="card-head">🔥 行业板块涨跌幅</div><table width="100%">{rows}</table></div>'
    # 核心资产
    if d.get("popular"):
        rows="".join(f'<tr><td style="padding:8px 12px;font-size:12px;color:#94a3b8">{i}</td><td style="padding:8px 12px;font-size:12px;font-weight:600">{p["name"]}</td><td style="padding:8px 12px;text-align:right;font-size:12px;font-weight:700;color:{"#ef4444" if p.get("chg",0)>=0 else "#10b981"}">{p.get("chg",0):+.2f}%</td></tr>' for i,p in enumerate(d["popular"][:10],1))
        html+=f'<div class="card"><div class="card-head">💎 核心资产</div><table width="100%">{rows}</table></div>'
    html+=f'<div style="text-align:center;padding:12px;font-size:10px;color:#94a3b8">DAO V3 · 数据来源:腾讯/新浪行情</div>'
    html+='</div>'
    return html
