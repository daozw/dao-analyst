#!/usr/bin/env python3
"""Level-2数据分析 — 封单监控 + 拖拉机单 + 盘口失衡 + 主力流向"""
import json, os, time, sys
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ────────────────────────────────
# 1. 封单监控 (打板核心)
# ────────────────────────────────
class SealMonitor:
    """监控涨停板封单强度变化"""
    def __init__(self, max_history=10):
        self.history = {}  # code → deque of (时间, 封单量, 封单金额)
        self.max_history = max_history
    
    def update(self, code, order_book):
        """更新封单数据"""
        limit_up = order_book.get('limit_up')
        if not limit_up:
            return None
        
        # 计算涨停价上的总买单
        bid_vol = 0; bid_amt = 0
        for bid in order_book.get('bids', []):
            if bid['price'] >= limit_up:
                bid_vol += bid['volume']
                bid_amt += bid['price'] * bid['volume'] * 100
        
        if code not in self.history:
            self.history[code] = deque(maxlen=self.max_history)
        
        self.history[code].append({
            'time': time.time(),
            'vol': bid_vol,
            'amt': bid_amt
        })
        
        return self._analyze(code)
    
    def _analyze(self, code):
        """分析封单变化趋势"""
        h = list(self.history.get(code, []))
        if len(h) < 3:
            return {"status": "观望", "signal": 0}
        
        # 封单量趋势
        vols = [x['vol'] for x in h]
        amts = [x['amt'] for x in h]
        
        # 最近3次变化率
        if vols[0] > 0:
            trend = (vols[-1] - vols[0]) / vols[0] * 100
        else:
            trend = 0
        
        if trend < -50:
            return {"status": "💥封单崩塌", "signal": -3, "trend": trend,
                    "msg": f"封单3秒内减少{abs(trend):.0f}%, 预判炸板!"}
        elif trend < -20:
            return {"status": "⚠️封单衰减", "signal": -1, "trend": trend,
                    "msg": f"封单减少{abs(trend):.0f}%, 注意风险"}
        elif trend > 20:
            return {"status": "🔥封单加强", "signal": 2, "trend": trend,
                    "msg": f"封单增加{trend:.0f}%, 封板牢固"}
        else:
            # 封单绝对值判断
            if amts and amts[-1] < 1000:  # 封单<1000万
                return {"status": "🟡封单偏弱", "signal": -1, "trend": trend,
                        "msg": f"封单仅{amts[-1]/10000:.0f}万, 易开板"}
            return {"status": "✅封单稳定", "signal": 1, "trend": trend}

# ────────────────────────────────
# 2. 拖拉机单检测
# ────────────────────────────────
class TractorDetector:
    """检测大单拆分(拖拉机单): 连续同向小单"""
    def __init__(self, window_sec=5, min_count=5):
        self.recent = deque(maxlen=100)  # (code, dir, vol, time)
        self.window = window_sec
        self.min_count = min_count
    
    def feed(self, code, direction, volume, price):
        """喂入逐笔数据"""
        self.recent.append((code, direction, volume, price, time.time()))
    
    def check(self, code):
        """检查拖拉机单"""
        now = time.time()
        # 过滤最近window内的同code同方向单
        same = [(d, v, p, t) for c, d, v, p, t in self.recent 
                if c == code and now - t < self.window]
        
        if len(same) < self.min_count:
            return None
        
        buys = [(v, p) for d, v, p, t in same if d == 'buy']
        sells = [(v, p) for d, v, p, t in same if d == 'sell']
        
        # 同向单数量远大于反向
        if len(buys) >= self.min_count and len(sells) <= 1:
            total_vol = sum(v for v, _ in buys)
            avg_price = sum(v * p for v, p in buys) / max(total_vol, 1)
            return {"type": "拖拉机买入", "count": len(buys), 
                    "total_vol": total_vol, "avg_price": avg_price,
                    "signal": 3}
        elif len(sells) >= self.min_count and len(buys) <= 1:
            total_vol = sum(v for v, _ in sells)
            avg_price = sum(v * p for v, p in sells) / max(total_vol, 1)
            return {"type": "拖拉机卖出", "count": len(sells),
                    "total_vol": total_vol, "avg_price": avg_price,
                    "signal": -3}
        
        return None

# ────────────────────────────────
# 3. 盘口失衡分析
# ────────────────────────────────
def order_book_imbalance(bids, asks, levels=5):
    """买卖盘口失衡率: 预测短期方向"""
    bid_vol = sum(b.get('volume', 0) for b in bids[:levels])
    ask_vol = sum(a.get('volume', 0) for a in asks[:levels])
    total = bid_vol + ask_vol
    
    if total == 0:
        return {"imbalance": 0, "signal": 0, "msg": "无数据"}
    
    imbalance = (bid_vol - ask_vol) / total  # -1(全卖) ~ +1(全买)
    
    if imbalance > 0.3:
        return {"imbalance": round(imbalance, 2), "signal": 2, 
                "msg": f"买盘占优({imbalance:.0%})→短线看涨"}
    elif imbalance < -0.3:
        return {"imbalance": round(imbalance, 2), "signal": -2,
                "msg": f"卖盘占优({-imbalance:.0%})→短线看跌"}
    else:
        return {"imbalance": round(imbalance, 2), "signal": 0, 
                "msg": f"盘口均衡({imbalance:.0%})"}

# ────────────────────────────────
# 4. 主力资金流向 (大单净流入)
# ────────────────────────────────
def big_order_flow(ticks, threshold_amt=500000):
    """大单净流入: 单笔>50万"""
    big_buy = 0; big_sell = 0
    
    for t in ticks:
        amt = t.get('price', 0) * t.get('volume', 0) * 100
        if amt < threshold_amt:
            continue
        if t.get('type') in ('买盘', '主动买入', 'buy'):
            big_buy += amt
        else:
            big_sell += amt
    
    net = big_buy - big_sell
    total = big_buy + big_sell
    
    if total == 0:
        return {"signal": 0, "msg": "无大单"}
    
    ratio = net / total
    if ratio > 0.2:
        return {"signal": 3, "net": net, "msg": f"主力净买{net/10000:.0f}万(+{ratio:.0%})"}
    elif ratio < -0.2:
        return {"signal": -3, "net": net, "msg": f"主力净卖{abs(net)/10000:.0f}万({ratio:.0%})"}
    else:
        return {"signal": 1 if net > 0 else -1, "net": net, "msg": f"主力{net/10000:.0f}万"}

# ────────────────────────────────
# 5. 综合Level-2信号
# ────────────────────────────────
def analyze_level2(code, snapshot, ticks=None):
    """综合Level-2分析 → 信号(-10~+10)"""
    score = 0
    signals = []
    
    # 盘口失衡
    bids = snapshot.get('bids', [])
    asks = snapshot.get('asks', [])
    imb = order_book_imbalance(bids, asks)
    score += imb['signal']
    if imb['signal'] != 0:
        signals.append(imb['msg'])
    
    # 主力流向
    if ticks:
        flow = big_order_flow(ticks)
        score += flow['signal']
        if flow['signal'] != 0:
            signals.append(flow['msg'])
    
    return {
        "score": max(-10, min(10, score)),
        "signals": signals,
        "imbalance": imb,
        "verdict": "🟢强势" if score >= 3 else ("🟡中性" if score >= 0 else "🔴弱势")
    }

if __name__ == '__main__':
    # 模拟测试
    print("📊 盘口失衡测试:")
    bids = [{'price': 167.0, 'volume': 500}, {'price': 166.99, 'volume': 300}]
    asks = [{'price': 167.01, 'volume': 200}, {'price': 167.02, 'volume': 100}]
    r = order_book_imbalance(bids, asks)
    print(f"  {r['msg']}")
    
    print("\n📊 封单测试:")
    sm = SealMonitor()
    # 模拟封单减少
    sm.update('test', {'limit_up': 10.0, 'bids': [{'price': 10.0, 'volume': 10000}]})
    sm.update('test', {'limit_up': 10.0, 'bids': [{'price': 10.0, 'volume': 5000}]})
    sm.update('test', {'limit_up': 10.0, 'bids': [{'price': 10.0, 'volume': 2000}]})
    r = sm.update('test', {'limit_up': 10.0, 'bids': [{'price': 10.0, 'volume': 1000}]})
    print(f"  {r['msg']}")
