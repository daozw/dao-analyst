#!/usr/bin/env python3
"""
自我进化引擎 V1.0 — 每日自主优化策略参数
运行时机: 每日收盘后 (cron 15:45)
"""
import sys,fcntl, os, json, random
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

EVOLVE_FILE = 'data/evolve_state.json'

def load_state():
    if os.path.exists(EVOLVE_FILE):
        return json.load(open(EVOLVE_FILE))
    return {
        'generation': 0,
        'best_params': {
            'stop_loss': -0.06, 'tp1_protect': 0.02, 'tp2_half': 0.08,
            'tp3_clear': 0.15, 'position_risk': 0.02, 'max_positions': 3,
            'slippage': 0.002,
            'pattern_weight': {'弱转强':1.0, '531主升浪':1.0, '辨识度放量':1.0, '趋势回调':1.0}
        },
        'best_score': 0,
        'history': []
    }

def save_state(state):
    os.makedirs(os.path.dirname(EVOLVE_FILE), exist_ok=True)
    with open(EVOLVE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── 市场温度 ──
def get_market_temp():
    """返回温度评分: 正向=进攻市, 负向=防御市"""
    try:
        # 腾讯API获取市场涨跌
        import urllib.request, ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        req = urllib.request.Request('https://qt.gtimg.cn/q=sh000001')
        raw = urllib.request.urlopen(req, timeout=3).read().decode('gbk').split('~')
        chg_5d = float(raw[32]) if len(raw) > 32 else 0
        
        if chg_5d < -3: return 'deep_defense', -3
        if chg_5d < -1: return 'defense', -1
        if chg_5d < 1:  return 'neutral', 0
        return 'offense', 1
    except:
        return 'neutral', 0

# ── 快速评估 ──
def quick_eval(pool_codes, params, days=90):
    """用最近N天快速测试一组参数"""
    from backtest_engine import fetch_stock_data, calculate_signals, generate_buy_signals, BacktestEngine
    
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 覆盖全局参数 (save/restore避免污染)
    import backtest_engine as be
    _orig = {k: getattr(be, k, None) for k in ['STOP_LOSS','TAKE_PROFIT_1','TAKE_PROFIT_2',
                'TAKE_PROFIT_3','MAX_POSITIONS','SLIPPAGE']}
    try:
        be.STOP_LOSS = params['stop_loss']
        be.TAKE_PROFIT_1 = params['tp1_protect']
        be.TAKE_PROFIT_2 = params['tp2_half']
        be.TAKE_PROFIT_3 = params['tp3_clear']
        be.MAX_POSITIONS = params['max_positions']
        be.SLIPPAGE = params['slippage']
        
        engine = BacktestEngine('eval')
        result = engine.run(pool_codes[:15], start, end)
        
        if 'error' in result:
            return 0, result
        
        # 综合评分: 年化>0 + 夏普>0 + 回撤<10 + 交易>5
        score = 0
        if result['annual_return_pct'] > 0: score += result['annual_return_pct'] * 2
        if result['sharpe'] > 0: score += result['sharpe'] * 5
        if result['max_drawdown_pct'] > -10: score += 2
        if result['total_trades'] >= 3: score += 2
        score += result['annual_return_pct'] - abs(result['max_drawdown_pct']) * 0.3
        
        return score, result
    finally:
        for k, v in _orig.items():
            if v is not None:
                setattr(be, k, v)

# ── 变异 ──
def mutate(params, generation):
    """随机变异参数"""
    new = json.loads(json.dumps(params))  # deep copy
    
    # 变异数值参数  
    for key in ['stop_loss', 'tp1_protect', 'tp2_half', 'tp3_clear', 'position_risk', 'slippage']:
        if random.random() < 0.4:  # 40%概率变异
            values = SEARCH_SPACE[key]
            new[key] = random.choice(values)
    
    if random.random() < 0.3:
        new['max_positions'] = random.choice(SEARCH_SPACE['max_positions'])
    
    # 变异模式权重
    for pw in new.get('pattern_weight', {}):
        if random.random() < 0.3:
            new['pattern_weight'][pw] = random.choice(SEARCH_SPACE['pattern_weight'][pw])
    
    return new

# ── 主循环 ──
def main(dry_run=False):
    state = load_state()
    state['generation'] += 1
    gen = state['generation']
    
    # 加载股票池
    try:
        wl = json.load(open('data/watchlist.json'))
    except:
        wl = {'groups': {'core': {'stocks': [
            {'code':'600900','name':'长江电力'},{'code':'601398','name':'工商银行'},
            {'code':'600123','name':'兰花科创'},{'code':'601918','name':'新集能源'},
        ]}}}
    
    pool = [s['code'] for gn, g in wl['groups'].items() if gn != 'exclude' 
            for s in g['stocks'] if not s['code'].startswith(('300','688','8'))]
    pool = list(dict.fromkeys(pool))[:15]
    
    market_mode, market_score = get_market_temp()
    
    print(f"🧬 第{gen}代进化 | {datetime.now().strftime('%m/%d %H:%M')} | 市场:{market_mode}")
    print(f"   股票池: {len(pool)}只 | 最佳分数: {state['best_score']:.1f}")
    
    # 用当前最优参数跑一次基准
    base_score, base_result = quick_eval(pool, state['best_params'])
    print(f"   基准: 年化{base_result.get('annual_return_pct',0):+.1f}% 夏普{base_result.get('sharpe',0):.2f}")
    
    # 生成3个变异体并测试
    candidates = [state['best_params']]  # 包含基准
    for i in range(3):
        candidates.append(mutate(state['best_params'], gen))
    
    best_new_score = base_score
    best_new_params = state['best_params']
    best_new_result = base_result
    
    for i, params in enumerate(candidates[1:], 1):
        score, result = quick_eval(pool, params)
        label = '⭐' if score > best_new_score else '  '
        print(f"   {label}变异{i}: 年化{result.get('annual_return_pct',0):+.1f}% "
              f"夏普{result.get('sharpe',0):.2f} 回撤{result.get('max_drawdown_pct',0):.1f}% "
              f"得分{score:.1f}")
        if score > best_new_score:
            best_new_score = score
            best_new_params = params
            best_new_result = result
    
    # 更新状态
    improved = best_new_score > state['best_score']
    if improved:
        state['best_score'] = best_new_score
        state['best_params'] = best_new_params
    
    entry = {
        'gen': gen,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'market': market_mode,
        'best_score': best_new_score,
        'improved': improved,
        'params': {
            'stop_loss': best_new_params['stop_loss'],
            'tp1': best_new_params['tp1_protect'],
            'tp2': best_new_params['tp2_half'],
            'tp3': best_new_params['tp3_clear'],
            'risk': best_new_params['position_risk'],
            'positions': best_new_params['max_positions'],
            'slippage': best_new_params['slippage'],
        },
        'result': {
            'annual': best_new_result.get('annual_return_pct', 0),
            'sharpe': best_new_result.get('sharpe', 0),
            'drawdown': best_new_result.get('max_drawdown_pct', 0),
            'win_rate': best_new_result.get('win_rate_pct', 0),
            'trades': best_new_result.get('total_trades', 0),
            'pf': str(best_new_result.get('profit_factor', 0)),
        }
    }
    state['history'].append(entry)
    save_state(state)
    write_evolve_params(state)
    
    # 报告
    change = '✅ 改进' if improved else '— 不变'
    report_lines = [
        f"🧬 自我进化 #{gen} | {datetime.now().strftime('%m/%d %H:%M')}",
        f"市场: {market_mode} | {change}",
        f"",
        f"📊 当前最优参数:",
        f"   止损: {best_new_params['stop_loss']:.0%} | 止盈: {best_new_params['tp1_protect']:.0%}/{best_new_params['tp2_half']:.0%}/{best_new_params['tp3_clear']:.0%}",
        f"   仓位: {best_new_params['max_positions']}只×{best_new_params['position_risk']:.1%}风险 | 滑点{best_new_params['slippage']:.1%}",
        f"",
        f"📈 最近90日验证:",
        f"   年化{best_new_result.get('annual_return_pct',0):+.1f}% 夏普{best_new_result.get('sharpe',0):.2f}",
        f"   胜率{best_new_result.get('win_rate_pct',0):.0f}% 交易{best_new_result.get('total_trades',0)}笔 回撤{best_new_result.get('max_drawdown_pct',0):.1f}%",
        f"   累计{state['generation']}代 | 历史最优分{state['best_score']:.1f}",
    ]
    report = '\n'.join(report_lines)
    print(report)
    
    # 写入告警队列(由cron推送到微信)
    try:
        alerts = []
        if os.path.exists(ALERT_FILE):
            try: alerts = json.load(open(ALERT_FILE))
            except: pass
        alerts.append({'time': datetime.now().strftime('%H:%M'), 'action': 'EVOLVE',
                       'message': report, 'sent': False})
        with open(ALERT_FILE, 'w') as fh:
            json.dump(alerts, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass

if __name__ == "__main__":
    main()
