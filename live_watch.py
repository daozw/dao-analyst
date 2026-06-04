#!/usr/bin/env python3
"""东方财富 WebSocket 实时盯盘 — 毫秒级行情推送"""

import asyncio, json, struct, zlib, time, sys
from datetime import datetime

# 东方财富实时行情 WebSocket
WS_URL = "ws://push2.eastmoney.com/api/qt/ws"

# 股票代码前缀: 0=深交所 1=上交所
def to_em_code(ticker):
    return f"{'0' if ticker.startswith(('0','3','2')) else '1'}.{ticker}"

# 要盯的股票
WATCH = {
    "002837": "英维克", "000733": "振华科技", "002015": "协鑫能科",
    "000600": "建投能源", "002298": "中电鑫龙", "002137": "实益达"
}

async def connect():
    """连接东方财富 WebSocket"""
    import websockets
    async with websockets.connect(WS_URL, ping_interval=30) as ws:
        # 订阅实时行情
        codes = ",".join(to_em_code(c) for c in WATCH)
        sub = {
            "op": "sub",
            "args": [f"push_realtimestock?fields=162,167,168,169,170,171,47,48,50&codes={codes}"]
        }
        await ws.send(json.dumps(sub))
        print(f"📡 已订阅 {len(WATCH)} 只股票\n")
        
        # 逐笔 header
        header = f"{'时间':<10} {'名称':<8} {'最新':>8} {'涨幅':>8} {'成交额':>12} {'换手':>6}"
        print(header)
        print("-" * 58)
        
        while True:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=60)
                # 解压
                if isinstance(data, bytes):
                    data = zlib.decompress(data, 15)
                msg = json.loads(data)
                
                if "data" not in msg:
                    continue
                    
                for item in msg["data"]:
                    code = item.get("c", "")
                    if not code:
                        continue
                    
                    ticker = code.split(".")[-1]
                    name = WATCH.get(ticker, ticker)
                    
                    price = item.get("162", 0) / 100  # 最新价
                    pct = item.get("170", 0) / 100     # 涨跌幅(%)
                    amt = item.get("48", 0)             # 成交额
                    turnover = item.get("168", 0) / 100  # 换手率
                    
                    now = datetime.now().strftime("%H:%M:%S")
                    arrow = "🔺" if pct > 0 else "🔻" if pct < 0 else "➖"
                    
                    amt_str = f"{amt/1e8:.1f}亿" if amt > 1e8 else f"{amt/1e4:.0f}万"
                    
                    print(f"{now:<10} {arrow}{name:<6} {price:>8.2f} {pct:>+7.2f}% {amt_str:>12} {turnover:>6.2f}%")
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"⚠️ {e}")
                break

async def http_poll(interval=3):
    """HTTP 轮询备选方案（兼容性更好）"""
    import subprocess
    
    script = "/Users/sound/.openclaw-autoclaw/skills/a-stock-analysis/scripts/analyze.py"
    
    while True:
        now = datetime.now().strftime("%H:%M:%S")
        lines = []
        for ticker, name in WATCH.items():
            try:
                r = subprocess.run(
                    ["python3", script, ticker, "--json"],
                    capture_output=True, text=True, timeout=10
                )
                d = json.loads(r.stdout)[0]["realtime"]
                arrow = "🔺" if d["change_pct"] > 0 else "🔻" if d["change_pct"] < 0 else "➖"
                lines.append(f"  {arrow} {name:<6} {d['price']:>8.2f} {d['change_pct']:>+6.2f}%")
            except:
                lines.append(f"  ❌ {name:<6} {'--':>8}")
        
        print(f"\n{'='*50}")
        print(f"📊 {now}")
        print(f"{'='*50}")
        for l in lines:
            print(l)
        
        await asyncio.sleep(interval)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"
    
    if mode == "ws":
        print("🔄 WebSocket 实时盯盘模式\n")
        try:
            asyncio.run(connect())
        except ImportError:
            print("❌ 需要 websockets 库: pip install websockets")
            print("回退到 HTTP 轮询模式...\n")
            asyncio.run(http_poll(5))
    else:
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        print(f"🔄 HTTP 轮询盯盘 (间隔 {interval}s)\n")
        asyncio.run(http_poll(interval))
