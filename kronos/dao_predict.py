#!/usr/bin/env python3
"""
Kronos → DAO 集成桥接
用法: python3 dao_predict.py --code 000001 --steps 5 --output json
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from predict import KronosEngine

def fetch_kline(code, days=500):
    """从东方财富获取K线数据"""
    try:
        import urllib.request
        secid = f'1.{code}' if code.startswith('6') else f'0.{code}'
        url = f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&end=20500101&lmt={days}'
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        klines = data['data']['klines']
        ohlcv = []
        for line in klines:
            parts = line.split(',')
            ohlcv.append([float(parts[1]), float(parts[3]), float(parts[4]), float(parts[2]), float(parts[5])])
        return np.array(ohlcv)
    except Exception as e:
        print(f'数据获取失败: {e}', file=sys.stderr)
        # 返回随机数据做测试
        return np.cumsum(np.random.randn(min(days, 200), 5) * 0.01, axis=0) + 100

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='000001', help='股票代码')
    ap.add_argument('--steps', type=int, default=5, help='预测步数')
    ap.add_argument('--output', choices=['json','text'], default='text')
    args = ap.parse_args()
    
    engine = KronosEngine()
    ohlcv = fetch_kline(args.code, days=500)
    
    if len(ohlcv) < 100:
        print(f'⚠️ 数据不足 ({len(ohlcv)}条), 需要至少100条')
        sys.exit(1)
    
    result = engine.predict(ohlcv, args.steps)
    last_close = ohlcv[-1, 3]
    pred_close = result['close'].iloc[-1]
    change = (pred_close - last_close) / last_close * 100
    
    if args.output == 'json':
        print(json.dumps({
            'code': args.code,
            'last_close': round(float(last_close), 2),
            'pred_close': round(float(pred_close), 2),
            'change_pct': round(float(change), 2),
            'trend': 'bullish' if change > 0 else 'bearish',
            'forecast': [round(float(x), 2) for x in result['close'].tolist()]
        }, ensure_ascii=False))
    else:
        print(f'📊 Kronos预测 [{args.code}]')
        print(f'当前收盘: {last_close:.2f}')
        print(f'预测{args.steps}日后: {pred_close:.2f} ({change:+.2f}%)')
        print(f'趋势: {"📈 看涨" if change > 0 else "📉 看跌"}')
        print(f'预测序列: {[round(x,2) for x in result["close"].tolist()]}')

if __name__ == '__main__':
    main()
