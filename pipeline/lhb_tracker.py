#!/usr/bin/env python3
"""龙虎榜追踪 — 游资席位监控"""
import urllib.request, ssl, json, os, re
from datetime import datetime, timedelta

ssl._create_default_https_context = ssl._create_unverified_context

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "state", "lhb_state.json")

def fetch_lhb(date=None):
    """获取龙虎榜数据(同花顺免费接口)"""
    if date is None:
        date = datetime.now().strftime('%Y%m%d')
    
    results = []
    # 同花顺龙虎榜接口
    url = f'https://data.10jqka.com.cn/dataapi/limit_up/lhb_list?date={date}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://data.10jqka.com.cn/'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        raw = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        data = json.loads(raw)
        if data.get('status_code') == 0:
            for item in data.get('data', []):
                results.append({
                    "code": item.get('code', ''),
                    "name": item.get('name', ''),
                    "chg": item.get('change', 0),
                    "type": item.get('reason', ''),  # 上榜原因
                    "buy_amount": item.get('buy', 0),  # 买入金额(万)
                    "sell_amount": item.get('sell', 0),  # 卖出金额(万)
                    "net_amount": item.get('net', 0),  # 净买入(万)
                    "turnover": item.get('turnover_rate', 0),
                })
    except Exception as e:
        # Fallback: 东方财富接口
        try:
            url2 = f'https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?' \
                   f'lmt=0&klt=1&secid=1.000001&fields1=f1,f2,f3,f7'
            # 东财可能被Clash挡, 不勉强
            pass
        except:
            pass
    
    return results

def check_lhb_signal(code):
    """检查个股龙虎榜信号"""
    state = {}
    if os.path.exists(STATE_FILE):
        try: state = json.load(open(STATE_FILE))
        except: pass
    
    today = datetime.now().strftime('%Y%m%d')
    lhb_list = state.get('data', {}).get(today, [])
    
    for item in lhb_list:
        if item.get('code') == code:
            net = item.get('net_amount', 0)
            if net > 5000:
                # 净买入>5000万 → 强信号
                return 10, f"龙虎榜净买{net/10000:.1f}亿"
            elif net > 1000:
                return 5, f"龙虎榜净买{net/10000:.1f}亿"
            elif net < -3000:
                return -8, f"龙虎榜净卖{abs(net)/10000:.1f}亿→游资出货"
            else:
                return 2, "龙虎榜上榜"
    
    return 0, ""

def update_lhb_cache():
    """更新龙虎榜缓存(盘后跑)"""
    today = datetime.now().strftime('%Y%m%d')
    data = fetch_lhb(today)
    
    state = {}
    if os.path.exists(STATE_FILE):
        try: state = json.load(open(STATE_FILE))
        except: pass
    
    if 'data' not in state:
        state['data'] = {}
    
    state['data'][today] = data
    state['last_update'] = datetime.now().isoformat()
    
    # 保留最近5天
    dates = sorted(state['data'].keys(), reverse=True)
    for old_date in dates[5:]:
        del state['data'][old_date]
    
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    
    return data

if __name__ == '__main__':
    data = update_lhb_cache()
    print(f"📊 龙虎榜更新: {len(data)}只上榜")
    
    if data:
        # 显示净买入前5
        top = sorted(data, key=lambda x: x.get('net_amount', 0), reverse=True)[:5]
        print("\n💰 游资净买入TOP5:")
        for item in top:
            print(f"  {item['name']}({item['code']}) 净买{item['net_amount']/10000:.2f}亿 {item.get('type','')}")
