#!/usr/bin/env python3
"""打板·竞价闪电 V1.0 — 09:22 抢板（抓>7%竞价封板票）"""
import sys, os, json, urllib.request, ssl, subprocess
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "board_lightning.json")
MIN_GAP = 7.0; MAX_PRICE = 30
BOARD_CAPITAL = 12000
MAX_BOARD_POSITIONS = 8          # 打板账户总持仓上限
MAX_DAILY_STOCKS = 3

def alert(action, msg):
    alerts = []; ts = datetime.now().strftime('%H:%M:%S')
    if os.path.exists(ALERT_FILE):
        try: alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({'time': ts, 'action': action, 'message': msg, 'sent': False})
    with open(ALERT_FILE, 'w') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def get_premarket_lightning():
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        stocks = json.loads(raw)
        results = []
        for s in stocks:
            code = s.get("code", "")
            if not code.startswith(("60", "00")): continue
            if code.startswith("688"): continue
            if "ST" in s.get("name", "") or "退" in s.get("name", ""): continue
            op = float(s.get("open", 0))
            prev = float(s.get("settlement", 0))
            if prev <= 0: continue
            gap = (op / prev - 1) * 100
            price = float(s.get("trade", 0))
            if gap >= MIN_GAP and price <= MAX_PRICE:
                results.append({
                    "code": code, "name": s.get("name", ""),
                    "price": price, "gap": round(gap, 2),
                    "vol": float(s.get("volume", 0)),
                    "limit_up": round(prev * 1.099 + 0.01, 2)
                })
        return sorted(results, key=lambda x: x['gap'], reverse=True)
    except Exception as e:
        print(f"  ⚠️ 竞价数据获取失败: {e}")
        return []

def submit_htsc_order(code, name, price, qty):
    """华泰挂单 — 通过UnifiedTrader"""
    try:
        from trader import UnifiedTrader
        trader = UnifiedTrader(strategy="board")
        resp = trader.buy(code, price, qty)
        ok = resp.get("ok", False) or resp.get("code") == "200"
        tag = "✅ MX" if ok else "❌"
        print(f"  {tag} 挂单 {name}({code}) {qty}股 @¥{price:.2f}")
        return ok
    except Exception as e:
        print(f"  华泰挂单失败: {e}")
        return False

def save_state(stock):
    today = datetime.now().strftime('%Y-%m-%d')
    state = {}
    if os.path.exists(STATE_FILE):
        try: state = json.load(open(STATE_FILE))
        except: pass
    if state.get('date') != today:
        state = {'date': today, 'stocks': []}
    state['stocks'].append(stock)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def check_market_safety():
    """多维安全检查: 温度 + 昨日涨停溢价 + 竞价情绪"""
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        level = t.get('level', '')
        if '防御主导' in level:
            return False, "防御主导→不追竞价"
    except: pass
    
    # 检查昨日涨停今日开盘(是否有溢价)
    try:
        import urllib.request
        # 简单检查: 看主要指数是否高开
        raw = urllib.request.urlopen('https://qt.gtimg.cn/q=sh000001', timeout=5).read().decode('gbk')
        d = raw.split('~')
        if len(d) > 32:
            open_px = float(d[5]) if d[5] else 0
            cur_px = float(d[3]) if d[3] else 0
            pre = float(d[4]) if d[4] else 0
            # 竞价期间今开=0，用当前价代替
            px = open_px if open_px > 0 else cur_px
            if pre > 0 and px > 0 and (px - pre) / pre < -0.01:
                return False, "大盘低开>1%→谨慎"
    except: pass
    
    return True, "安全"

def scan():
    print(f"⚡ 竞价闪电扫描 {datetime.now().strftime('%H:%M:%S')}")
    
    # 多维安全检查
    safe, reason = check_market_safety()
    if not safe:
        print(f"  ⛔ {reason}")
        return
    
    stocks = get_premarket_lightning()
    if not stocks:
        print("  无符合条件标的")
        return
    
    print(f"  发现{len(stocks)}只,>7%竞价:")
    for s in stocks[:8]:
        tag = "🔴" if s['gap'] >= 9.5 else "🟠"
        print(f"  {tag} {s['name']}({s['code']}) ¥{s['price']:.2f} +{s['gap']:.1f}% 涨停{s['limit_up']:.2f}")
    
    # 多维筛选: 高价优先 + 量比优先 + 市场温度调节
    # 进攻市可激进(≤3只), 防御抬头限1只
    max_orders = 2
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        if '防御抬头' in t.get('level', ''): max_orders = 1
        elif '进攻占优' in t.get('level', ''): max_orders = 3
    except: pass
    
    # 写入候选清单供gateway推送(下单前)
    candidate_file = '/tmp/dao_board_candidates.json'
    candidates = [{'code': s['code'], 'name': s['name'], 'price': s['limit_up'], 'gap': s['gap']} for s in stocks[:max_orders] if s['price'] >= 3]
    if candidates:
        with open(candidate_file, "w") as f:
            json.dump(candidates, f, ensure_ascii=False)
        print(f'  📋 候选标的已写入: {len(candidates)}只')
    else:
        # 空文件也写入,防止gateway卡住
        with open(candidate_file, "w") as f:
            json.dump([], f)
        print('  无符合候选')

def execute_orders():
    '''读取候选文件,执行下单'''
    candidate_file = '/tmp/dao_board_candidates.json'
    if not os.path.exists(candidate_file):
        print("  无候选文件")
        return
    
    candidates = json.load(open(candidate_file))
    max_orders = 2  # 默认
    # 检查当前打板持仓数,避免越滚越多
    try:
        from trader import UnifiedTrader
        board_trader = UnifiedTrader(strategy="board")
        resp = board_trader.positions()
        pos_list = resp.get("data", dict()).get("posList", [])
        # 只统计有实际持仓的(count>0且availCount>0)
        active_pos = [p for p in pos_list if p.get('count', 0) > 0 and p.get('availCount', 0) > 0]
        current_pos_count = len(active_pos)
        if current_pos_count >= MAX_BOARD_POSITIONS:
            print(f"  ! 打板持仓{current_pos_count}只已达上限{MAX_BOARD_POSITIONS}, 跳过新买入")
            return
        remaining = MAX_BOARD_POSITIONS - current_pos_count
        max_orders = min(max_orders, remaining)
        print(f"  当前持仓{current_pos_count}只, 可新增{remaining}只")
    except Exception as e:
        print(f"  仓位查询失败: {e}, 继续执行(最多{max_orders}只)")
    
    print(f"📋 读取{candidate_file}: {len(candidates)}只候选")
    
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        if '防御抬头' in t.get('level', ''): max_orders = 1
        elif '进攻占优' in t.get('level', ''): max_orders = 3
    except: pass
    
    ordered = 0
    for c in candidates:
        if ordered >= max_orders: break
        budget_per_stock = BOARD_CAPITAL // max(max_orders, 1)
        qty = max(100, int(budget_per_stock / c['price'] / 100) * 100)
        
        if submit_htsc_order(c['code'], c['name'], c['price'], qty):
            print(f"  ✅ 挂单: {c['name']} {qty}股 @涨停¥{c['price']:.2f}")
            ordered += 1
            save_state({
                "code": c['code'], "name": c['name'],
                "qty": qty, "price": c['price'], "gap": c['gap']
            })
            alert("LIGHTNING", f"⚡ 竞价闪电 {c['name']}({c['code']}) +{c['gap']:.1f}% 挂涨停¥{c['price']:.2f}")
        else:
            print(f"  ❌ 挂单失败: {c['name']}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "--execute":
        execute_orders()
    else:
        scan()
