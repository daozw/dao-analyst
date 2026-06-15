#!/usr/bin/env python3
"""市场复盘PNG — 仪表盘风格，数据可视化"""
import sys, os, json, urllib.request, ssl
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.ft2font import FT2Font
import numpy as np

OUT = os.path.expanduser("~/.openclaw-autoclaw/workspace/reports")
os.makedirs(OUT, exist_ok=True)

def setup_font():
    for f in fm.findSystemFonts():
        for p in ['PingFang.ttc','STHeiti Medium.ttc','Hiragino Sans GB.ttc','STHeiti Light.ttc']:
            if f.endswith(p):
                try: FT2Font(f); plt.rcParams['axes.unicode_minus']=False; return fm.FontProperties(fname=f)
                except: pass
    plt.rcParams['axes.unicode_minus']=False; return None
fp = setup_font()

def g(u,t=8):
    try: return urllib.request.urlopen(u,timeout=t).read()
    except: return None

IND = ['pt01801080','pt01801050','pt01801054','pt01801081','pt01801082',
       'pt01801083','pt01801055','pt01801084','pt01801085','pt01801056',
       'pt01801057','pt01801058','pt01801059','pt01801060','pt01801061']

def fetch():
    raw = g(f'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,{",".join(IND)}',8)
    if not raw: return None
    idx,sec={},[]
    for ln in raw.decode('gbk').strip().split('\n'):
        d=ln.split('~')
        if len(d)<40: continue
        n,c,px,chg=d[1],d[2],float(d[3]),float(d[32])
        hi,lo,op,amt=float(d[33]or'0'),float(d[34]or'0'),float(d[5]),float(d[37]or'0')/1e8
        if c in('000001','399001','399006'):
            idx[c]={'name':n,'price':px,'chg':chg,'open':op,'high':hi,'low':lo,'amount':amt}
        elif d[32]: sec.append({'name':n,'chg':chg})
    sec.sort(key=lambda x:-x['chg'])
    return idx,sec

def fetch_zt():
    bf='data/state/board_scan.json'
    if not os.path.exists(bf): return None
    try:
        bs=json.load(open(bf)); s=bs.get('scanned',bs.get('candidates',[]))
        if not s: return None
        if isinstance(s[0],dict):
            return {'sealed':[c for c in s if c.get('zone')=='封板'],
                    'rushing':[c for c in s if c.get('zone')=='抢板'],'total':len(s)}
        codes=s[:12]
        q=','.join(f'sz{c}'if c.startswith(('0','3'))else f'sh{c}'for c in codes)
        raw=g(f'https://qt.gtimg.cn/q={q}',5)
        st={}
        if raw:
            for ln in raw.decode('gbk').strip().split('\n'):
                d=ln.split('~')
                if len(d)>40: st[d[2]]=(d[1],float(d[32]))
        items=[]
        for c in codes[:10]:
            v=st.get(c,(c,0)); items.append({'code':c,'name':v[0],'chg':v[1]})
        items.sort(key=lambda x:-x['chg'])
        return {'items':items,'total':len(s)}
    except: return None

def draw():
    now=datetime.now(); ds,ts=now.strftime('%Y%m%d'),now.strftime('%H:%M')
    r=fetch()
    if not r: return print('no data')
    idx,sec=r; zt=fetch_zt()
    avg=sum(d['chg']for d in idx.values())/3
    if avg>2: mood,mc='🔥 强势','#6bcb77'
    elif avg>0.5: mood,mc='✅ 温和','#7ec98f'
    elif avg>-0.5: mood,mc='⚡ 震荡','#f0a040'
    elif avg>-2: mood,mc='⚠️ 弱势','#ff6b6b'
    else: mood,mc='🚨 下跌','#ff3333'

    fig=plt.figure(figsize=(10,9.5),dpi=150)
    fig.patch.set_facecolor('#0d1117')
    wd=datetime.now().strftime('%A')

    # 顶栏
    fig.text(0.08,0.96,f'{ts} {wd}',fontproperties=fp,fontsize=10,color='#8b949e')
    fig.text(0.50,0.96,'📊 A股收盘复盘',fontproperties=fp,fontsize=18,color='white',ha='center',fontweight='bold')
    fig.text(0.50,0.92,f'平均{avg:+.2f}%  {mood}',fontproperties=fp,fontsize=11,color=mc,ha='center')

    # 情绪渐变条
    ax_m=fig.add_axes([0.25,0.945,0.50,0.012])
    ax_m.set_xlim(-3,3); ax_m.set_ylim(0,1); ax_m.axis('off')
    for xi in np.linspace(-3,3,60):
        c='#ff6b6b'if xi<-1 else'#f0a040'if xi<0 else'#7ec98f'if xi<1 else'#6bcb77'
        ax_m.axvline(xi,color=c,alpha=0.15,linewidth=2)
    ax_m.axvline(0,color='#484f58',linewidth=0.5)
    ax_m.plot(avg,0.5,'o',color=mc,markersize=10,zorder=5)
    ax_m.plot(avg,0.5,'o',color='white',markersize=4,zorder=6)

    # 三大指数卡片
    cfg=[('000001','上证','#ff6b6b'),('399001','深证','#ffd93d'),('399006','创业板','#6bcb77')]
    for i,(code,label,color) in enumerate(cfg):
        d=idx.get(code)
        if not d: continue
        x=0.07+i*0.31; sign='+'if d['chg']>=0 else''
        card=plt.Rectangle((x-0.02,0.76),0.28,0.13,fill=True,
                    facecolor='#161b22',edgecolor='#30363d',linewidth=0.5,transform=fig.transFigure)
        fig.patches.append(card)
        fig.text(x,0.86,label,fontproperties=fp,fontsize=10,color=color,fontweight='bold')
        fig.text(x,0.83,f'{d["price"]:,.0f}',fontproperties=fp,fontsize=22,color=color,fontweight='bold')
        fig.text(x+0.11,0.83,f'{sign}{d["chg"]:.2f}%',fontproperties=fp,fontsize=12,color=color,fontweight='bold')
        fig.text(x,0.79,f'开{d["open"]:,.0f} 高{d["high"]:,.0f} 低{d["low"]:,.0f}',
                 fontproperties=fp,fontsize=6.5,color='#8b949e')
        fig.text(x,0.77,f'成交¥{d["amount"]:.0f}亿',fontproperties=fp,fontsize=6.5,color='#8b949e')

    # 板块柱状图
    ax_s=fig.add_axes([0.08,0.47,0.86,0.26])
    ax_s.set_facecolor('#0d1117')
    ax_s.set_title('行业板块涨幅',fontproperties=fp,fontsize=13,color='#d2a8ff',fontweight='bold',pad=5,loc='left')
    ax_s.tick_params(colors='#8b949e',labelsize=8)
    if sec:
        names=[s['name']for s in sec[:12]]
        vals=[s['chg']for s in sec[:12]]
        colors=['#6bcb77'if v>=0 else'#ff6b6b'for v in vals]
        ax_s.barh(range(len(names)),vals,height=0.6,color=colors,alpha=0.7)
        ax_s.set_yticks(range(len(names)))
        ax_s.set_yticklabels(names,fontproperties=fp,fontsize=9)
        ax_s.invert_yaxis()
        ax_s.axvline(0,color='#484f58',linewidth=0.3)
        for i,(v,c)in enumerate(zip(vals,colors)):
            sign='+'if v>=0 else''
            ax_s.text(v+(0.2 if v>=0 else-0.2),i,f'{sign}{v:.2f}%',
                     fontproperties=fp,fontsize=8,color=c,va='center',
                     ha='left'if v>=0 else'right',fontweight='bold')
        ax_s.spines['top'].set_visible(False)
        ax_s.spines['right'].set_visible(False)
        ax_s.spines['left'].set_color('#30363d')
        ax_s.spines['bottom'].set_color('#30363d')

    # 涨停候选
    ax_z=fig.add_axes([0.08,0.15,0.50,0.28])
    ax_z.set_facecolor('#0d1117')
    ax_z.set_title('涨停板候选',fontproperties=fp,fontsize=13,color='#ff6b6b',fontweight='bold',pad=5,loc='left')
    ax_z.axis('off')
    if zt:
        items=zt.get('items',[])
        sealed=zt.get('sealed',[]); rushing=zt.get('rushing',[])
        if sealed or rushing:
            all_items=sealed+rushing
            for i,s in enumerate(all_items[:6]):
                ry=0.85-i*0.13; nm=s.get('name','?'); ch=s.get('chg',0)
                zn=s.get('zone',''); sign='+'if ch>=0 else''
                c='#ff6b6b'if zn=='封板'else'#f0a040'
                ax_z.text(0,ry,nm,fontproperties=fp,fontsize=9,color=c,transform=ax_z.transAxes)
                ax_z.text(0.5,ry,f'{sign}{ch:.1f}%',fontproperties=fp,fontsize=9,color=c,transform=ax_z.transAxes,fontweight='bold')
                ax_z.text(0.7,ry,zn,fontproperties=fp,fontsize=8,color='#8b949e',transform=ax_z.transAxes)
        elif items:
            for i,s in enumerate(items[:6]):
                ry=0.85-i*0.13; nm=s.get('name','?'); ch=s.get('chg',0)
                sign='+'if ch>=0 else''; c='#6bcb77'if ch>=0 else'#ff6b6b'
                ax_z.text(0,ry,nm,fontproperties=fp,fontsize=9,color=c,transform=ax_z.transAxes)
                ax_z.text(0.55,ry,f'{sign}{ch:.1f}%',fontproperties=fp,fontsize=9,color=c,transform=ax_z.transAxes,fontweight='bold')

    # 总览面板
    ax_o=fig.add_axes([0.62,0.15,0.32,0.28])
    ax_o.set_facecolor('#0d1117')
    ax_o.set_title('今日总览',fontproperties=fp,fontsize=13,color='#79c0ff',fontweight='bold',pad=5,loc='left')
    ax_o.axis('off')
    ts2=['市场: '+mood,f'平均: {avg:+.2f}%']
    if sec: ts2.append(f'领涨: {sec[0]["name"]} {sec[0]["chg"]:+.1f}%')
    if zt: ts2.append(f'涨停候选: {zt.get("total",0)}只')
    try:
        from market_thermometer_v2 import get_thermometer
        t=get_thermometer(); ts2.append(f'温度: {t.get("level","?")}')
    except: pass
    for i,tx in enumerate(ts2):
        ax_o.text(0.05,0.85-i*0.16,tx,fontproperties=fp,fontsize=10,color='#c9d1d9',transform=ax_o.transAxes)

    # 底部
    fig.text(0.5,0.02,'⚠️ 仅供参考，不构成投资建议 | 股市有风险，投资需谨慎',
             fontproperties=fp,fontsize=6.5,color='#484f58',ha='center')
    fig.text(0.08,0.02,f'DAOV3.3 · {ts} · 腾讯行情',fontproperties=fp,fontsize=6.5,color='#484f58')

    path=os.path.join(OUT,f'market_report_{ds}.png')
    fig.savefig(path,dpi=150,bbox_inches='tight',facecolor='#0d1117',edgecolor='none')
    plt.close(fig)
    return path

if __name__=='__main__':
    p=draw()
    print(f'✅ {p}'if p else'❌')
