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
