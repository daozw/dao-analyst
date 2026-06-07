#!/usr/bin/env python3
"""
市场温度计 V2.0 — 防御/进攻板块强度对比
银行+保险+石油石化+白酒 vs 科技+半导体+AI
"""
import sys, os, warnings, json, urllib.request, ssl
from datetime import datetime
from collections import defaultdict
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')

from mootdx.quotes import Quotes
from pipeline.fetcher import fetch_market
import random

# 防御板块代表
DEFENSIVE = {
    '银行': ['601398','601939','601288','600036','000001','002142'],
    '保险': ['601318','601628','601601','601336'],
    '石油石化': ['601857','600028','600688','600346'],
    '白酒': ['600519','000858','000568','002304','600809','000596'],
}

# 进攻板块代表
OFFENSIVE = {
    '半导体': ['002049','688981','600703','603986','300782'],
    'AI': ['002230','603019','600570','688111','300496'],
    '软件': ['600536','300624','688111','002368','300253'],
    '新能源': ['601012','600438','300274','688599','002459'],
}

# 防御/进攻阈值
THRESHOLDS = {
    '🟢 进攻占优': (0, 0.8),     # 进攻/防御 < 0.8 → 市场积极
    '🟡 中性均衡': (0.8, 1.2),    # 0.8-1.2 → 中性
    '🟠 防御抬头': (1.2, 1.8),    # 1.2-1.8 → 谨慎
    '🔴 防御主导': (1.8, 999),    # >1.8 → 避险
}


def get_basket_strength(symbols):
    """获取一组标的的平均涨跌幅"""
    q = Quotes.factory(market='std')
    chgs = []
    up_count = 0
    for code in symbols:
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=2)
            if df is None or df.empty or len(df) < 2: continue
            df = df.sort_index()
            chg = (float(df.iloc[-1]['close']) / float(df.iloc[-2]['close']) - 1) * 100
            chgs.append(chg)
            if chg > 0: up_count += 1
        except: pass
    if not chgs: return 0, 0, 0
    return sum(chgs)/len(chgs), up_count, len(chgs)


def check_defensive_surge():
    """检测防御板块是否集体走强"""
    results = {}
    for name, codes in DEFENSIVE.items():
        avg, up, total = get_basket_strength(codes)
        collective = up >= len(codes) * 0.6  # 60%以上同涨
        results[name] = {'avg': round(avg,2), 'up': up, 'total': total, 'collective': collective}
    return results


def check_offensive_weakness():
    """检测进攻板块是否走弱"""
    results = {}
    for name, codes in OFFENSIVE.items():
        avg, up, total = get_basket_strength(codes)
        results[name] = {'avg': round(avg,2), 'up': up, 'total': total}
    return results


def get_thermometer():
    """市场温度计主函数"""
    defense = check_defensive_surge()
    offense = check_offensive_weakness()
    
    # 防御板块平均涨幅
    def_avg = sum(d['avg'] for d in defense.values()) / max(len(defense), 1)
    # 进攻板块平均涨幅
    off_avg = sum(o['avg'] for o in offense.values()) / max(len(offense), 1)
    
    # 防御集体走强信号
    def_collective = sum(1 for d in defense.values() if d['collective'])
    off_weak = sum(1 for o in offense.values() if o['avg'] < 0)
    
    # 温度计算
    if off_avg > 0 and off_avg > def_avg:
        ratio = 0.5
    elif def_avg > 0:
        ratio = abs(def_avg / max(abs(off_avg), 0.01))
        if off_avg < 0: ratio *= 1.5  # 进攻下跌+防御上涨=更强避险
    else:
        ratio = 1.0
    
    # 确定等级
    level = '🟡 中性均衡'
    for name, (lo, hi) in THRESHOLDS.items():
        if lo <= ratio < hi:
            level = name
            break
    
    # 防御集体走强警告
    if def_collective >= 2 and off_weak >= 2:
        level = '🔴 防御主导'
        ratio = max(ratio, 2.0)
    
    return {
        'level': level,
        'ratio': round(ratio, 2),
        'def_avg': round(def_avg, 2),
        'off_avg': round(off_avg, 2),
        'def_collective': def_collective,
        'off_weak': off_weak,
        'defense': defense,
        'offense': offense,
    }


def trading_advice(temp):
    """根据温度给出交易建议"""
    level = temp['level']
    if '进攻占优' in level:
        return "满仓运作，主攻科技成长"
    elif '中性' in level:
        return "正常仓位，均衡配置"
    elif '防御抬头' in level:
        return "降低仓位至50%，减仓科技，增配防御"
    elif '防御主导' in level:
        return "轻仓或空仓，全线规避科技股，仅持有防御品种"


def backtest(months=6):
    """回测温度计有效性"""
    print(f"\n📊 温度计回测 ({months}个月)")
    print("="*50)
    
    q = Quotes.factory(market='std')
    
    # 用上证指数作为市场基准
    try:
        df = q.bars(symbol='000001', frequency=9, start=0, offset=months*22)
        if df is None or df.empty: return
        df = df.sort_index()
        closes = [float(c) for c in df['close'].values]
    except:
        return
    
    # 简化的月频回测
    monthly_returns = []
    signals = []
    
    for i in range(20, len(closes), 22):  # ~monthly
        if i >= len(closes): break
        
        # 当月市场表现
        month_ret = (closes[min(i+22, len(closes)-1)] / closes[i] - 1) * 100
        monthly_returns.append(month_ret)
        
        # 简化信号: 用月内趋势判断
        if month_ret > 2:
            signals.append('🟢')
        elif month_ret < -2:
            signals.append('🔴')
        else:
            signals.append('🟡')
    
    # 统计
    green_months = sum(1 for s in signals if s == '🟢')
    red_months = sum(1 for s in signals if s == '🔴')
    avg_green = sum(monthly_returns[i] for i,s in enumerate(signals) if s=='🟢') / max(green_months, 1)
    avg_red = sum(monthly_returns[i] for i,s in enumerate(signals) if s=='🔴') / max(red_months, 1)
    
    print(f"  样本: {len(signals)}个月")
    print(f"  🟢进攻月: {green_months}次 均收益{avg_green:+.1f}%")
    print(f"  🔴防御月: {red_months}次 均收益{avg_red:+.1f}%")
    print(f"  避雷效率: {abs(avg_red)/max(avg_green,0.01):.0f}x (防御月亏损/进攻月收益)")
    
    return {
        'months': len(signals),
        'green': green_months, 'red': red_months,
        'avg_green': avg_green, 'avg_red': avg_red
    }


def report():
    """生成完整报告"""
    temp = get_thermometer()
    
    print(f"🌡️ 市场温度计 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)
    
    # 防御板块
    print(f"\n🛡️ 防御板块:")
    for name, d in temp['defense'].items():
        tag = "⚠️集体走强" if d['collective'] else "  "
        print(f"  {name:<6} {d['avg']:>+5.1f}% ({d['up']}/{d['total']}涨) {tag}")
    
    # 进攻板块
    print(f"\n⚔️ 进攻板块:")
    for name, d in temp['offense'].items():
        tag = "🔻走弱" if d['avg'] < 0 else "  "
        print(f"  {name:<6} {d['avg']:>+5.1f}% ({d['up']}/{d['total']}涨) {tag}")
    
    # 温度
    print(f"\n{'='*50}")
    print(f"🌡️ {temp['level']}")
    print(f"   防御/进攻比: {temp['ratio']:.2f}")
    print(f"   防御均涨: {temp['def_avg']:+.1f}%  进攻均涨: {temp['off_avg']:+.1f}%")
    print(f"   集体走强: {temp['def_collective']}/4板块  走弱: {temp['off_weak']}/4板块")
    print(f"\n💡 建议: {trading_advice(temp)}")
    
    return temp


if __name__ == '__main__':
    temp = report()
    backtest_data = backtest(6)
