#!/usr/bin/env python3
"""高级指标 V1.0 — 夏普+回撤+相关性+幻觉检测"""
import sys, os, json, warnings
import numpy as np
from datetime import datetime
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def calc_sharpe(returns, risk_free=0.02):
    """夏普比率"""
    if len(returns) < 5: return 0
    excess = np.mean(returns) - risk_free/252
    std = np.std(returns)
    return excess / std * np.sqrt(252) if std > 0 else 0

def calc_max_drawdown(equity_curve):
    """最大回撤"""
    if len(equity_curve) < 2: return 0
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    return abs(min(drawdown))

def calc_correlation(positions, cm_file='data/concept_map.json'):
    """持仓板块相关性"""
    if len(positions) < 2: return 0, {}
    cm = json.load(open(cm_file)) if os.path.exists(cm_file) else {}
    
    # Count sector overlap
    sector_count = {}
    for code in positions:
        for c in cm.get(code, []):
            sector_count[c] = sector_count.get(c, 0) + 1
    
    max_overlap = max(sector_count.values()) if sector_count else 0
    risk_level = '🟢' if max_overlap <= 2 else '🟡' if max_overlap <= 3 else '🔴'
    
    return max_overlap, sector_count, risk_level

def check_data_hallucination(source1, source2, tolerance=0.05):
    """跨源数据校验(幻觉检测)"""
    if not source1 or not source2: return False, '数据源缺失'
    diff = abs(source1 - source2) / max(abs(source2), 0.01)
    if diff > tolerance:
        return True, f'偏差{diff:.0%}({source1:.2f} vs {source2:.2f})'
    return False, f'一致({diff:.1%})'

def generate_report(positions=None):
    """生成高级指标报告"""
    lines = [f'📊 高级风控指标 {datetime.now().strftime("%H:%M")}']
    lines.append('='*40)
    
    # 1. 持仓相关性
    if positions:
        max_ov, sec_count, risk = calc_correlation(list(positions.keys()))
        lines.append(f'\n🔗 持仓相关性: {risk}')
        lines.append(f'   最大板块集中: {max_ov}只')
        if max_ov >= 3:
            overs = [f'{k}({v}只)' for k,v in sec_count.items() if v >= 3]
            lines.append(f'   ⚠️ 过度集中: {",".join(overs)}')
    
    # 2. 幻觉检测(腾讯vs新浪)
    try:
        import urllib.request, ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # 腾讯价格
        tx = urllib.request.urlopen(urllib.request.Request('https://qt.gtimg.cn/q=sh600900'), timeout=5).read().decode('gbk')
        tx_price = float(tx.split('~')[3]) if '~' in tx else 0
        
        # 新浪价格
        sn = urllib.request.urlopen(urllib.request.Request('https://hq.sinajs.cn/list=sh600900', 
            headers={'Referer':'https://finance.sina.com.cn'}), timeout=5).read().decode('gbk')
        sn_price = float(sn.split(',')[3]) if ',' in sn else 0
        
        halluc, msg = check_data_hallucination(tx_price, sn_price)
        lines.append(f'\n🤖 数据校验: {"⚠️ 异常" if halluc else "✅ 正常"} ({msg})')
    except:
        lines.append(f'\n🤖 数据校验: ⚠️ 不可用')
    
    return '\n'.join(lines)

if __name__ == '__main__':
    from pipeline.autotrade import get_mx_positions
    pos, tv, tp = get_mx_positions()
    print(generate_report(pos))
