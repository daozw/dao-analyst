#!/usr/bin/env python3
"""东财Level-2逐笔数据 — 拖拉机单+主力吸筹+主动买卖+量价背离"""
import json, time, os, ssl, urllib.request
from collections import deque
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['no_proxy'] = '*'  # 绕过Clash代理

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
HEADERS = {'User-Agent': UA, 'Referer': 'https://quote.eastmoney.com/'}

CACHE = {}
CACHE_TTL = 5  # 5秒缓存

def _fetch_json(url, timeout=5):
    req = urllib.request.Request(url, headers=HEADERS)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))

def fetch_tick_details(code):
    """获取逐笔成交明细"""
    sc = f'1.{code}' if code.startswith('6') else f'0.{code}'
    url = f'https://push2.eastmoney.com/api/qt/stock/details/get?secid={sc}&fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55'
    
    try:
        data = _fetch_json(url, timeout=8)
        details = data.get('data', {}).get('details', [])
        ticks = []
        for d in details:
            parts = d.split(',')
            if len(parts) >= 5:
                ticks.append({
                    'time': parts[0], 'price': float(parts[1]),
                    'volume': int(parts[2]), 'direction': 'buy' if parts[4] == '1' else 'sell'
                })
        return ticks
    except:
        return []

def fetch_minute_trends(code):
    """获取分时线(每分钟OHLCV)"""
    sc = f'1.{code}' if code.startswith('6') else f'0.{code}'
    url = f'https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid={sc}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ndays=1'
    
    try:
        data = _fetch_json(url, timeout=8)
        trends = data.get('data', {}).get('trends', [])
        minutes = []
        for t in trends:
            parts = t.split(',')
            if len(parts) >= 8:
                minutes.append({
                    'time': parts[0], 'price': float(parts[1]),
                    'avg_price': float(parts[2]) if parts[2] else 0,
                    'volume': int(parts[6]) if len(parts) > 6 and parts[6] else 0,
                    'amount': float(parts[7]) if len(parts) > 7 and parts[7] else 0,
                })
        return minutes
    except:
        return []

# ────────────────────────
# 拖拉机单检测(真实数据)
# ────────────────────────
def detect_tractor(ticks, window_sec=5, min_same=5):
    """检测连续同向小单(拆单伪装)"""
    if len(ticks) < min_same:
        return None
    
    # 按时间窗口分组
    patterns = []
    buy_streak = 0
    sell_streak = 0
    buy_vol = 0
    sell_vol = 0
    
    for t in ticks:
        if t['direction'] == 'buy':
            buy_streak += 1
            sell_streak = 0
            buy_vol += t['volume']
        else:
            sell_streak += 1
            buy_streak = 0
            sell_vol += t['volume']
        
        if buy_streak >= min_same:
            patterns.append({'type': '拖拉机买入', 'count': buy_streak, 'vol': buy_vol})
        elif sell_streak >= min_same:
            patterns.append({'type': '拖拉机卖出', 'count': sell_streak, 'vol': sell_vol})
    
    if patterns:
        latest = patterns[-1]
        if latest['type'] == '拖拉机买入':
            return {'signal': 4, 'msg': f"主力拆单买入×{latest['count']}笔 {latest['vol']}手"}
        else:
            return {'signal': -4, 'msg': f"主力拆单卖出×{latest['count']}笔 {latest['vol']}手"}
    return None

# ────────────────────────
# 主动买卖比
# ────────────────────────
def active_buy_sell_ratio(ticks):
    """主动买卖比: 外盘/内盘"""
    buy_vol = sum(t['volume'] for t in ticks if t['direction'] == 'buy')
    sell_vol = sum(t['volume'] for t in ticks if t['direction'] == 'sell')
    total = buy_vol + sell_vol
    
    if total == 0:
        return {'ratio': 1.0, 'signal': 0, 'msg': '无逐笔数据'}
    
    ratio = buy_vol / max(sell_vol, 1)
    
    if ratio > 2:
        return {'ratio': round(ratio, 1), 'signal': 3, 'msg': f'主动买压极强({ratio:.1f}:1)'}
    elif ratio > 1.5:
        return {'ratio': round(ratio, 1), 'signal': 2, 'msg': f'主动买盘占优({ratio:.1f}:1)'}
    elif ratio < 0.5:
        return {'ratio': round(ratio, 1), 'signal': -3, 'msg': f'主动卖压极强(1:{1/ratio:.1f})'}
    elif ratio < 0.67:
        return {'ratio': round(ratio, 1), 'signal': -2, 'msg': f'主动卖盘占优(1:{1/ratio:.1f})'}
    else:
        return {'ratio': round(ratio, 1), 'signal': 0, 'msg': f'买卖均衡({ratio:.1f}:1)'}

# ────────────────────────
# 量价背离检测
# ────────────────────────
def volume_price_divergence(minutes):
    """量价背离: 价涨量缩→见顶, 价跌量缩→见底"""
    if len(minutes) < 10:
        return None
    
    recent = minutes[-10:]  # 最近10分钟
    
    prices = [m['price'] for m in recent]
    volumes = [m['volume'] for m in recent]
    
    # 简单趋势判断
    price_up = prices[-1] > prices[0]
    vol_up = sum(volumes[-3:]) > sum(volumes[:3])
    
    if price_up and not vol_up:
        return {'signal': -2, 'msg': '⚠️价涨量缩→上涨乏力,防回落'}
    elif not price_up and vol_up:
        return {'signal': 1, 'msg': '🔍价跌量增→多空分歧,可观察'}
    elif not price_up and not vol_up:
        return {'signal': 2, 'msg': '✅价跌量缩→抛压衰竭,可能见底'}
    
    return None

# ────────────────────────
# 大单检测(分时线)
# ────────────────────────
def detect_big_order_minute(minutes, threshold=500):
    """检测大单分钟(成交额>50万/分钟)"""
    if not minutes:
        return None
    
    big_minutes = [m for m in minutes if m['amount'] > threshold * 10000]
    
    if not big_minutes:
        return None
    
    # 计算大单分钟的涨跌方向
    up = sum(1 for m in big_minutes if m['price'] > m['avg_price'])
    down = len(big_minutes) - up
    
    if up > down * 2:
        return {'signal': 3, 'msg': f'主力扫货×{len(big_minutes)}分钟(大单买入为主)', 'count': len(big_minutes)}
    elif down > up * 2:
        return {'signal': -3, 'msg': f'主力出货×{len(big_minutes)}分钟(大单卖出为主)', 'count': len(big_minutes)}
    
    return None

# ────────────────────────
# 综合逐笔分析
# ────────────────────────
def analyze_ticks(code):
    """综合逐笔分析 → 信号(-10~+10)"""
    # 腾讯数据(快速,5档盘口)
    try:
        from pipeline.fetcher import fetch
        px = fetch(code)
    except:
        px = {}
    
    score = 0
    signals = []
    
    # 逐笔数据(东财,每笔成交)
    ticks = fetch_tick_details(code)
    if ticks:
        # 拖拉机单
        tractor = detect_tractor(ticks)
        if tractor:
            score += tractor['signal']
            signals.append({'type': '拖拉机单', 'msg': tractor['msg'], 'tag': tractor['signal']})
        
        # 主动买卖比
        abs_ratio = active_buy_sell_ratio(ticks)
        score += abs_ratio['signal']
        if abs_ratio['signal'] != 0:
            signals.append({'type': '主动买卖', 'msg': abs_ratio['msg'], 'tag': abs_ratio['signal']})
    
    # 分时数据(量价背离+大单)
    minutes = fetch_minute_trends(code)
    if minutes:
        vp = volume_price_divergence(minutes)
        if vp:
            score += vp['signal']
            signals.append({'type': '量价关系', 'msg': vp['msg'], 'tag': vp['signal']})
        
        big = detect_big_order_minute(minutes)
        if big:
            score += big['signal']
            signals.append({'type': '大单分钟', 'msg': big['msg'], 'tag': big['signal']})
    
    # 盘口数据(腾讯,5档)
    if px:
        imb = px.get('imbalance_ratio', 0)
        if imb < -0.3:
            score -= 2; signals.append({'type': '盘口失衡', 'msg': f'卖盘压倒(失衡{imb:.0%})-2', 'tag': -2})
        elif imb > 0.2:
            score += 1; signals.append({'type': '盘口失衡', 'msg': f'买盘占优(失衡{imb:.0%})+1', 'tag': 1})
        
        inside = px.get('inside_ratio', 0)
        if inside < 0.5:
            score -= 1; signals.append({'type': '内外比', 'msg': f'内盘主导({inside:.1f})-1', 'tag': -1})
        elif inside > 1.5:
            score += 1; signals.append({'type': '内外比', 'msg': f'外盘主导({inside:.1f})+1', 'tag': 1})
    
    return {
        'score': max(-10, min(10, score)),
        'signals': signals,
        'verdict': '🟢主力做多' if score >= 3 else ('🟡中性' if score >= 0 else '🔴主力出逃'),
        'time': datetime.now().isoformat()
    }

if __name__ == '__main__':
    for code in ['600519', '000001']:
        r = analyze_ticks(code)
        print(f"\n📊 {code}: {r['verdict']} (信号{r['score']:+d})")
        for s in r['signals']:
            print(f"  {s['type']}: {s['msg']}")
