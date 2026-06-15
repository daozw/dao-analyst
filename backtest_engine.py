#!/usr/bin/env python3
"""
🦅 猎鹰回测引擎 v1.0 — DAO分析师 V3.1
==============================
独立于路径迁移，自动发现 venv 和数据源
支持: 单策略回测 / 网格搜索 / 多周期 / 持久化
"""

import sys, json, time, warnings
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional

warnings.filterwarnings('ignore')

# ====== 自动发现 venv ======
def _find_venv():
    for p in [
        Path.home() / "quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages",
        Path.home() / "dao-analyst/.venv/lib/python3.12/site-packages",
    ]:
        if p.exists():
            return str(p)
    raise RuntimeError("找不到 venv，请先部署")

sys.path.insert(0, _find_venv())

import pandas as pd
import numpy as np
from mootdx.quotes import Quotes

# ====== 数据结构 ======
@dataclass
class StrategyParams:
    """策略参数"""
    name: str = "猎鹰"
    version: str = "v2.6T"
    ma_period: int = 20
    atr_period: int = 14
    stop_atr: float = 2.5
    profit_atr: float = 3.5
    chg_min: float = 0.3
    chg_max: float = 8.0
    vol_ratio_min: float = 1.2
    kelly_fraction: float = 0.25
    capital: float = 20000
    use_ma5: bool = True

@dataclass
class Trade:
    code: str
    name: str
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    shares: int
    pnl: float
    pnl_pct: float
    reason: str

@dataclass
class BacktestResult:
    params: StrategyParams
    period: str
    total_stocks: int
    signals: int
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_win: float
    max_loss: float
    sharpe: float = 0.0
    trades_detail: list = field(default_factory=list)

# ====== 核心引擎 ======
class FalconBacktest:
    """猎鹰回测引擎"""
    
    def __init__(self):
        self.client = Quotes.factory(market='std')
        self._stock_cache = {}
    
    def get_stock_pool(self, market='mainboard'):
        """获取股票池"""
        all_stocks = self.client.stocks()
        ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
        
        if market == 'mainboard':
            mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
                    ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
                    ~all_stocks['name'].str.contains('ST|退', na=False))
        elif market == 'watchlist':
            codes = ['002837','000733','002015','000600','002298','002137','002703']
            mask = all_stocks['code'].astype(str).isin(codes)
        else:
            mask = all_stocks['code'].astype(str).isin(market if isinstance(market, list) else [])
        
        pool = all_stocks[mask]
        return pool['code'].astype(str).tolist(), dict(zip(pool['code'].astype(str), pool['name']))
    
    def fetch_data(self, code, lookback=35):
        """获取个股日线"""
        try:
            df = self.client.bars(symbol=code, frequency=9, start=0, offset=lookback)
            if df is None or df.empty or len(df) < 15:
                return None
            df = df.sort_index()
            # 价格过滤
            if df['close'].mean() < 1 or df['close'].mean() > 500:
                return None
            return df
        except:
            return None
    
    def calc_indicators(self, df, params: StrategyParams):
        """计算技术指标"""
        df = df.copy()
        df['ma20'] = df['close'].rolling(params.ma_period).mean()
        if params.use_ma5:
            df['ma5'] = df['close'].rolling(5).mean()
        h, l, c = df['high'], df['low'], df['close']
        pc = c.shift(1)
        df['tr'] = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
        df['atr'] = df['tr'].rolling(params.atr_period).mean()
        df['chg'] = c.pct_change() * 100
        df['vma5'] = df['volume'].rolling(5).mean()
        df['vratio'] = df['volume'] / df['vma5']
        return df
    
    def check_entry(self, row, params: StrategyParams):
        """检查买入条件"""
        if pd.isna(row['ma20']) or pd.isna(row['atr']) or row['atr'] == 0:
            return False
        if row['close'] <= row['ma20']:
            return False
        if params.use_ma5 and row['close'] <= row.get('ma5', 0):
            return False
        if not (params.chg_min < row['chg'] < params.chg_max):
            return False
        if row['vratio'] <= params.vol_ratio_min:
            return False
        return True
    
    def calc_position(self, buy_price, stop_price, target_price, params: StrategyParams):
        """凯利仓位计算"""
        lr = abs(stop_price - buy_price) / buy_price
        pr = abs(target_price - buy_price) / buy_price
        if pr * lr <= 0:
            return 0
        kelly = (0.55 * pr - 0.45 * lr) / (pr * lr)
        kelly = max(0, min(abs(kelly) * params.kelly_fraction, 0.3))
        shares = int(params.capital * kelly / buy_price / 100) * 100
        return shares if shares >= 100 else 0
    
    def run(self, params: StrategyParams, codes=None, start=None, end=None, 
            market='mainboard', verbose=True):
        """执行回测"""
        if start is None:
            start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if end is None:
            end = datetime.now().strftime('%Y-%m-%d')
        
        if codes is None:
            codes, names = self.get_stock_pool(market)
        elif isinstance(codes, str):
            codes, names = self.get_stock_pool(codes)
        else:
            names = {}
        
# 缓存检查: 同策略+同周期跳过
        cache_key = f"{params.name}_{params.version}_{start}_{end}_{len(codes)}"
        if verbose:
            print(f"🦅 {params.name} {params.version} | {start}~{end} | {len(codes)}只")
        
        all_trades = []
        t0 = time.time()
        
        for i, code in enumerate(codes):
            df = self.fetch_data(code)
            if df is None:
                continue
            
            mask = (df.index >= start) & (df.index <= end + ' 23:59:59')
            period_data = df[mask]
            if period_data.empty or len(period_data) < 1:
                continue
            
            df = self.calc_indicators(df, params)
            
            # 模拟交易
            pos = None
            for idx in period_data.index:
                row = df.loc[idx]
                
                if pos is None:
                    if self.check_entry(row, params):
                        bp = row['close']
                        sl = bp - params.stop_atr * row['atr']
                        tp = bp + params.profit_atr * row['atr']
                        shares = self.calc_position(bp, sl, tp, params)
                        if shares > 0:
                            pos = (bp, shares, sl, tp, str(idx)[:10])
                else:
                    bp_, shares_, sl_, tp_, bd = pos
                    reason = sp = None
                    
                    if row['low'] <= sl_:
                        reason, sp = '止损', sl_
                    elif row['high'] >= tp_:
                        reason, sp = '止盈', tp_
                    elif row['close'] < row['ma20'] and row.get('chg', 0) < -2:
                        reason, sp = '破MA', row['close']
                    
                    if reason:
                        sp = max(sp, bp_ * 0.93)
                        pnl = (sp - bp_) * shares_
                        pnl_pct = (sp / bp_ - 1) * 100
                        all_trades.append(Trade(
                            code=code, name=names.get(code, ''),
                            buy_date=bd, sell_date=str(idx)[:10],
                            buy_price=bp_, sell_price=round(sp, 2),
                            shares=shares_, pnl=round(pnl, 2),
                            pnl_pct=round(pnl_pct, 2), reason=reason
                        ))
                        pos = None
            
            # 期末平仓
            if pos:
                bp_, shares_, sl_, tp_, bd = pos
                last = period_data.iloc[-1]
                sp = last['close']
                pnl = (sp - bp_) * shares_
                pnl_pct = (sp / bp_ - 1) * 100
                all_trades.append(Trade(
                    code=code, name=names.get(code, ''),
                    buy_date=bd, sell_date=str(last.name)[:10],
                    buy_price=bp_, sell_price=round(sp, 2),
                    shares=shares_, pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 2), reason='持仓'
                ))
            
            if verbose and (i+1) % 500 == 0:
                print(f"  {i+1}/{len(codes)} 交易{len(all_trades)}")
        
        # 统计
        wins = [t for t in all_trades if t.pnl > 0]
        losses = [t for t in all_trades if t.pnl <= 0]
        signal_codes = set(t.code for t in all_trades)
        
        total_pnl = sum(t.pnl for t in all_trades)
        wr = len(wins) / len(all_trades) * 100 if all_trades else 0
        aw = np.mean([t.pnl for t in wins]) if wins else 0
        al = np.mean([t.pnl for t in losses]) if losses else 0
        pf = abs(aw / al) if aw and al else 0
        
        result = BacktestResult(
            params=params,
            period=f"{start}~{end}",
            total_stocks=len(codes),
            signals=len(signal_codes),
            trades=len(all_trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=round(wr, 1),
            total_pnl=round(total_pnl, 2),
            avg_win=round(aw, 2),
            avg_loss=round(al, 2),
            profit_factor=round(pf, 2),
            max_win=max(t.pnl for t in all_trades) if all_trades else 0,
            max_loss=min(t.pnl for t in all_trades) if all_trades else 0,
            trades_detail=[asdict(t) for t in sorted(all_trades, key=lambda x: x.pnl, reverse=True)]
        )
        
        if verbose:
            elapsed = time.time() - t0
            print(f"  ✅ {result.signals}信号 {result.trades}笔 胜率{result.win_rate}% "
                  f"盈亏{result.total_pnl:+.0f} PF{result.profit_factor} ({elapsed:.0f}s)")
        
        return result
    
    def grid_search(self, param_grid: dict, codes=None, start=None, end=None, market='mainboard'):
        """网格搜索最优参数"""
        import itertools
        
        base = StrategyParams()
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        results = []
        total = 1
        for v in values:
            total *= len(v)
        
        print(f"🔍 网格搜索: {total}种组合")
        
        for i, combo in enumerate(itertools.product(*values)):
            params_dict = asdict(base)
            for k, v in zip(keys, combo):
                params_dict[k] = v
            params = StrategyParams(**params_dict)
            params.name = f"GS-{i+1}"
            params.version = ""
            
            result = self.run(params, codes=codes, start=start, end=end, 
                            market=market, verbose=False)
            results.append(result)
            
            desc = ', '.join(f"{k}={v}" for k, v in zip(keys, combo))
            print(f"  [{i+1}/{total}] {desc} → "
                  f"{result.signals}信号 胜率{result.win_rate}% 盈亏{result.total_pnl:+.0f}")
        
        # 排序
        results.sort(key=lambda x: x.total_pnl, reverse=True)
        return results
    
    def save_result(self, result: BacktestResult, path: str = None):
        """保存结果到JSON"""
        if path is None:
            path = str(Path.home() / "dao-analyst/backtest/results.json")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # 加载已有
        existing = []
        if Path(path).exists():
            with open(path) as f:
                existing = json.load(f)
        
        # 追加
        record = {
            'timestamp': datetime.now().isoformat(),
            'params_name': f"{result.params.name} {result.params.version}",
            'params': asdict(result.params),
            'period': result.period,
            'total_stocks': result.total_stocks,
            'signals': result.signals,
            'trades': result.trades,
            'wins': result.wins,
            'losses': result.losses,
            'win_rate': result.win_rate,
            'total_pnl': result.total_pnl,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'profit_factor': result.profit_factor,
            'top_trades': result.trades_detail[:10]
        }
        existing.append(record)
        
        with open(path, 'w') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        return path
    
    def load_history(self, path: str = None):
        """加载历史回测记录"""
        if path is None:
            path = str(Path.home() / "dao-analyst/backtest/results.json")
        if not Path(path).exists():
            return []
        with open(path) as f:
            return json.load(f)
    
    def print_history(self, path: str = None):
        """打印回测历史对比"""
        history = self.load_history(path)
        if not history:
            print("暂无回测记录")
            return
        
        print(f"\n📊 回测历史 ({len(history)}条)")
        print(f"  {'时间':<16} {'策略':<16} {'周期':<18} {'信号':>4} {'胜率':>6} {'盈亏':>8}")
        print(f"  {'─'*70}")
        for h in history[-10:]:  # 最近10条
            ts = h['timestamp'][:16]
            print(f"  {ts:<16} {h['params_name']:<16} {h['period']:<18} "
                  f"{h['signals']:>4} {h['win_rate']:>5.1f}% {h['total_pnl']:>+8.0f}")


# ====== CLI ======
if __name__ == "__main__":
    engine = FalconBacktest()
    
    if len(sys.argv) < 2:
        print("🦅 猎鹰回测引擎 v1.0")
        print("用法:")
        print("  python3 backtest_engine.py run [start] [end]      运行回测")
        print("  python3 backtest_engine.py grid                   网格搜索")
        print("  python3 backtest_engine.py history                查看历史")
        print("  python3 backtest_engine.py compare                版本对比")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "run":
        start = sys.argv[2] if len(sys.argv) > 2 else None
        end = sys.argv[3] if len(sys.argv) > 3 else None
        params = StrategyParams()
        result = engine.run(params, start=start, end=end, market='watchlist')
        engine.save_result(result)
        engine.print_history()
    
    elif cmd == "grid":
        # 示例网格搜索
        grid = {
            'stop_atr': [1.5, 2.0, 2.5],
            'profit_atr': [2.0, 2.5, 3.0],
            'chg_min': [1.5, 2.0, 2.5],
            'vol_ratio_min': [1.2, 1.4, 1.6],
        }
        results = engine.grid_search(grid, market='mainboard', 
                                     start='2026-05-25', end='2026-05-29')
        print(f"\n🏆 TOP 5:")
        for i, r in enumerate(results[:5]):
            print(f"  {i+1}. {r.params_name} 胜率{r.win_rate}% 盈亏{r.total_pnl:+.0f} "
                  f"PF{r.profit_factor}")
    
    elif cmd == "history":
        engine.print_history()
    
    elif cmd == "compare":
        # 生成演进对比表
        print("🦅 猎鹰策略演进")
        print(f"  {'版本':<18} {'信号':>4} {'胜率':>6} {'盈亏':>8} {'PF':>5}")
        print(f"  {'─'*45}")
        history = engine.load_history()
        for h in history:
            print(f"  {h['params_name']:<18} {h['signals']:>4} "
                  f"{h['win_rate']:>5.1f}% {h['total_pnl']:>+8.0f} {h['profit_factor']:>5.2f}")
