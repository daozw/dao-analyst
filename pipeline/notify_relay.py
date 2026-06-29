#!/usr/bin/env python3
"""
通知中继 v4: 只推有意义的变化 + 指纹去重
- 智能清理: 交易记录>24h清理, 信号不过期
- 信号去重+增量推送
- 整合温度计+持仓
- 输出 relay_fingerprint.txt 供 relay shell 去重
"""
import json, os, time, hashlib
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ALERT_FILE = BASE / "data" / "live" / "trade_alerts.json"
RELAY_FILE = BASE / "data" / "live" / "relay_pending.txt"
FP_FILE = BASE / "data" / "live" / "relay_fingerprint.txt"
STATE_FILE = BASE / "data" / "live" / "relay_state.json"

CUTOFF_HOURS = 24
MAX_SIGNALS = 8
PUSH_INTERVAL = 300

TX_ACTIONS = {'BUY', 'SELL', 'STOP_LOSS', 'BOARD', 'BOARD_LIGHTNING', 'CLOSING'}

def cleanup_old():
    if not ALERT_FILE.exists():
        return
    try:
        alerts = json.load(open(ALERT_FILE))
    except:
        return
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff = (datetime.now() - timedelta(hours=CUTOFF_HOURS)).strftime('%H:%M')
    modified = False
    for a in alerts:
        if a.get('sent'):
            continue
        d = a.get('date', '') or ''
        t = a.get('time', '') or ''
        action = a.get('action', '')
        if action in TX_ACTIONS:
            if not d or d != today or (t and t < cutoff):
                a['sent'] = True
                modified = True
        elif d and d != today:
            a['sent'] = True
            modified = True
    if modified:
        with open(ALERT_FILE, 'w') as f:
            json.dump(alerts, f, ensure_ascii=False)

def get_index():
    try:
        import urllib.request
        raw = urllib.request.urlopen('https://qt.gtimg.cn/q=sh000001,sz399001', timeout=3).read().decode('gbk')
        idx = []
        for ln in raw.strip().split('\n'):
            d = ln.split('~')
            if len(d) > 32:
                idx.append(f"{d[1]} {float(d[3]):.0f} {d[32]}%")
        return '  '.join(idx) if idx else ''
    except:
        return ''

def get_thermo():
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        return t.get('level', ''), t.get('advice', '')
    except:
        return '', ''

def get_pos():
    try:
        from pipeline.autotrade import get_band_positions
        pos, tv, tp = get_band_positions()
        return pos, tv, tp
    except:
        return {}, 0, 0

def load_state():
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {'last_push': 0, 'last_signals': [], 'last_buys': [], 'last_sells': []}

def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, ensure_ascii=False)

def relay():
    cleanup_old()
    if not ALERT_FILE.exists():
        return None
    try:
        alerts = json.load(open(ALERT_FILE))
    except:
        return None

    state = load_state()
    now_ts = time.time()
    now_str = datetime.now().strftime('%H:%M')

    important = [a for a in alerts if not a.get('sent') and a.get('action') in TX_ACTIONS]
    signals = [a for a in alerts if not a.get('sent') and a.get('action') == '🚀SIG']

    buys = [a for a in important if a.get('action') == 'BUY']
    sells = [a for a in important if a.get('action') in ('SELL', 'STOP_LOSS')]
    boards = [a for a in important if a.get('action') in ('BOARD_LIGHTNING', 'BOARD')]

    sig_map = {}
    for s in signals:
        code = s.get('code', '')
        try:
            pct = float(str(s.get('result', '')).split('+')[1].split('%')[0]) if '+' in str(s.get('result', '')) else 0
        except:
            pct = 0
        if code not in sig_map or pct > sig_map[code][0]:
            sig_map[code] = (pct, s.get('name', '?'), s.get('price', 0))

    top_sigs = sorted(sig_map.items(), key=lambda x: -x[1][0])

    sig_ids = [c for c, _ in top_sigs[:MAX_SIGNALS]]
    buy_ids = [a.get('code', '') for a in buys]
    sell_ids = [a.get('code', '') for a in sells]

    has_change = (
        sig_ids != state.get('last_signals', []) or
        buy_ids != state.get('last_buys', []) or
        sell_ids != state.get('last_sells', [])
    )
    if not has_change and (now_ts - state.get('last_push', 0)) < PUSH_INTERVAL:
        return None

    # 构建指纹: 信号代码+交易代码的hash (不含时间/指数)
    fp_parts = sorted(sig_ids) + sorted(buy_ids) + sorted(sell_ids)
    fp = hashlib.md5(','.join(fp_parts).encode()).hexdigest() if fp_parts else 'empty'

    lines = [f"📊 {now_str} DAO"]

    idx = get_index()
    if idx:
        lines.append(idx)

    tl, ta = get_thermo()
    if tl:
        lines.append(f"🌡 {tl} | {ta}")

    pos, tv, tp = get_pos()
    if pos:
        lines.append(f"💼 持仓{len(pos)}只 ¥{tv:,.0f} | {tp:+,.0f}")

    if buys:
        lines.append("\n💰 买入:")
        for a in buys[-3:]:
            lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 ¥{a['price']}")
    if sells:
        lines.append("\n📉 卖出:")
        for a in sells[-3:]:
            lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 ¥{a['price']}")
    if boards:
        lines.append("\n⚡ 打板:")
        for a in boards[-3:]:
            lines.append(f"  {a['name']}({a['code']}) ¥{a['price']}")

    if top_sigs:
        new_count = len([c for c, _ in top_sigs if c not in state.get('last_signals', [])])
        label = f"\n📡 信号({len(top_sigs)}只"
        if new_count:
            label += f" 🆕{new_count}"
        label += ")"
        lines.append(label)
        for code, (pct, name, price) in top_sigs[:MAX_SIGNALS]:
            new_mark = " 🆕" if code not in state.get('last_signals', []) else ""
            lines.append(f"  {code} {name} {pct:+.1f}% ¥{price}{new_mark}")

    msg = '\n'.join(lines)

    # 写入文件
    RELAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RELAY_FILE, 'w') as f:
        f.write(msg)
    with open(FP_FILE, 'w') as f:
        f.write(fp)

    state['last_push'] = now_ts
    state['last_signals'] = sig_ids
    state['last_buys'] = buy_ids
    state['last_sells'] = sell_ids
    save_state(state)
    return msg

if __name__ == '__main__':
    msg = relay()
    if msg:
        print(msg)
    else:
        print("⏭ 无变化,跳过")
