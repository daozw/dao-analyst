import backtrader as bt

class V25Strategy(bt.Strategy):
    params = dict(
        atr_period=5,      # 18天数据用5日ATR
        stop_mult=2.0,
        take_mult=3.0,
        ma5_period=5,
        ma20_period=10,    # 降为10
        position_pct=0.10,
        max_positions=3,
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.ma5 = bt.indicators.SMA(self.data.close, period=self.p.ma5_period)
        self.ma20 = bt.indicators.SMA(self.data.close, period=self.p.ma20_period)
        self.vol_ma5 = bt.indicators.SMA(self.data.volume, period=5)
        self.buy_price = None
        self.trades = 0
        self.entries = []
        self.exits = []
    
    def next(self):
        if len(self.data) < self.p.atr_period + 2: return
        
        if self.position:
            atr_val = self.atr[0]
            stop = self.buy_price - self.p.stop_mult * atr_val
            take = self.buy_price + self.p.take_mult * atr_val
            profit_pct = (self.data.close[0] - self.buy_price) / self.buy_price
            if profit_pct > 0.05:
                stop = self.buy_price * 1.01
            
            if self.data.low[0] <= stop:
                self.sell(size=self.position.size)
                self.exits.append((self.data.datetime.date(), '止损', self.data.close[0]))
            elif self.data.high[0] >= take:
                self.sell(size=self.position.size)
                self.exits.append((self.data.datetime.date(), '止盈', self.data.close[0]))
            return
        
        chg = (self.data.close[0] - self.data.close[-1]) / self.data.close[-1] * 100
        if not (3 <= chg <= 8): return
        if self.data.close[0] < self.ma5[0]: return
        if len(self.data) > self.p.ma20_period and self.data.close[0] < self.ma20[0]: return
        if self.data.volume[0] < self.vol_ma5[0] * 1.2: return
        
        size = int(self.broker.getcash() * self.p.position_pct / self.data.close[0] / 100) * 100
        if size < 100: return
        
        self.buy_price = self.data.close[0]
        self.trades += 1
        self.entries.append((self.data.datetime.date(), self.data.close[0], size))
        self.buy(size=size)
    
    def stop(self):
        print(f"\n  交易记录:")
        for d, p, s in self.entries:
            print(f"    {d} 买入 {s}股 @{p:.2f}")
        for d, t, p in self.exits:
            print(f"    {d} {t} @{p:.2f}")

cerebro = bt.Cerebro()
cerebro.addstrategy(V25Strategy)

data = bt.feeds.GenericCSVData(
    dataname='/tmp/huadian_may.csv',
    dtformat='%Y-%m-%d',
    datetime=0, open=1, high=2, low=3, close=4, volume=5,
    openinterest=-1
)
cerebro.adddata(data)
cerebro.broker.setcash(20000.0)
cerebro.broker.setcommission(commission=0.00025)

start = cerebro.broker.getvalue()
results = cerebro.run()
end = cerebro.broker.getvalue()

strat = results[0]
print(f"V2.5 backtrader回测 (华电国际 5月)")
print("="*50)
print(f"  初始: {start:,.0f}  最终: {end:,.0f}")
print(f"  收益: {end-start:+,.0f} ({(end-start)/start*100:.1f}%)")
print(f"  买入: {strat.trades}笔  退出: {len(strat.exits)}笔")
