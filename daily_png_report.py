#!/usr/bin/env python3
"""收盘复盘PNG — 大盘+持仓+信号+简评+风险，每天15:50自动出图"""
import sys, os, json, urllib.request, ssl
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

OUT = os.path.expanduser("~/.openclaw-autoclaw/workspace/reports")
os.makedirs(OUT, exist_ok=True)

def setup_chinese_font():
    for f in fm.findSystemFonts():
        if 'PingFang' in f or 'Heiti' in f or 'STHeiti' in f:
            return fm.FontProperties(fname=f)
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False
    return None

fp = setup_chinese_font()

def get(url, timeout=5):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return r.read()
    except:
        return None

# ═══════════════════════════════════════════════
# 数据源
# ═══════════════════════════════════════════════

def fetch_quotes(codes):
    q = ','.join(codes)
    raw = get(f'https://qt.gtimg.cn/q={q}', 6)
    if not raw: return {}
    result = {}
    for ln in raw.decode('gbk').strip().split('\n'):
        d = ln.split('~')
        if len(d) < 45: continue
        result[d[2]] = {
            'name': d[1], 'price': float(d[3]), 'chg': float(d[32]),
            'open': float(d[5]), 'high': float(d[33] or '0'),
            'low': float(d[34] or '0'), 'prev_close': float(d[4]),
            'vol_ratio': float(d[48] or '0'), 'turnover': float(d[38] or '0'),
            'amount': float(d[37] or '0'),
        }
    return result

def fetch_market_stats():
    """获取涨跌家数等"""
    try:
        d = json.loads(get(
            'https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001,0.399006&fields=f2,f3,f4,f5,f6,f7,f15,f16,f17,f18',
            5))
        return d.get('data',{}).get('diff',[])
    except:
        return []

def fetch_mx():
    try:
        from pipeline.autotrade import get_mx_positions
        return get_mx_positions()
    except:
        return {}, 0, 0

def read_json(path):
    try:
        if os.path.exists(path): return json.load(open(path))
    except: pass
    return None

def analyze_stock(name, code, px, chg, vol_ratio, turnover):
    """个股一句话简评"""
    if abs(chg) >= 9:
        return '涨停封板' if chg > 0 else '跌停'
    lines = []
    if chg > 0:
        if vol_ratio > 2:
            lines.append('放量上攻')
            if turnover > 10: lines.append('高换手博弈')
        elif chg > 5:
            lines.append('稳步上涨')
        else:
            lines.append('小幅走强')
    else:
        if vol_ratio > 2:
            lines.append('放量回调')
            if chg < -5: lines.append('短期承压')
        elif chg < -5:
            lines.append('持续走弱')
        else:
            lines.append('震荡调整')
    return '·'.join(lines) if lines else '横盘整理'

# ═══════════════════════════════════════════════
# 绘图
# ═══════════════════════════════════════════════

def draw():
    today = datetime.now().strftime('%Y年%m月%d日')
    date_str = datetime.now().strftime('%Y%m%d')
    
    codes = ['sh000001','sz399001','sz399006','sz002015','sz000600','sz002031']
    mkt = fetch_quotes(codes)
    mx_pos, mx_tv, mx_tp = fetch_mx()
    tier = read_json('data/state/tier_review.json')
    cb = read_json('data/state/circuit_breaker.json')
    disc = read_json('data/state/discipline_check.json')
    board = read_json('data/state/board_scan.json')
    
    fig = plt.figure(figsize=(9, 15), dpi=150)
    fig.patch.set_facecolor('#0d1117')
    
    # ═══ 标题栏 ═══
    fig.text(0.5, 0.97, f'📊 DAO收盘复盘', fontproperties=fp, fontsize=20,
             color='white', ha='center', fontweight='bold')
    fig.text(0.5, 0.945, today, fontproperties=fp, fontsize=12, color='#8b949e', ha='center')
    fig.text(0.95, 0.97, 'V3.3', fontproperties=fp, fontsize=9, color='#58a6ff', ha='right')
    
    # ═══ 1. 大盘一览 ═══
    y = 0.88
    fig.text(0.06, y+0.02, '━━ 大盘一览', fontproperties=fp, fontsize=13, color='#58a6ff', fontweight='bold')
    
    idx_cfg = [('000001','上证','#ff6b6b'),('399001','深证','#ffd93d'),('399006','创业板','#6bcb77')]
    for i, (code, name, color) in enumerate(idx_cfg):
        if code in mkt:
            d = mkt[code]
            sign = '+' if d['chg'] >= 0 else ''
            line = (f' {name:<5}  开{d["open"]:>8.0f}  收{d["price"]:>8.0f}  '
                   f'{sign}{d["chg"]:.2f}%   高{d["high"]:>8.0f}  低{d["low"]:>8.0f}')
            fig.text(0.07, y - i*0.035, line, fontproperties=fp, fontsize=10, color=color)
    
    # 市场统计
    stats = fetch_market_stats()
    stat_texts = []
    for item in stats:
        # f2=收盘, f3=涨跌幅%, f4=涨跌点, f5=成交量, f6=成交额
        pass  # indices data only
    
    # 从腾讯数据计算涨跌统计
    all_chg = [mkt[c]['chg'] for c in ['000001','399001','399006'] if c in mkt]
    avg_chg = sum(all_chg)/len(all_chg) if all_chg else 0
    mood = '🔥强势' if avg_chg > 1 else '✅温和' if avg_chg > 0 else '🔥弱势' if avg_chg < -1 else '⚡震荡'
    mood_color = '#6bcb77' if avg_chg > 0 else '#ff6b6b' if avg_chg < -0.5 else '#f0a040'
    
    # 持仓股涨跌
    pos_chgs = []
    for code in ['002015','000600','002031']:
        if code in mkt: pos_chgs.append(mkt[code]['chg'])
    pos_avg = sum(pos_chgs)/len(pos_chgs) if pos_chgs else 0
    pos_color = '#6bcb77' if pos_avg >= 0 else '#ff6b6b'
    
    stat_line = f'市场情绪: {mood}  持仓平均: {"+" if pos_avg>=0 else ""}{pos_avg:.1f}%'
    fig.text(0.07, y - 0.12, stat_line, fontproperties=fp, fontsize=10, color=mood_color)
    
    # ═══ 2. 成交额TOP ═══
    # 用腾讯数据取量比高的
    active = []
    for code, d in mkt.items():
        if code.startswith('0') or code.startswith('6'):
            if code in ['000001','399001','399006']: continue
            if d.get('vol_ratio', 0) > 1.5:
                active.append((d['name'], code, d['vol_ratio'], d['turnover'], d['chg']))
    active.sort(key=lambda x: -x[2])
    
    if active:
        fig.text(0.55, y, '成交活跃:', fontproperties=fp, fontsize=9, color='#8b949e')
        for i, (name, code, vr, to, chg) in enumerate(active[:3]):
            c = '#6bcb77' if chg >= 0 else '#ff6b6b'
            sign = '+' if chg >= 0 else ''
            fig.text(0.55, y - (i+1)*0.03, f' {name} 量{vr:.1f}x 换手{to:.1f}% {sign}{chg:.1f}%',
                     fontproperties=fp, fontsize=8, color=c)
    
    # ═══ 3. 实盘持仓 ═══
    y = 0.72
    fig.text(0.06, y+0.02, '━━ 实盘持仓', fontproperties=fp, fontsize=13, color='#f0883e', fontweight='bold')
    
    real_holdings = [
        ('002015','协鑫能科',19.90,200), ('000600','建投能源',9.80,200), ('002031','巨轮智能',6.75,700)
    ]
    
    total_value = total_pnl = 0
    rows = []
    for code, name, cost, shares in real_holdings:
        d = mkt.get(code)
        if not d: continue
        px = d['price']; chg = d['chg']
        pnl_pct = (px / cost - 1) * 100
        pnl_val = (px - cost) * shares
        total_value += px * shares; total_pnl += pnl_val
        sign = '+' if pnl_pct >= 0 else ''
        comment = analyze_stock(name, code, px, chg, d['vol_ratio'], d['turnover'])
        rows.append((name, shares, px, chg, pnl_pct, pnl_val, sign, comment))
    
    headers = ['名称','持仓','现价','日涨跌','盈亏','简评']
    cw = [0.12, 0.10, 0.14, 0.12, 0.15, 0.28]
    xs = [0.07]
    for w in cw[:-1]: xs.append(xs[-1] + w)
    
    for j, h in enumerate(headers):
        fig.text(xs[j], y, h, fontproperties=fp, fontsize=9, color='#8b949e')
    
    for i, (name, shares, px, chg, pnl_pct, pnl_val, sign, comment) in enumerate(rows):
        row_y = y - (i+1)*0.045
        c1 = '#6bcb77' if pnl_pct >= 0 else '#ff6b6b'
        c2 = '#6bcb77' if chg >= 0 else '#ff6b6b'
        sign2 = '+' if chg >= 0 else ''
        fig.text(xs[0], row_y, name, fontproperties=fp, fontsize=10, color=c1)
        fig.text(xs[1], row_y, f'{shares}股', fontproperties=fp, fontsize=10, color='#c9d1d9')
        fig.text(xs[2], row_y, f'¥{px:.2f}', fontproperties=fp, fontsize=10, color='#c9d1d9')
        fig.text(xs[3], row_y, f'{sign2}{chg:.1f}%', fontproperties=fp, fontsize=10, color=c2)
        fig.text(xs[4], row_y, f'{sign}¥{pnl_val:.0f}', fontproperties=fp, fontsize=10, color=c1)
        fig.text(xs[5], row_y, comment, fontproperties=fp, fontsize=9, color='#8b949e')
    
    sign_t = '+' if total_pnl >= 0 else ''
    tc = '#6bcb77' if total_pnl >= 0 else '#ff6b6b'
    ry = y - (len(rows)+1)*0.045
    fig.text(0.07, ry, f'合计 ¥{total_value:,.0f}  日盈亏{sign_t}¥{total_pnl:,.0f}',
             fontproperties=fp, fontsize=11, color=tc, fontweight='bold')
    
    # ═══ 4. MX模拟 ═══
    y = 0.55
    fig.text(0.06, y+0.02, '━━ MX模拟（波段 ¥20,000）', fontproperties=fp, fontsize=13, color='#a371f7', fontweight='bold')
    
    if mx_pos:
        for i, (code, p) in enumerate(list(mx_pos.items())[:6]):
            pnl_pct = p.get('profit_pct', 0)
            sign = '+' if pnl_pct >= 0 else ''
            c = '#6bcb77' if pnl_pct >= 0 else '#ff6b6b'
            qty = p.get('qty', 1) or 1; mv = p.get('value', 0)
            px = mv / max(qty, 1) if mv else 0
            fig.text(0.07, y - i*0.035, f'{p["name"]:<8} {qty}股 ¥{px:.2f} {sign}{pnl_pct:.1f}%',
                     fontproperties=fp, fontsize=9, color=c)
        c2 = '#6bcb77' if mx_tp >= 0 else '#ff6b6b'
        sign2 = '+' if mx_tp >= 0 else ''
        fig.text(0.07, y - min(len(mx_pos),6)*0.035, f'总市值 ¥{mx_tv:,.0f}  盈亏{sign2}¥{mx_tp:,.0f}',
                 fontproperties=fp, fontsize=10, color='#a371f7', fontweight='bold')
    else:
        fig.text(0.07, y, '  空仓', fontproperties=fp, fontsize=10, color='#8b949e')
    
    # ═══ 5. 打板信号 ═══
    y = 0.38
    fig.text(0.06, y+0.02, '━━ 今日信号', fontproperties=fp, fontsize=13, color='#d2a8ff', fontweight='bold')
    
    signal_lines = []
    
    # 梯队复盘
    if tier:
        tdata = tier.get('data', tier)
        if isinstance(tdata, str):
            signal_lines.extend(l.strip() for l in tdata.split('\\n') if l.strip() and ('涨停' in l or '跌停' in l or '晋级' in l or '梯队' in l))
    
    # board scanner
    if board and not signal_lines:
        cands = board.get('candidates', board.get('scanned', []))
        if cands and isinstance(cands[0], dict):
            sealed = [c for c in cands if c.get('zone')=='封板']
            rushing = [c for c in cands if c.get('zone')=='抢板']
            if sealed:
                signal_lines.append(f'封板{len(sealed)}只: {", ".join(c.get("name","?") for c in sealed[:3])}')
            if rushing:
                signal_lines.append(f'抢板{len(rushing)}只: {", ".join(c.get("name","?") for c in rushing[:3])}')
        elif cands:
            # old format: list of codes
            signal_lines.append(f'扫描候选: {len(cands)}只')
    
    # 仓位持仓表现也算信号
    winners = [r for r in rows if r[4] > 0]
    losers = [r for r in rows if r[4] <= 0]
    if winners or losers:
        signal_lines.append(f'持仓: {len(winners)}涨{len(losers)}跌  最强{max(rows,key=lambda x:x[3])[0] if rows else "—"}')
    
    if signal_lines:
        for i, line in enumerate(signal_lines[:5]):
            fig.text(0.07, y - i*0.035, line[:60], fontproperties=fp, fontsize=9, color='#c9d1d9')
    else:
        fig.text(0.07, y, '今日无特殊信号', fontproperties=fp, fontsize=9, color='#8b949e')
    
    # ═══ 6. 风险状态 ═══
    y = 0.18
    fig.text(0.06, y+0.02, '━━ 风险状态', fontproperties=fp, fontsize=13, color='#f85149', fontweight='bold')
    
    # 熔断
    cb_status = '✅ 正常'; cb_color = '#6bcb77'
    if cb:
        active = cb.get('active', cb.get('breaker_triggered', False))
        if active: cb_status = f'🚨 熔断: {cb.get("level","触发")}'; cb_color = '#ff6b6b'
        elif cb.get('breaches', []): cb_status = f'⚠️ 预警'; cb_color = '#f0a040'
    fig.text(0.07, y, f'熔断: {cb_status}', fontproperties=fp, fontsize=10, color=cb_color)
    
    # 纪律
    disc_status = '✅ 通过'; disc_color = '#6bcb77'
    if disc:
        score = disc.get('score', disc.get('total_score', 100))
        issues = disc.get('issues', [])
        if score < 80: disc_status = f'❌ {score}分'; disc_color = '#ff6b6b'
        elif issues: disc_status = f'⚠️ {score}分'; disc_color = '#f0a040'
    fig.text(0.07, y - 0.035, f'纪律: {disc_status}', fontproperties=fp, fontsize=10, color=disc_color)
    
    # 市场温度
    temp_str = '—'
    try:
        from market_thermometer_v2 import get_thermometer
        temp = get_thermometer()
        temp_str = f'{temp.get("level","—")}({temp.get("score",0)})'
    except: pass
    fig.text(0.55, y, f'温度: {temp_str}', fontproperties=fp, fontsize=10, color='#79c0ff')
    
    # 实盘胜率
    win_rate = f'{sum(1 for r in rows if r[4]>0)}/{len(rows)}' if rows else '—'
    fig.text(0.55, y - 0.035, f'持仓胜率: {win_rate}', fontproperties=fp, fontsize=10, color='#c9d1d9')
    
    # ═══ 底部 ═══
    fig.text(0.5, 0.04, '⚠️ 仅供参考，不构成投资建议 | 股市有风险，投资需谨慎',
             fontproperties=fp, fontsize=7, color='#484f58', ha='center')
    fig.text(0.95, 0.04, datetime.now().strftime("%H:%M"), fontproperties=fp, fontsize=7, color='#484f58', ha='right')
    fig.text(0.06, 0.04, 'DAOV3.3', fontproperties=fp, fontsize=7, color='#484f58')
    
    path = os.path.join(OUT, f'daily_report_{date_str}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='#0d1117', edgecolor='none')
    plt.close(fig)
    return path

if __name__ == '__main__':
    p = draw()
    print(f'✅ {p}')
