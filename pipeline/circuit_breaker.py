#!/usr/bin/env python3
"""熔断检查 V2.0 — 精简版：仅检测跌停暴增(千股跌停级)"""
import sys, os, json, urllib.request, ssl
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def count_limit_downs(codes):
    """扫描跌停数"""
    count = 0
    try:
        for i in range(0, len(codes), 30):
            batch = codes[i:i+30]
            q = ','.join(f'sh{c}' if c.startswith('6') else f'sz{c}' for c in batch)
            raw = urllib.request.urlopen(
                f'https://qt.gtimg.cn/q={q}', timeout=8
            ).read().decode('gbk')
            for ln in raw.strip().splitlines():
                d = ln.split('~')
                if len(d) >= 33:
                    try:
                        if float(d[32]) <= -9.9:
                            count += 1
                    except: pass
    except: pass
    return count

def get_market():
    """大盘涨跌"""
    try:
        raw = urllib.request.urlopen(
            'https://qt.gtimg.cn/q=sh000001,sz399001', timeout=5
        ).read().decode('gbk')
        chgs = []
        for ln in raw.strip().splitlines():
            d = ln.split('~')
            if len(d) >= 33: chgs.append(float(d[32]))
        return sum(chgs)/len(chgs) if chgs else 0
    except:
        return 0

def main():
    # 加载池子 (取前200只扫描)
    try:
        wl = json.load(open(os.path.join(BASE, 'data/watchlist.json')))
        pool = []
        for gn, g in wl['groups'].items():
            if gn == 'exclude': continue
            for s in g.get('stocks', []):
                c = s['code']
                if not c.startswith(('300','688','8')):
                    pool.append(c)
        pool = pool[:200]
    except:
        pool = ['600900']

    market_chg = get_market()
    ld_count = count_limit_downs(pool)
    
    # 只检查跌停暴增: >50只在池中跌停 = 千股跌停级别
    if ld_count > 50:
        print(f"🔴 熔断! 跌停{ld_count}只 | 大盘{market_chg:+.1f}%")
        import json as _json_breaker
        _json_breaker.dump({"triggered": True, "limit_down": ld_count, "time": __import__("datetime").datetime.now().isoformat()},
                          open("/tmp/circuit_breaker_state.json", "w"))
        print(f"   全市场恐慌 → 暂停买入")
        sys.exit(1)
    elif ld_count > 30:
        print(f"🟠 预警: 跌停{ld_count}只 | 大盘{market_chg:+.1f}%")
        sys.exit(0)
    else:
        print(f"🟢 正常 | 跌停{ld_count}只 | 大盘{market_chg:+.1f}%")
        sys.exit(0)

if __name__ == '__main__':
    main()
