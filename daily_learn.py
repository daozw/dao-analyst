#!/usr/bin/env python3
"""
每日交易分析 V1.0 — 从交易结果中学习并优化
追踪: 胜率·盈亏比·板块表现·时段质量·参数自适应
"""
import sys, os, json, urllib.request, ssl
from datetime import datetime, timezone, timedelta
from collections import defaultdict
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MX_KEY = 'mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8'
MX_API = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'
LEARNING_FILE = os.path.expanduser('~/dao-analyst/data/state/learning.json')

def load_learning():
    if os.path.exists(LEARNING_FILE):
        return json.load(open(LEARNING_FILE))
    return {
        'total_trades': 0, 'wins': 0, 'losses': 0,
        'total_pnl': 0, 'max_drawdown': 0,
        'by_strategy': {}, 'by_sector': {}, 'by_concept': {},
        'by_weekday': {}, 'by_hour': {},
        'best_trades': [], 'worst_trades': [],
        'parameter_suggestions': [],
        'lessons': [],
    }

def save_learning(data):
    os.makedirs(os.path.dirname(LEARNING_FILE), exist_ok=True)
    with open(LEARNING_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def analyze_trades():
    """分析最近交易,提取学习洞察"""
    try:
        req = urllib.request.Request(f'{MX_API}/orders',
            data=json.dumps({}).encode(), headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
        orders = json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return None
    
    all_orders = orders.get('data',{}).get('orders',[])
    
    # 重组为交易对(BUY→SELL)
    trades = []
    positions = {}
    
    for o in sorted(all_orders, key=lambda x: x['time']):
        tm = datetime.fromtimestamp(o['time'], tz=timezone(timedelta(hours=8)))
        code = o['secCode']
        otype = o.get('type', 0)
        price = o.get('tradePrice', o['price']) / (10 ** o.get('priceDec', 2))
        qty = o['count']
        
        if otype == 5:  # BUY
            if code not in positions:
                positions[code] = []
            positions[code].append({'time': tm, 'price': price, 'qty': qty})
        elif otype == 6:  # SELL
            if code in positions and positions[code]:
                buy = positions[code].pop(0)
                pnl = (price - buy['price']) * qty
                trades.append({
                    'code': code, 'name': o.get('secName',''),
                    'buy_time': buy['time'], 'sell_time': tm,
                    'buy_price': buy['price'], 'sell_price': price,
                    'qty': qty, 'pnl': pnl, 'pnl_pct': (price/buy['price']-1)*100,
                    'hold_days': (tm - buy['time']).days
                })
    
    return trades

def generate_insights(learning, trades):
    """生成学习洞察"""
    if not trades:
        return []
    
    insights = []
    
    # 1. 胜率分析
    wins = sum(1 for t in trades if t['pnl'] > 0)
    total = len(trades)
    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in trades if t['pnl']>0) / max(wins, 1)
    avg_loss = sum(t['pnl'] for t in trades if t['pnl']<0) / max(total-wins, 1)
    
    win_rate = wins/max(total,1)*100
    insights.append(f'📊 近期{total}笔交易,胜率{win_rate:.0f}%,盈亏¥{total_pnl:+,.0f}')
    
    if avg_win > 0 and avg_loss < 0:
        ratio = abs(avg_win/avg_loss)
        insights.append(f'   盈亏比{ratio:.1f}:1 (均赢¥{avg_win:.0f}/均亏¥{avg_loss:.0f})')
    
    # 2. 时段分析
    hour_pnl = defaultdict(lambda: {'pnl':0,'count':0})
    for t in trades:
        h = t['buy_time'].hour
        hour_pnl[h]['pnl'] += t['pnl']
        hour_pnl[h]['count'] += 1
    
    best_hour = max(hour_pnl.items(), key=lambda x: x[1]['pnl']/max(x[1]['count'],1)) if hour_pnl else None
    worst_hour = min(hour_pnl.items(), key=lambda x: x[1]['pnl']/max(x[1]['count'],1)) if hour_pnl else None
    
    if best_hour:
        insights.append(f'⏰ 最佳买入时段: {best_hour[0]}:00 (均¥{best_hour[1]["pnl"]/max(best_hour[1]["count"],1):+.0f})')
    if worst_hour and worst_hour[0] != best_hour[0]:
        insights.append(f'⏰ 最差买入时段: {worst_hour[0]}:00 (均¥{worst_hour[1]["pnl"]/max(worst_hour[1]["count"],1):+.0f})')
    
    # 3. 持仓天数分析
    days_pnl = defaultdict(lambda: {'pnl':0,'count':0})
    for t in trades:
        d = min(t['hold_days'], 10)
        days_pnl[d]['pnl'] += t['pnl']
        days_pnl[d]['count'] += 1
    
    # 4. 参数建议
    if win_rate < 40 and total >= 10:
        insights.append('⚠️ 胜率<40%: 建议收紧买入条件(提高信号门槛)')
    elif win_rate > 60 and total >= 10:
        insights.append('✅ 胜率>60%: 当前参数有效,保持')
    
    if total_pnl < 0 and total >= 10:
        insights.append('🔴 累计亏损: 检查是否有系统性错误')
    
    # 5. 学习记录
    learning['total_trades'] += total
    learning['wins'] += wins
    learning['losses'] += total - wins
    learning['total_pnl'] += total_pnl
    
    # Top/bottom trades
    sorted_trades = sorted(trades, key=lambda x: -x['pnl'])
    learning['best_trades'] = [
        {'code':t['code'],'name':t['name'],'pnl':t['pnl'],'pct':round(t['pnl_pct'],1)}
        for t in sorted_trades[:3]
    ]
    learning['worst_trades'] = [
        {'code':t['code'],'name':t['name'],'pnl':t['pnl'],'pct':round(t['pnl_pct'],1)}
        for t in sorted_trades[-3:]
    ]
    
    return insights

def run():
    """每日交易分析主流程"""
    print(f'🧠 每日交易分析 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*45)
    
    learning = load_learning()
    trades = analyze_trades()
    
    if not trades:
        print('  暂无完整交易对分析')
        return
    
    insights = generate_insights(learning, trades)
    
    for i in insights:
        print(f'  {i}')
    
    # 累积统计
    if learning['total_trades'] > 0:
        wr = learning['wins']/learning['total_trades']*100
        print(f'\n📈 历史累计: {learning["total_trades"]}笔 胜率{wr:.0f}% 盈亏¥{learning["total_pnl"]:+,.0f}')
    
    # 记录到A/B测试
    for t in trades:
        from strategy_ab import record_trade
        record_trade('A', t['pnl'], t['pnl'] > 0)
    
    save_learning(learning)
    print(f'\n✅ 学习数据已保存')

if __name__ == '__main__':
    run()
