#!/usr/bin/env python3
"""打板预警+明日预测 V3"""
from collections import Counter
from mootdx.quotes import Quotes
from datetime import datetime
import json, urllib.request, ssl

ssl._create_default_https_context = ssl._create_unverified_context

def _fetch_ind(codes):
    r = {}
    for i in range(0, len(codes), 50):
        b = codes[i:i+50]
        try:
            s = ','.join(f'1.{c}' if c.startswith('6') else f'0.{c}' for c in b)
            u = f'https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f12,f100&secids={s}'
            d = json.loads(urllib.request.urlopen(u, timeout=5).read())
            r.update({x['f12']: x.get('f100','其他') for x in d.get('data',{}).get('diff',[])})
        except: pass
    return r

def _scan():
    c = Quotes.factory(market='std')
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    s = c.stocks()
    m = (s['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
         ~s['name'].str.contains('|'.join(ik), na=False) &
         ~s['name'].str.contains('ST|退', na=False))
    return c, s[m]['code'].astype(str).tolist(), dict(zip(s[m]['code'].astype(str), s[m]['name']))

def board_warn():
    c, codes, names = _scan()
    ap = []
    for code in codes:
        try:
            df = c.bars(symbol=code, frequency=9, start=0, offset=12)
            if df is None or df.empty or len(df) < 3: continue
            df = df.sort_index()
            lt = df.iloc[-1]; pr = df.iloc[-2]
            chg = (lt['close']/pr['close']-1)*100
            if not (5.0 <= chg < 9.5): continue
            rv = df['volume'].iloc[-4:-1].mean() if len(df)>=4 else pr['volume']
            vr = lt['volume']/rv if rv>0 else 1
            if chg<7 and vr<2.5: continue
            elif chg>=7 and vr<1.3: continue
            h,l = lt['high'],lt['low']
            sp = (lt['close']-l)/(h-l)*100 if h>l else 100
            sd = (lt['close']-df.iloc[-3]['close'])/df.iloc[-3]['close']*100 if len(df)>=3 else chg
            if chg<7 and sd<5: continue
            lp = round(pr['close']*1.099+0.007,2)
            dp = round((lp-lt['close'])/lt['close']*100,1)
            # 风险
            rc=rf=rd=rp=rs=0
            p2=df.iloc[-3] if len(df)>=4 else pr
            p3=df.iloc[-4] if len(df)>=5 else p2
            cy=(pr['close']/p2['close']-1)*100
            cyy=(p2['close']/p3['close']-1)*100
            cc=sum(1 for x in[cy,cyy] if x>=9.5)
            if cc>=2: rc=-20
            elif cc==1: rc=-12
            elif cy>=5: rc=-5
            ltoday=pr['close']*1.1
            if lt['high']>=ltoday*0.998 and chg<9.0: rf=-18
            elif lt['high']>=ltoday*0.995 and chg<8.0: rf=-12
            if vr>3 and sd<5: rd=-8
            elif vr>2 and sd<2: rd=-5
            if lt['close']>80: rp=-6
            elif lt['close']>50: rp=-3
            if sp<30: rs=-8
            elif sp<50: rs=-3
            sc = min((chg-5)*10,30)+min(vr*4,20)+min(sp*0.2,20)+min(sd*3,15)+max(15-dp*5,0)+rc+rf+rd+rp+rs
            ap.append({'code':code,'name':names.get(code,''),'chg':round(chg,1),'vr':round(vr,1),
                       'dist':dp,'score':round(sc,1),'speed':round(sd,1),
                       'rc':rc,'rf':rf,'rd':rd,'rs':rs,'res':1})
        except: pass
    if not ap: return f'⚡ {datetime.now().strftime("%m-%d %H:%M")}\n  暂无逼近标的'
    im = _fetch_ind([x['code'] for x in ap])
    scnt = Counter()
    for x in ap: x['sector']=im.get(x['code'],'其他'); scnt[x['sector']]+=1
    for x in ap:
        n=scnt[x['sector']]; x['res']=n
        x['score']=round(x['score']+(10 if n>=4 else(8 if n>=3 else(5 if n>=2 else 2))),1)
    ap.sort(key=lambda x:-x['score'])
    now = datetime.now().strftime('%m-%d %H:%M')
    sure=[]; buy=[]; watch=[]; avoid=[]
    for x in ap:
        has_r = x['rc']<0 or x['rf']<0 or x['rd']<0 or x['rs']<0
        strong = x['chg']>=6.5 and x['vr']>=2 and x['speed']>=8
        # 确定性买: 涨幅>=7%+量>=2.5x+速度>=10+无风险+板块>=2只共振
        definitive = x['chg']>=7.0 and x['vr']>=2.5 and x['speed']>=10 and not has_r and x['res']>=2
        ln = f'  {x["code"]} {x["name"]:<8} +{x["chg"]}% 量{x["vr"]}x {x["sector"]}'
        if definitive:
            sure.append(ln+f' ·{x["res"]}只共振 → 确定性买')
        elif strong and not has_r:
            buy.append(ln+(f' ·{x["res"]}只共振' if x['res']>=2 else ''))
        elif has_r:
            rsks = []
            if x['rf']<0: rsks.append('开板回落')
            if x['rc']<0: rsks.append('连板')
            if x['rd']<0: rsks.append('放量不涨')
            if x['rs']<0: rsks.append('低位起')
            avoid.append(ln+f' — {" ".join(rsks)}')
        else:
            watch.append(ln+(f' ·{x["res"]}只共振' if x['res']>=2 else ''))
    lines = [f'⚡ {now} | {len(ap)}只逼近']
    if sure: lines.append(f'\n👑 确定性买 ({len(sure)}只):'); [lines.append(l) for l in sure[:3]]
    if buy: lines.append(f'\n🟢 可买 ({len(buy)}只):'); [lines.append(l) for l in buy[:5]]
    if watch: lines.append(f'\n🟡 等 ({len(watch)}只):'); [lines.append(l) for l in watch[:5]]
    if avoid: lines.append(f'\n🔴 避 ({len(avoid)}只):'); [lines.append(l) for l in avoid[:5]]
    return '\n'.join(lines)

def next_day():
    c, codes, names = _scan()
    sd = []
    for code in codes:
        try:
            df = c.bars(symbol=code, frequency=9, start=0, offset=30)
            if df is None or df.empty or len(df)<3: continue
            df = df.sort_index()
            lt=df.iloc[-1]; pr=df.iloc[-2]
            chg=(lt['close']/pr['close']-1)*100
            lp=round(pr['close']*1.099+0.007,2)
            if lt['close']<lp*0.998: continue
            sh=14.5; sdur=10
            try:
                df1=c.bars(symbol=code,frequency=8,start=0,offset=240)
                if df1 is not None and not df1.empty:
                    df1=df1.sort_index()
                    for i,(idx,row) in enumerate(df1.iterrows()):
                        if row['close']>=lp*0.998:
                            sh=idx.hour+idx.minute/60
                            sdur=len(df1)-i if i<len(df1) else 0
                            break
            except: pass
            p2=df.iloc[-3] if len(df)>=4 else pr
            cy=(pr['close']/p2['close']-1)*100
            chain=1 if cy>=9.5 else 0
            vr=lt['volume']/pr['volume'] if pr['volume']>0 else 1
            sd.append({'code':code,'name':names.get(code,''),'price':round(lt['close'],2),
                       'chg':round(chg,1),'vr':round(vr,1),'chain':chain,
                       'sh':round(sh,1),'sdur':sdur})
        except: pass
    if not sd: return '📈 明日预测\n  暂无封板标的'
    im=_fetch_ind([x['code'] for x in sd])
    scnt=Counter()
    for x in sd: x['sector']=im.get(x['code'],'其他'); scnt[x['sector']]+=1
    for x in sd:
        sc=25 if x['chain']==0 else(10 if x['chain']==1 else-10)
        h=x['sh']
        st=25 if h<=10 else(20 if h<=11.5 else(10 if h<=14 else 5))
        sv=min(x['vr']*5,15)
        su=15 if x['sdur']>60 else(10 if x['sdur']>30 else 5)
        cnt=scnt[x['sector']]
        ss=10 if cnt>=3 else(5 if cnt>=2 else 0)
        x['prob']=min(sc+st+sv+su+ss,100)
        x['reason']=[]
        if x['chain']==0: x['reason'].append('首板')
        else: x['reason'].append(f'{x["chain"]+1}板')
        if x['sh']<=10: x['reason'].append('早封')
        elif x['sh']<=11: x['reason'].append('上午封')
        if x['vr']>=3: x['reason'].append(f'量{x["vr"]}x')
        if cnt>=3: x['reason'].append(f'{x["sector"]}共振')
    sd.sort(key=lambda x:-x['prob'])
    now=datetime.now().strftime('%m-%d %H:%M')
    sure=[x for x in sd if x['prob']>=85 and x['chain']==0 and x['sh']<=10.5]
    hi=[x for x in sd if x['prob']>=75]
    mi=[x for x in sd if 50<=x['prob']<75]
    lo=[x for x in sd if x['prob']<50]
    lines=[f'📈 明日高开预测 {now} | {len(sd)}只封板']
    if sure: lines.append(f'\n👑 确定性({len(sure)}只):'); [lines.append(f'  {x["code"]} {x["name"]:<8} {x["prob"]}% — {" ".join(x["reason"])}') for x in sure[:3]]
    if hi: lines.append(f'\n🟢 高概率({len(hi)}只):'); [lines.append(f'  {x["code"]} {x["name"]:<8} {x["prob"]}% — {" ".join(x["reason"])}') for x in hi[:5]]
    if mi: lines.append(f'\n🟡 中等({len(mi)}只):'); [lines.append(f'  {x["code"]} {x["name"]:<8} {x["prob"]}% — {" ".join(x["reason"])}') for x in mi[:5]]
    if lo: lines.append(f'\n⚪ 偏低({len(lo)}只):'); [lines.append(f'  {x["code"]} {x["name"]:<8} {x["prob"]}% — {" ".join(x["reason"])}') for x in lo[:3]]
    lines.append('\n💡 首板+早封=高溢价 | 尾盘封+连板=低溢价')
    return '\n'.join(lines)

def early_warn():
    """启动前/刚启动检测: +2%~+5% 量能突增+加速中"""
    c, codes, names = _scan()
    early = []
    for code in codes:
        try:
            df = c.bars(symbol=code, frequency=8, start=0, offset=120)
            if df is None or df.empty or len(df) < 10: continue
            df = df.sort_index()
            lt = df.iloc[-1]; pr = df.iloc[-2]
            chg = (lt['close']/pr['close']-1)*100
            if not (2.0 <= chg < 5.0): continue
            # 最近5分钟量能突增
            v5 = df['volume'].iloc[-5:].mean() if len(df)>=5 else lt['volume']
            v15 = df['volume'].iloc[-15:-5].mean() if len(df)>=15 else v5
            v_ratio = v5/v15 if v15>0 else 1
            if v_ratio < 3: continue  # 量能必须3x以上(启动信号)
            # 5分钟涨幅
            prev5 = df.iloc[-6]['close'] if len(df)>=6 else df.iloc[-3]['close']
            chg5 = (lt['close']-prev5)/prev5*100
            if chg5 < 1.5: continue  # 5分钟内涨幅<1.5%=没启动
            # 突破日内高点
            h_early = df['high'].iloc[:-5].max() if len(df)>=5 else df['high'].max()
            is_breakout = lt['close'] > h_early * 1.002
            # 距涨停空间
            lp = round(pr['close']*1.099+0.007,2)
            room = round((lp-lt['close'])/lt['close']*100,1)
            if room < 5: continue  # 不足5%空间, 放弃
            
            # 评分: 量突(30)+涨幅(20)+突破(20)+空间(15)+速度(15)
            sc = min(v_ratio*6,30) + min(chg*4,20) + (20 if is_breakout else 5) + min(room*2,15) + min(chg5*6,15)
            early.append({
                'code':code,'name':names.get(code,''),'chg':round(chg,1),'chg5':round(chg5,1),
                'vr':round(v_ratio,1),'room':room,'score':round(sc,1),
                'breakout':is_breakout,'price':round(lt['close'],2)
            })
        except: pass
    
    if not early:
        return f'🚀 启动检测 {datetime.now().strftime("%m-%d %H:%M")}\n  暂无+2%~+5%启动标的'
    
    # 行业
    im = _fetch_ind([x['code'] for x in early])
    scnt = Counter()
    for x in early: x['sector']=im.get(x['code'],'其他'); scnt[x['sector']]+=1
    for x in early: x['res']=scnt[x['sector']]
    
    early.sort(key=lambda x:-x['score'])
    now = datetime.now().strftime('%m-%d %H:%M')
    
    # 分级
    go = [x for x in early if x['score']>=50 and x['breakout'] and x['chg5']>=2.5]
    look = [x for x in early if x['score']>=35 and x not in go]
    skip = [x for x in early if x['score']<35]
    
    lines = [f'🚀 启动检测 {now} | {len(early)}只启动中']
    if go:
        lines.append(f'\n👑 可进 ({len(go)}只):')
        for x in go[:5]:
            btag = '突破' if x['breakout'] else ''
            lines.append(f'  {x["code"]} {x["name"]:<8} +{x["chg"]}% 量突{x["vr"]}x 空间{x["room"]}% {x["sector"]}{" ·"+btag if btag else ""}')
    if look:
        lines.append(f'\n🟡 观察 ({len(look)}只):')
        for x in look[:5]:
            lines.append(f'  {x["code"]} {x["name"]:<8} +{x["chg"]}% 量突{x["vr"]}x 空间{x["room"]}% {x["sector"]}')
    if skip:
        lines.append(f'\n⚪ 量能不足 ({len(skip)}只)')
    lines.append('\n👑 量突>3x+突破前高+5分钟涨>2.5%+空间>5% = 可进')
    return '\n'.join(lines)
