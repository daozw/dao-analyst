#!/usr/bin/env python3
"""策略A/B对比 V1.0 — 双参数并行,自动选优"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AB_FILE = os.path.expanduser('~/dao-analyst/data/state/strategy_ab.json')

# A/B参数组
PARAM_SETS = {
    'A': {'risk': 600, 'min_signal': 3, 'tp1': 8, 'tp2': 15, 'desc': '标准(600风险)'},
    'B': {'risk': 400, 'min_signal': 4, 'tp1': 5, 'tp2': 10, 'desc': '保守(400风险)'},
}

def load():
    if os.path.exists(AB_FILE):
        data = json.load(open(AB_FILE))
        if data.get('month') == datetime.now().strftime('%Y-%m'):
            return data
    return {
        'month': datetime.now().strftime('%Y-%m'),
        'A': {'trades': 0, 'wins': 0, 'pnl': 0, 'max_dd': 0},
        'B': {'trades': 0, 'wins': 0, 'pnl': 0, 'max_dd': 0},
        'active': 'A',  # 当前使用的策略
    }

def save(data):
    os.makedirs(os.path.dirname(AB_FILE), exist_ok=True)
    with open(AB_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_trade(strategy, pnl, won):
    data = load()
    data[strategy]['trades'] += 1
    if won: data[strategy]['wins'] += 1
    data[strategy]['pnl'] += pnl
    save(data)

def evaluate_and_switch():
    """月末评估,自动切换最优策略"""
    data = load()
    a = data['A']; b = data['B']
    
    if a['trades'] < 5 and b['trades'] < 5:
        return None
    
    a_score = (a['pnl'] / max(a['trades'],1)) * (a['wins']/max(a['trades'],1)) if a['trades']>0 else 0
    b_score = (b['pnl'] / max(b['trades'],1)) * (b['wins']/max(b['trades'],1)) if b['trades']>0 else 0
    
    best = 'A' if a_score >= b_score else 'B'
    changed = best != data['active']
    if changed:
        data['active'] = best
        save(data)
    
    return {
        'A': {'score': a_score, 'pnl': a['pnl'], 'wr': a['wins']/max(a['trades'],1)*100},
        'B': {'score': b_score, 'pnl': b['pnl'], 'wr': b['wins']/max(b['trades'],1)*100},
        'best': best, 'changed': changed,
        'desc': PARAM_SETS[best]['desc']
    }

def report():
    data = load()
    result = evaluate_and_switch()
    
    lines = [f'🔬 策略A/B {datetime.now().strftime("%Y-%m")}']
    lines.append('='*35)
    
    for s in ['A','B']:
        d = data[s]; t = d['trades']
        if t > 0:
            wr = d['wins']/t*100
            avg = d['pnl']/t
            lines.append(f'\n策略{s} ({PARAM_SETS[s]["desc"]}):')
            lines.append(f'  {t}笔 胜率{wr:.0f}% 均¥{avg:+.0f} 总¥{d["pnl"]:+.0f}')
    
    if result:
        lines.append(f'\n🏆 最优: 策略{result["best"]}')
        if result['changed']:
            lines.append(f'  ⚡ 已切换为{result["desc"]}')
    
    # 月考核
    active = data[data['active']]
    if active['trades'] >= 10:
        wr = active['wins']/active['trades']*100
        if wr < 40:
            lines.append(f'\n⚠️ 月胜率{wr:.0f}%<40% 建议收紧条件')
        elif wr > 60:
            lines.append(f'\n✅ 月胜率{wr:.0f}% 策略有效')
    
    return '\n'.join(lines)

if __name__ == '__main__':
    print(report())
