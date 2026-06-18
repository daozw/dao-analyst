#!/usr/bin/env python3
"""
梯队复盘 V1.1 — 基于股票池快速扫描
运行: 收盘后 15:05
"""
import sys,fcntl,os,json,urllib.request,ssl,time,re
from datetime import datetime
from collections import defaultdict
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALERT_FILE='/tmp/dao_trade_alerts.json'

SECTOR_KW = {
    '电力':['电力','能源','发电','水电','火电','核电','风光'],
    '煤炭':['煤炭','煤业'],
    '银行':['银行'],
    '机器人':['机器','机器','智能'],
    '芯片':['芯片','半导'],
    'AI算力':['AI','算力','GPU'],
    '新能源':['锂电','电池','新能源','汽配'],
    '军工':['军工','航天','航空'],
    '医药':['医药','生物','医疗'],
    '消费':['食品','饮料','白酒'],
    '地产':['地产','房产','建材'],
    '金融':['证券','保险','信托'],
    '化工':['化工','材料','新材'],
    '传媒':['传媒','影视','广电'],
    '通信':['通信','5G','光纤'],
    '稀土':['稀土','磁材'],
    '农业':['农业','种业','养猪'],
}

def get_sector(name):
    for s,kws in SECTOR_KW.items():
        if any(k in name for k in kws): return s
    return '其他'

def batch_prices(codes, bs=40):
    r={}
    for i in range(0,len(codes),bs):
        b=codes[i:i+bs]
        s=','.join([f'sh{c}' if c.startswith('6') else f'sz{c}' for c in b])
        try:
            req=urllib.request.Request(f'https://qt.gtimg.cn/q={s}')
            raw=urllib.request.urlopen(req,timeout=8).read().decode('gbk')
            time.sleep(0.3)  # 限流
            for ln in raw.strip().split('\n'):
                d=ln.split('~')
                if len(d)<40: continue
                try:
                    r[d[2]]={
                        'code':d[2],'name':d[1],'price':float(d[3]),
                        'chg':float(d[32]),'turn':float(d[38]) if d[38].replace('.','').isdigit() else 0,
                        'vol_ratio':float(d[49]) if len(d)>49 and d[49].replace('.','').replace('-','').isdigit() else 1,
                    }
                except: pass
        except: pass
    return r

def get_yesterday_boards():
    y=[]
    if os.path.exists(ALERT_FILE):
        try:
            for a in json.load(open(ALERT_FILE)):
                if a.get('action')=='BOARD':
                    for c in re.findall(r'\((\d{6})\)',a.get('message','')):
                        if c not in [x['code'] for x in y]: y.append({'code':c,'name':''})
        except: pass
    return y

def main():
    # 加载全池股票
    wl=json.load(open('data/watchlist.json'))
    all_codes,seen=[],set()
    for gn,g in wl.get('groups',{}).items():
        if gn=='exclude': continue
        for s in g.get('stocks',[]):
            c=s['code']
            if c.startswith(('300','688','8')) or c in seen: continue
            seen.add(c)
            all_codes.append({'code':c,'name':s['name']})
    
    prices=batch_prices([s['code'] for s in all_codes])
    
    # 分类
    boards=[p for p in prices.values() if p['chg']>=9.5]
    downs=[p for p in prices.values() if p['chg']<=-9.5]
    
    today_codes={b['code'] for b in boards}
    yesterday_codes={s['code'] for s in get_yesterday_boards()}
    
    # 按板块分组
    sec_boards=defaultdict(list)
    for b in boards:
        sec_boards[get_sector(b['name'])].append(b)
    
    promoted=[b for b in boards if b['code'] in yesterday_codes]
    sec_promoted=defaultdict(list)
    for p in promoted:
        sec_promoted[get_sector(p['name'])].append(p)
    
    danger=[d for d in downs if d.get('turn',0)>5]
    
    lines=[]
    lines.append(f"⚔️ 梯队复盘 | {datetime.now().strftime('%m/%d %H:%M')}")
    lines.append(f"🤖 DAO分析师 V3.3 — 扫描{len(all_codes)}只")
    lines.append("")
    
    # ① 晋级
    lines.append("━ ① 晋级榜 ━")
    lines.append("首板=播种  二板=出苗  出苗越多板块越肥")
    lines.append("")
    ranked=sorted(sec_promoted.items(),key=lambda x:len(x[1]),reverse=True)
    if promoted:
        for sec,stocks in ranked[:4]:
            if not stocks: continue
            names=' · '.join([f"{s['name']}({s['turn']:.1f}%)" for s in stocks[:4]])
            lines.append(f"  ✅ {sec}: {len(stocks)}只晋级  {names}")
    else:
        lines.append("  今日无晋级 → 休息或板块轮动")
    lines.append("")
    
    # ② 跌停
    lines.append("━ ② 跌停警报 ━")
    lines.append("高换手+跌停 = 主力撤退信号")
    lines.append("")
    if danger:
        for d in danger[:5]:
            lines.append(f"  ⚠️ {d['name']}({d['code']}) 换手{d['turn']:.1f}% 跌{d['chg']:.1f}%")
    else:
        lines.append("  ✅ 无高换手跌停")
    lines.append("")
    
    # ③ 梯队
    lines.append("━ ③ 板块梯队 ━")
    lines.append("金字塔: 龙头→中位→跟风  缺一不可")
    lines.append("")
    for sec in sorted(sec_boards,key=lambda x:len(sec_boards[x]),reverse=True):
        stocks=sec_boards[sec]
        if len(stocks)<2: continue
        names=' · '.join([f"{s['name']}" for s in stocks[:5]])
        status='🔥' if len(stocks)>=4 else '🟡' if len(stocks)>=2 else ''
        lines.append(f"  {status} {sec}({len(stocks)}只): {names}")
    lines.append("")
    
    # ④ 判断
    lines.append("━ ④ 综合判断 ━")
    n=len(boards)
    if n>=20: mood='🔥 涨停活跃  可积极打板'
    elif n>=8: mood='🟡 温和  精选板块打板'
    elif n>=3: mood='🟠 偏弱  控制仓位'
    else: mood='🔴 极弱  休息不打新板'
    top3=[f"{s}({len(stocks)})" for s,stocks in sorted(sec_boards.items(),key=lambda x:len(x[1]),reverse=True)[:3]]
    lines.append(f"  涨停{n}只  {mood}")
    if top3: lines.append(f"  主线: {' > '.join(top3)}")
    lines.append("")
    lines.append("─"*20)
    lines.append("以上仅供参考  股市有风险")
    
    report='\n'.join(lines)
    print(report)
    
    try:
        al=[]
        if os.path.exists(ALERT_FILE):
            try: al=json.load(open(ALERT_FILE))
            except: pass
        al.append({'time':datetime.now().strftime('%H:%M'),'action':'TIER_REVIEW','message':report,'sent':False})
        with open(ALERT_FILE,'w') as f: json.dump(al,f,ensure_ascii=False,indent=2)
    except: pass
    return report

if __name__=="__main__":
    main()
