#!/usr/bin/env python3
"""
自适应学习 V2.0 — 根据交易结果自动调整参数
调优: 信号门槛·仓位大小·止盈比例·止损松紧
"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEARNING_FILE = os.path.expanduser('~/dao-analyst/data/state/learning.json')
PARAMS_FILE = os.path.expanduser('~/dao-analyst/data/state/adaptive_params.json')

# 可调参数及其范围
ADAPTIVE_PARAMS = {
    'min_signal': {'current': 3, 'min': 2, 'max': 5, 'desc': '最低买入信号'},
    'risk_per_trade': {'current': 600, 'min': 300, 'max': 1000, 'desc': '单笔风险(¥)'},
    'take_profit_pct': {'current': 8, 'min': 5, 'max': 20, 'desc': '第一次止盈%'},
    'max_loss_pct': {'current': -5, 'min': -10, 'max': -3, 'desc': '硬止损%'},
    'max_daily_trades': {'current': 3, 'min': 1, 'max': 5, 'desc': '每日最大笔数'},
}

def load_params():
    if os.path.exists(PARAMS_FILE):
        return json.load(open(PARAMS_FILE))
    return ADAPTIVE_PARAMS

def save_params(params):
    os.makedirs(os.path.dirname(PARAMS_FILE), exist_ok=True)
    with open(PARAMS_FILE, 'w') as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

def analyze_and_adapt():
    """根据学习数据调整参数"""
    if not os.path.exists(LEARNING_FILE):
        return None
    
    learning = json.load(open(LEARNING_FILE))
    params = load_params()
    changes = []
    
    total = learning.get('total_trades', 0)
    wins = learning.get('wins', 0)
    
    if total < 10:
        return None  # 数据不足
    
    win_rate = wins / total * 100
    
    # 规则1: 胜率过低→收紧条件
    if win_rate < 35:
        new_sig = min(params['min_signal']['current'] + 1, params['min_signal']['max'])
        if new_sig != params['min_signal']['current']:
            changes.append(f'📈 胜率{win_rate:.0f}%偏低 → 信号门槛 {params["min_signal"]["current"]}→{new_sig}')
            params['min_signal']['current'] = new_sig
    
    # 规则2: 胜率高→可放宽
    elif win_rate > 60 and total >= 20:
        new_sig = max(params['min_signal']['current'] - 1, params['min_signal']['min'])
        if new_sig != params['min_signal']['current']:
            changes.append(f'📉 胜率{win_rate:.0f}%优秀 → 信号门槛 {params["min_signal"]["current"]}→{new_sig}')
            params['min_signal']['current'] = new_sig
    
    # 规则3: 连续亏损→缩仓
    total_pnl = learning.get('total_pnl', 0)
    if total_pnl < -2000 and total >= 10:
        new_risk = max(params['risk_per_trade']['current'] - 150, params['risk_per_trade']['min'])
        if new_risk != params['risk_per_trade']['current']:
            changes.append(f'🔴 累计亏损¥{total_pnl:+.0f} → 风险 {params["risk_per_trade"]["current"]}→{new_risk}')
            params['risk_per_trade']['current'] = new_risk
    
    # 规则4: 连续盈利→扩仓
    elif total_pnl > 5000 and total >= 10:
        new_risk = min(params['risk_per_trade']['current'] + 100, params['risk_per_trade']['max'])
        if new_risk != params['risk_per_trade']['current']:
            changes.append(f'🟢 累计盈利¥{total_pnl:+.0f} → 风险 {params["risk_per_trade"]["current"]}→{new_risk}')
            params['risk_per_trade']['current'] = new_risk
    
    if changes:
        save_params(params)
    
    return changes

def report():
    """生成调整报告"""
    params = load_params()
    changes = analyze_and_adapt()
    
    lines = [f'🧠 自适应学习 {datetime.now().strftime("%Y-%m-%d %H:%M")}']
    lines.append('='*40)
    
    if not os.path.exists(LEARNING_FILE):
        lines.append('  数据不足,等待更多交易')
        return '\n'.join(lines)
    
    learning = json.load(open(LEARNING_FILE))
    total = learning.get('total_trades', 0)
    wins = learning.get('wins', 0)
    
    lines.append(f'累计{total}笔 胜率{wins/max(total,1)*100:.0f}% 盈亏¥{learning.get("total_pnl",0):+,.0f}')
    
    lines.append(f'\n当前参数:')
    for key, p in params.items():
        lines.append(f'  {p["desc"]}: {p["current"]}')
    
    if changes:
        lines.append(f'\n本次调整:')
        for c in changes:
            lines.append(f'  {c}')
    else:
        lines.append(f'\n无需调整(数据不足或参数已最优)')
    
    return '\n'.join(lines)

if __name__ == '__main__':
    print(report())
