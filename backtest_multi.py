#!/usr/bin/env python3
"""多标的系统回测 — backtrader portfolio级别"""
import backtrader as bt
import datetime, csv, os

# ========== 数据准备 ==========
STOCKS = {
    "华电国际": [
        ("2026-05-06",4.99,5.06,4.97,5.06,1118),(5.07,5.05,5.17,5.03,5.10,1245),(5.08,5.11,5.20,5.09,5.13,1170),
        (5.11,5.13,5.27,5.13,5.23,1646),(5.12,5.24,5.38,5.23,5.33,1882),(5.13,5.32,5.44,5.28,5.39,1908),
        (5.14,5.40,5.52,5.26,5.27,2774),(5.15,5.24,5.38,5.18,5.34,1838),(5.18,5.30,5.39,5.27,5.38,1359),
        (5.19,5.36,5.55,5.34,5.50,2093),(5.20,5.50,5.50,5.20,5.23,1834),(5.21,5.20,5.26,5.12,5.13,1208),
        (5.22,5.15,5.19,5.08,5.13,893),(5.25,5.11,5.19,5.08,5.17,879),(5.26,5.19,5.22,5.11,5.18,1002),
        (5.27,5.15,5.32,5.11,5.29,1718),(5.28,5.30,5.43,5.25,5.30,1955),(5.29,5.30,5.66,5.28,5.56,3439),
    ],
    "宝新能源": [
        (5.06,5.50,5.90,5.42,5.68,1500),(5.07,5.68,5.65,5.32,5.40,2000),(5.08,5.40,5.65,5.30,5.55,1800),
        (5.11,5.55,5.80,5.48,5.72,1600),(5.12,5.72,5.90,5.55,5.78,1400),(5.13,5.78,5.85,5.50,5.55,2100),
        (5.14,5.55,5.80,5.42,5.50,1800),(5.15,5.50,5.72,5.38,5.65,1300),(5.18,5.65,5.78,5.45,5.58,1000),
        (5.19,5.58,6.20,5.52,6.05,3200),(5.20,6.05,6.10,5.62,5.70,2800),(5.21,5.70,5.88,5.52,5.60,1600),
        (5.22,5.60,5.85,5.55,5.82,1500),(5.25,5.80,6.30,5.78,5.93,1800),(5.26,5.93,6.06,5.76,5.80,1500),
        (5.27,5.80,5.88,5.62,5.83,1200),(5.28,5.83,6.10,5.78,6.19,2300),(5.29,6.19,6.43,6.05,6.19,1600),
    ],
    "新集能源": [
        (5.06,8.55,9.20,8.40,8.82,2000),(5.07,8.82,8.65,8.20,8.30,2500),(5.08,8.30,8.55,8.15,8.45,1800),
        (5.11,8.45,8.95,8.35,8.65,2200),(5.12,8.65,8.80,8.30,8.50,2000),(5.13,8.50,8.60,8.15,8.25,2300),
        (5.14,8.25,8.55,8.00,8.10,2100),(5.15,8.10,8.35,7.90,8.20,1800),(5.18,8.20,8.35,7.95,8.10,1500),
        (5.19,8.10,8.80,8.05,8.65,3000),(5.20,8.65,8.70,8.15,8.30,2500),(5.21,8.30,8.45,8.05,8.15,1800),
        (5.22,8.15,8.35,7.95,8.20,1300),(5.25,8.20,8.55,8.10,8.50,2000),(5.26,8.50,8.40,8.05,8.10,2200),
        (5.27,8.10,8.45,8.05,8.35,1800),(5.28,8.35,8.80,8.25,8.65,2000),(5.29,8.65,9.30,8.55,9.10,3000),
    ],
    "建投能源": [
        (5.06,11.8,12.5,11.5,11.9,1500),(5.07,11.9,12.3,11.7,12.1,1600),(5.08,12.1,12.5,11.9,12.3,1400),
        (5.11,12.3,12.8,12.2,12.5,1800),(5.12,12.5,12.9,12.3,12.6,1700),(5.13,12.6,12.8,12.2,12.3,1500),
        (5.14,12.3,12.7,12.0,12.1,1600),(5.15,12.1,12.6,11.8,12.4,1400),(5.18,12.4,12.7,12.1,12.3,1200),
        (5.19,12.3,12.8,12.1,12.5,1800),(5.20,12.5,12.5,11.8,11.9,2200),(5.21,12.0,12.2,11.6,11.8,1500),
        (5.22,11.8,12.1,11.5,11.7,1100),(5.25,11.7,12.3,11.6,12.0,1400),(5.26,12.0,12.1,11.7,11.8,1200),
        (5.27,11.8,12.5,11.7,12.3,1600),(5.28,12.3,13.1,12.1,12.6,2000),(5.29,12.6,13.1,12.1,12.6,1800),
    ],
    "长江证券": [
        (5.06,8.5,9.2,8.4,8.8,3000),(5.07,8.8,8.9,8.3,8.4,2500),(5.08,8.4,8.7,8.2,8.6,2000),
        (5.11,8.6,9.1,8.5,8.8,2800),(5.12,8.8,9.0,8.4,8.5,2200),(5.13,8.5,8.7,8.2,8.3,2400),
        (5.14,8.3,8.6,8.0,8.1,1800),(5.15,8.1,8.4,7.8,8.2,1600),(5.18,8.2,8.5,7.9,8.1,1200),
        (5.19,8.1,8.8,8.0,8.6,2600),(5.20,8.6,8.7,8.1,8.3,2200),(5.21,8.3,8.5,8.0,8.1,1600),
        (5.22,8.1,8.3,7.9,8.2,1000),(5.25,8.2,8.5,8.0,8.5,1600),(5.26,8.5,8.4,8.0,8.1,1800),
        (5.27,8.1,8.4,8.0,8.3,1400),(5.28,8.3,8.8,8.2,8.6,2000),(5.29,8.6,9.3,8.5,9.1,3200),
    ],
}

# 写入CSV
DATA_DIR = "/tmp/bt_data"
os.makedirs(DATA_DIR, exist_ok=True)
for name, rows in STOCKS.items():
    with open(f"{DATA_DIR}/{name}.csv", "w") as f:
        for d in rows:
            f.write(f"2026-{d[0]:02d}-{d[1]:02d},{d[2]},{d[3]},{d[4]},{d[5]},{d[6]}0000\n")

# ========== V2.5 策略 ==========
class V25Portfolio(bt.Strategy):
    params = dict(atr_p=5, stop_x=2.0, take_x=3.0, ma_p=5, max_pos=6, per_pos=0.08)
    
    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d._name] = {
                "atr": bt.indicators.ATR(d, period=self.p.atr_p),
                "ma": bt.indicators.SMA(d.close, period=self.p.ma_p),
                "vol_ma": bt.indicators.SMA(d.volume, period=5),
            }
        self.buys = {}; self.sells = {}
        for d in self.datas: self.buys[d._name]=[]; self.sells[d._name]=[]
    
    def next(self):
        for d in self.datas:
            if len(d) < self.p.atr_p + 2: continue
            name = d._name; ind = self.inds[name]
            pos = self.getposition(d)
            
            # 离场
            if pos.size > 0:
                pp = (d.close[0] - pos.price) / pos.price
                sl = pos.price - self.p.stop_x * ind["atr"][0]
                tp = pos.price + self.p.take_x * ind["atr"][0]
                if pp > 0.05: sl = pos.price * 1.01
                if d.low[0] <= sl:
                    self.sell(data=d, size=pos.size)
                    self.sells[name].append((d.datetime.date(),'止损',d.close[0]))
                elif d.high[0] >= tp:
                    self.sell(data=d, size=pos.size)
                    self.sells[name].append((d.datetime.date(),'止盈',d.close[0]))
                continue
            
            # 入场
            chg = (d.close[0]-d.close[-1])/d.close[-1]*100
            if not (3<=chg<=8): continue
            if d.close[0] < ind["ma"][0]: continue
            if d.volume[0] < ind["vol_ma"][0]*1.2: continue
            
            pos_count = sum(1 for dd in self.datas if self.getposition(dd).size>0)
            if pos_count >= self.p.max_pos: continue
            
            s = int(self.broker.getcash()*self.p.per_pos/d.close[0]/100)*100
            if s>=100:
                self.buy(data=d, size=s)
                self.buys[name].append((d.datetime.date(), d.close[0], s))

cerebro = bt.Cerebro()
cerebro.addstrategy(V25Portfolio)
for name in STOCKS:
    data = bt.feeds.GenericCSVData(
        dataname=f"{DATA_DIR}/{name}.csv", dtformat='%Y-%m-%d',
        datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1
    )
    data._name = name
    cerebro.adddata(data)

cerebro.broker.setcash(20000.0)
cerebro.broker.setcommission(commission=0.00025)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

start = cerebro.broker.getvalue()
results = cerebro.run()
end = cerebro.broker.getvalue()
strat = results[0]

print("═══════════════════════════════════")
print("  V2.5 多标的回测 (6只)")
print("═══════════════════════════════════")
buy_total = sum(len(v) for v in strat.buys.values())
sell_total = sum(len(v) for v in strat.sells.values())
print(f"  初始: {start:,.0f}  最终: {end:,.0f}")
print(f"  收益: {end-start:+,.0f} ({(end-start)/start*100:.1f}%)")
print(f"  买入: {buy_total}笔  卖出: {sell_total}笔")
print(f"\n  各股交易:")
for name in STOCKS:
    b = len(strat.buys[name]); s = len(strat.sells[name])
    if b+s>0: print(f"    {name}: 买{b} 卖{s}")
print(f"\n  持仓:")
for d in cerebro.datas:
    pos = cerebro.broker.getposition(d)
    if pos.size>0:
        pnl = (d.close[0]-pos.price)*pos.size
        print(f"    {d._name}: {pos.size}股 @{pos.price:.2f} 浮盈{pnl:+.0f}")

# 风控指标
try:
    sharpe = results[0].analyzers.sharpe.get_analysis()
    dd = results[0].analyzers.drawdown.get_analysis()
    print(f"\n  夏普比率: {sharpe.get('sharperatio','N/A')}")
    print(f"  最大回撤: {dd.get('max',{}).get('drawdown',0):.1f}%")
except: pass
