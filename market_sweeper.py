#!/usr/bin/env python3
"""
全市场扫雷器 V1.0 — 实时扫描主板异动, 补realtime_monitor关注池盲区
频率: 每10秒扫一次东方财富涨幅榜(>3%+量比>2), 接入signal_catcher
"""
import sys, os, json, time, urllib.request, ssl
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signal_catcher import capture as catch_signal

LOG_FILE = os.path.expanduser("~/dao-analyst/logs/market_sweeper.log")
SIGNAL_FILE = os.path.expanduser("~/dao-analyst/data/live/signals.json")

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def fetch_hot_stocks():
    """获取主板+中小板 涨幅>3%且量比>1.5的活跃股"""
    url = ('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=80&po=1&np=1&fltt=2&invt=2'
           '&fid=f3&fs=m:0+t:6,m:0+t:80&fields=f2,f3,f4,f8,f10,f12,f14,f15,f20,f21')
    try:
        raw = urllib.request.urlopen(url, timeout=10).read().decode()
        data = json.loads(raw)
        items = data.get('data', {}).get('diff', [])
        stocks = []
        for s in items:
            code = s.get('f12', '')
            name = s.get('f14', '')
            pct = s.get('f3', 0)
            vol_ratio = s.get('f10', 0)
            price = s.get('f2', 0)
            turnover = s.get('f8', 0)
            high = s.get('f15', 0)
            low = s.get('f16', 0)
            pre_close = s.get('f18', 0)
            
            if 'ST' in name or pct < 3 or vol_ratio < 1.5:
                continue
            if not (code.startswith('60') or code.startswith('00')):
                continue
            
            # 计算盘口简化指标
            pre = s.get('f18', pre_close)
            limit_up = round(pre * 1.10, 2) if pre > 0 else 0
            
            stocks.append({
                'code': code, 'name': name, 'price': price,
                'chg': pct, 'vol_ratio': vol_ratio, 'turnover': turnover,
                'limit_up': limit_up
            })
        return stocks
    except Exception as e:
        log(f"获取行情失败: {e}")
        return []

def build_px_snapshot(stock):
    """将东方财富数据转为signal_catcher需要的格式"""
    pct = stock['chg']
    price = stock['price']
    vol = stock.get('vol_ratio', 1)
    
    # 估算盘口: 涨幅越高买盘越强
    if pct >= 7:
        imb = min(80, 30 + pct * 3)
    elif pct >= 5:
        imb = 20 + (pct - 5) * 5
    else:
        imb = max(-20, (pct - 3) * 5)
    
    return {
        'price': price,
        'chg': pct,
        'vol_ratio': vol,
        'bid_total': int(price * vol * 100),
        'ask_total': int(price * 100),
        'imbalance_ratio': imb,
        'inside_ratio': 1.5 if vol > 2 else 1.2,
        'commission_ratio': pct * 0.5,
        'turnover': stock.get('turnover', 0),
        'pre_close': stock.get('limit_up', 0) / 1.10 if stock.get('limit_up', 0) > 0 else price / (1 + pct/100)
    }

def sweep(verbose=False):
    """扫描全市场,捕获信号"""
    stocks = fetch_hot_stocks()
    if verbose:
        log(f"扫描到{len(stocks)}只活跃股(>3%+量比>1.5)")
    
    found = 0
    for s in stocks:
        px = build_px_snapshot(s)
        sig = catch_signal(s['code'], s['name'], px, commit=True)
        if sig:
            found += 1
            if verbose:
                log(f"  {sig['type']} {s['name']}({s['code']}) +{s['chg']:.1f}%")
    
    if verbose and found == 0:
        log("无新信号")
    
    return found

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'once'
    
    if mode == 'once':
        sweep(verbose=True)
    elif mode == 'daemon':
        log("全市场扫雷器启动 (10秒间隔)")
        while True:
            try:
                sweep(verbose=False)
            except Exception as e:
                log(f"ERROR: {e}")
            time.sleep(10)
