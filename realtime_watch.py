#!/usr/bin/env python3
"""实时异动监控 V1.0 — WebSocket推送,秒级响应"""
import asyncio, json, struct, zlib, time, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 东财WebSocket
WS_URL = "ws://push2.eastmoney.com/api/qt/ws"

def load_watch_codes():
    """加载所有池子中的股票"""
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    codes = set()
    for g in ['core','band','board']:
        for s in wl['groups'].get(g,{}).get('stocks',[]):
            codes.add(s['code'])
    return list(codes)

def to_em(codes):
    """代码→东财格式"""
    result = []
    for c in codes:
        if c.startswith(('0','3','2')): result.append(f'0.{c}')
        else: result.append(f'1.{c}')
    return result

async def connect():
    codes = load_watch_codes()
    if not codes:
        print("无监控标的")
        return
    
    em_codes = to_em(codes)
    print(f"📡 实时监控 {len(codes)}只 | {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        import websockets
    except ImportError:
        print("❌ 需要 pip install websockets")
        return
    
    async with websockets.connect(WS_URL, ping_interval=30) as ws:
        sub = {"op":"sub","args":[f"push_realtimestock?fields=162,167,168,169,170,171,47,48,50&codes={','.join(em_codes)}"]}
        await ws.send(json.dumps(sub))
        
        alerts_sent = set()
        
        while True:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=60)
                if isinstance(data, bytes):
                    data = zlib.decompress(data, 15)
                msg = json.loads(data)
                
                if "data" not in msg: continue
                
                for item in msg["data"]:
                    code = item.get("c","").split(".")[-1]
                    price = item.get("162",0)/100
                    chg = item.get("170",0)/100
                    vol = item.get("47",0)
                    
                    # 异动检测阈值
                    if abs(chg) >= 3 and code not in alerts_sent:
                        alerts_sent.add(code)
                        name = item.get("n","")
                        now = datetime.now().strftime("%H:%M:%S")
                        
                        arrow = "🔴" if chg >= 9.5 else "🟠" if chg >= 5 else "🟢" if chg <= -5 else "⚡"
                        msg_text = f"{arrow} {name}({code}) ¥{price:.2f} {chg:+.1f}% [{now}]"
                        print(msg_text)
                        
                        # Queue alert
                        af = '/tmp/dao_trade_alerts.json'
                        alerts = []
                        if os.path.exists(af):
                            try: alerts = json.load(open(af))
                            except: pass
                        alerts.append({"time":now,"action":"REALTIME","code":code,"name":name,
                            "message":msg_text,"sent":False})
                        with open(af,"w") as f:
                            json.dump(alerts,f,ensure_ascii=False,indent=2)
                        
                        # 打板自动执行
                        try:
                            wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
                            board_codes = {s['code'] for s in wl['groups'].get('board',{}).get('stocks',[])}
                            band_codes = {s['code'] for s in wl['groups'].get('band',{}).get('stocks',[])}
                            
                            # 打板: 涨幅≥8%
                            if code in board_codes and chg >= 8:
                                # 检查竞价是否已挂单
                                sf = os.path.expanduser('~/dao-analyst/data/state/board_trade.json')
                                if os.path.exists(sf):
                                    import json as _j
                                    _st = _j.load(open(sf))
                                    if code in {s['code'] for s in _st.get('stocks',[])}:
                                        print(f'  ⏭️ {name} 竞价已挂单,跳过WebSocket')
                                        break
                                
                                import subprocess as sp
                                qty = min(500, int(10000 / price / 100) * 100)
                                if qty >= 100:
                                    env = {**os.environ, 'HT_APIKEY': os.environ.get('HT_APIKEY','ht_2dPFpTyi93kWDXZc5dlI2a7SFyfWCy3Y5cfcVLu2P')}
                                    skill = os.path.expanduser('~/.openclaw-autoclaw/skills/a-share-paper-trading/a_share_paper_trading.py')
                                    ex = 'SZ' if code.startswith(('0','3','2')) else 'SH'
                                    cmd = [sys.executable, skill, 'submitOrder', '--symbol', str(code),
                                           '--side', 'buy', '--quantity', str(qty), '--price', str(price), '--exchange', ex]
                                    sp.run(cmd, capture_output=True, text=True, env=env, timeout=10)
                                    alerts.append({"time":now,"action":"BOARD_TRADE","code":code,"name":name,
                                        "message":f'🔥 实时打板 {name}({code}) {qty}股 @¥{price:.2f}','sent':False})
                                    with open(af,"w") as f:
                                        json.dump(alerts,f,ensure_ascii=False,indent=2)
                                    print(f'  ⚡ 自动打板: {name} {qty}股')
                            
                            # 波段: 进入买入区间(-2%~5%) → 自动交易
                            if code in band_codes and -2 < chg < 5:
                                try:
                                    import sys as _sys
                                    _sys.path.insert(0, os.path.expanduser('~/dao-analyst'))
                                    from pipeline.fetcher import fetch
                                    from pipeline.signals import analyze
                                    from pipeline.autotrade import auto_trade, calc_shares
                                    d = fetch(code, use_cache=False)
                                    if 'error' not in d:
                                        a = analyze(d)
                                        if a['g'] >= 3:
                                            # 检查日限额
                                            state_file = os.path.expanduser('~/dao-analyst/data/state/band.json')
                                            import json as _j
                                            _state = _j.load(open(state_file)) if os.path.exists(state_file) else {'buy_count':0,'stocks':[]}
                                            if _state.get('buy_count',0) >= 3:
                                                print(f'  ⏭️ 波段 {name} 日限额已满')
                                                break
                                            if code in {s.get('code','') for s in _state.get('stocks',[])}:
                                                print(f'  ⏭️ 波段 {name} 今日已买')
                                                break
                                            
                                            pr = a['prices']
                                            shares = calc_shares(price, pr['stop_loss'])
                                            if shares >= 100:
                                                from pipeline.autotrade import _exec_trade
                                                ok, msg = _exec_trade('BUY', code, name, price, shares, False)
                                                tag = '✅' if ok else '❌'
                                                print(f'  📊 波段买入: {tag} {name} {shares}股 @¥{price:.2f}')
                                                alerts.append({"time":now,"action":"BAND_TRADE","code":code,"name":name,
                                                    "message":f'📊 波段买入 {tag} {name}({code}) {shares}股 @¥{price:.2f}','sent':False})
                                                with open(af,"w") as f:
                                                    json.dump(alerts,f,ensure_ascii=False,indent=2)
                                except: pass
                        except: pass
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"⚠️ {e}")
                break

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "codes":
        print(json.dumps(load_watch_codes()))
    else:
        try:
            asyncio.run(connect())
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
