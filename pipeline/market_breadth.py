#!/usr/bin/env python3
"""市场广度 — 连板高度+炸板率+北向资金, 短线情绪即时温度计"""
import json, os, time, ssl, urllib.request, re
from datetime import datetime
from collections import defaultdict

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['no_proxy'] = '*'

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
HEADERS_EM = {'User-Agent': UA, 'Referer': 'https://quote.eastmoney.com/'}

def _em_fetch(url, timeout=10, retries=3):
    """东财API请求(带重试+间隔)"""
    for attempt in range(retries):
        try:
            time.sleep(0.3)  # 避免限流
            req = urllib.request.Request(url, headers=HEADERS_EM)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(0.5)
    return None

# ═══════════════════════════════════
# 1. 连板高度追踪
# ═══════════════════════════════════
def fetch_limit_up_boards():
    """获取涨停板连板高度: 用东财f8字段(连续涨停天数)"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f3,f8,f12,f14'
        data = _em_fetch(url)
        stocks = data.get('data', {}).get('diff', []) if data else []
        
        max_board = 0
        board_dist = defaultdict(int)
        for s in stocks:
            chg = s.get('f3', 0)
            if chg < 9.5:
                continue
            # f8 = 连续涨停天数
            days = s.get('f8', 0) or 0
            max_board = max(max_board, int(days))
            board_dist[int(days)] += 1
        
        return {'max_board': max_board, 'distribution': dict(board_dist),
                'total_limit_up': sum(board_dist.values())}
    except Exception as e:
        return {'error': str(e), 'max_board': 0}

def get_board_height_signal():
    """连板高度→信号"""
    boards = fetch_limit_up_boards()
    
    height = boards.get('max_board', 0)
    
    if height >= 7:
        return {'height': height, 'signal': 4, 'verdict': '🔥超高连板', 
                'advice': '打板黄金期,满仓进攻'}
    elif height >= 5:
        return {'height': height, 'signal': 3, 'verdict': '🟢高连板',
                'advice': '打板环境好,积极排板'}
    elif height >= 3:
        return {'height': height, 'signal': 1, 'verdict': '🟡中连板',
                'advice': '打板可行,控制仓位'}
    else:
        return {'height': height, 'signal': -2, 'verdict': '🔴无连板',
                'advice': '游资熄火,暂停打板'}

# ═══════════════════════════════════
# 2. 炸板率
# ═══════════════════════════════════
def fetch_broken_board_rate():
    """获取今日炸板率: 涨停后开板比例"""
    try:
        # 涨停板
        url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f3,f8,f12,f14'
        data = _em_fetch(url)
        stocks = data.get('data', {}).get('diff', []) if data else []
        
        sealed = 0  # 封住的
        broken = 0  # 炸板的(触及涨停但涨幅<9.8)
        for s in stocks:
            chg = s.get('f3', 0)
            high_chg = s.get('f8', 0) or 0
            if chg >= 9.8:
                sealed += 1
            elif chg >= 5 and s.get('f8', 0) and float(s.get('f8', 0)) > 9:
                # 到过涨停但回落
                broken += 1
        
        total = sealed + broken
        rate = broken / max(total, 1) * 100
        
        return {'total_limit_up': total, 'sealed': sealed, 'broken': broken,
                'broken_rate': round(rate, 1)}
    except Exception as e:
        return {'error': str(e)}

def get_broken_board_signal():
    """炸板率→信号"""
    data = fetch_broken_board_rate()
    if 'error' in data:
        return data
    
    rate = data['broken_rate']
    
    if rate < 15:
        return {**data, 'signal': 3, 'verdict': '✅封板率高', 
                'advice': '打板环境好'}
    elif rate < 30:
        return {**data, 'signal': 1, 'verdict': '🟡炸板适中',
                'advice': '打板可行,注意封单'}
    elif rate < 50:
        return {**data, 'signal': -2, 'verdict': '⚠️炸板偏多',
                'advice': '减少打板,严格筛选'}
    else:
        return {**data, 'signal': -4, 'verdict': '💥大面积炸板',
                'advice': '暂停打板,观望'}

# ═══════════════════════════════════
# 3. 北向资金
# ═══════════════════════════════════
def fetch_northbound_flow():
    """获取北向资金净流入"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/kamt.kline/get?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54&klt=1&lmt=5'
        data = _em_fetch(url)
        if not data or not data.get('data'):
            return {'error': '北向数据暂不可用', 'net_flow': 0}
        
        klines = data.get('data', {}).get('klines', [])
        if klines:
            latest = klines[-1].split(',')
            net_flow = float(latest[2]) if len(latest) > 2 else 0
            return {'net_flow': round(net_flow, 1), 'time': latest[0]}
        return {'error': '无北向数据', 'net_flow': 0}
    except Exception as e:
        return {'error': str(e), 'net_flow': 0}

def get_northbound_signal():
    """北向资金→信号"""
    data = fetch_northbound_flow()
    if not data or 'error' in data:
        return {'error': '北向不可用', 'signal': 0, 'net_flow': 0, 'verdict': '🟡无数据', 'advice': '北向数据暂不可用'}
    
    flow = data['net_flow']
    
    if flow > 50:
        return {**data, 'signal': 4, 'verdict': '🔥外资爆买',
                'advice': f'北向净买{flow:.0f}亿,全面看多'}
    elif flow > 20:
        return {**data, 'signal': 2, 'verdict': '🟢外资流入',
                'advice': f'北向净买{flow:.0f}亿,偏多'}
    elif flow > -20:
        return {**data, 'signal': 0, 'verdict': '🟡外资观望',
                'advice': f'北向{flow:.0f}亿,中性'}
    elif flow > -50:
        return {**data, 'signal': -2, 'verdict': '🔴外资流出',
                'advice': f'北向净卖{abs(flow):.0f}亿,偏空'}
    else:
        return {**data, 'signal': -4, 'verdict': '💥外资出逃',
                'advice': f'北向净卖{abs(flow):.0f}亿,全面看空'}

# ═══════════════════════════════════
# 综合市场广度
# ═══════════════════════════════════
def market_breadth():
    """综合市场广度报告"""
    results = {
        'time': datetime.now().isoformat(),
        'board_height': get_board_height_signal(),
        'broken_board': get_broken_board_signal(),
        'northbound': get_northbound_signal(),
    }
    
    # 综合评分
    score = 0
    for key in ['board_height', 'broken_board', 'northbound']:
        s = results[key].get('signal', 0)
        score += s
    
    results['total_score'] = score
    results['verdict'] = '🟢进攻' if score >= 5 else ('🟡中性' if score >= 0 else '🔴防御')
    
    return results

if __name__ == '__main__':
    print("📊 市场广度扫描\n")
    
    height = get_board_height_signal()
    print(f"🔺 连板高度: {height.get('verdict','?')} (最高{height.get('height','?')}板) → {height.get('advice','数据暂不可用')}")
    
    broken = get_broken_board_signal()
    if broken.get('broken_rate') is not None:
        print(f"💔 炸板率: {broken.get('verdict','?')} ({broken.get('broken',0)}/{broken.get('total_limit_up',0)}={broken.get('broken_rate',0)}%) → {broken.get('advice','')}")
    else:
        print(f"💔 炸板率: 数据暂不可用(非交易时段)")
    
    nb = get_northbound_signal()
    if nb.get('net_flow') is not None:
        print(f"🌏 北向: {nb.get('verdict','?')} → {nb.get('advice','')}")
    else:
        print(f"🌏 北向: 数据暂不可用")
    
    print()
    r = market_breadth()
    print(f"📊 市场广度总分: {r.get('total_score',0):+d} → {r.get('verdict','?')}")
