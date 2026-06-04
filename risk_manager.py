#!/usr/bin/env python3
"""
统一止盈止损引擎 V1.0
解决: rules.md/backtest/weekly plan 三套规则不一致
原则: ATR动态 + 浮动止盈 + 时间止损 + 大盘联动
"""
from dataclasses import dataclass
from typing import Optional
import math

@dataclass
class StopLoss:
    initial: float      # 初始止损价
    current: float      # 当前止损价
    trailing_pct: float # 浮动比例
    atr_mult: float     # ATR倍数
    max_loss_pct: float # 最大亏损百分比
    time_limit_days: int # 持仓天数上限(未盈利)

@dataclass
class TakeProfit:
    target_pct: float   # 目标收益率
    partial_pct: float  # 部分止盈比例
    trail_from_high: float # 从高点回落比例
    force_days: int     # 强制止盈天数

class UnifiedRiskManager:
    """
    统一风控 — 所有策略共用
    
    三个止损维度:
    1. ATR动态止损 — 根据波动调整
    2. 浮动止盈 — 盈利后锁利润
    3. 时间止损 — 持仓过久未涨→出局
    """
    
    # 策略参数预设
    PRESETS = {
        "band": {       # V2.1波段
            "atr_stop": 2.0,      # 2×ATR
            "trail_pct": 0.05,    # 从高点回落5%
            "target": 0.15,       # +15%止盈
            "partial": 0.50,      # 止盈时卖50%
            "max_loss": 0.08,     # 最大亏8%
            "time_limit": 10,     # 10天未盈利出局
        },
        "dip": {        # 低吸
            "atr_stop": 1.5,
            "trail_pct": 0.04,
            "target": 0.20,
            "partial": 0.40,
            "max_loss": 0.06,
            "time_limit": 7,
        },
        "board": {      # 首板/涨停
            "atr_stop": 2.5,
            "trail_pct": 0.06,
            "target": 0.25,
            "partial": 0.60,
            "max_loss": 0.10,
            "time_limit": 3,
        },
        "momentum": {   # 动量
            "atr_stop": 2.0,
            "trail_pct": 0.05,
            "target": 0.10,
            "partial": 0.50,
            "max_loss": 0.07,
            "time_limit": 5,
        },
    }
    
    def __init__(self, strategy="band", atr_period=14):
        preset = self.PRESETS.get(strategy, self.PRESETS["band"])
        self.atr_mult = preset["atr_stop"]
        self.trail_pct = preset["trail_pct"]
        self.target_pct = preset["target"]
        self.partial_pct = preset["partial"]
        self.max_loss_pct = preset["max_loss"]
        self.time_limit = preset["time_limit"]
        self.atr_period = atr_period
    
    def initial_stop(self, entry_price, atr):
        """初始止损价"""
        stop = entry_price - self.atr_mult * atr
        # 不超过最大亏损
        max_stop = entry_price * (1 - self.max_loss_pct)
        return max(stop, max_stop)
    
    def trailing_stop(self, entry_price, highest_price, atr):
        """浮动止损: 从最高点回落 trail_pct"""
        trail = highest_price * (1 - self.trail_pct)
        atr_stop = highest_price - self.atr_mult * atr
        
        # 如果盈利>5%, 止损提到成本+1% (保本)
        if highest_price > entry_price * 1.05:
            breakeven = entry_price * 1.01
            return max(trail, atr_stop, breakeven)
        
        return max(trail, atr_stop)
    
    def check_stop(self, entry_price, current_price, highest_price, atr, days_held=0, is_profitable=True):
        """
        综合止损检查
        
        返回: (should_stop, reason, action_price)
        """
        reasons = []
        action = None
        
        # 1. ATR动态止损
        atr_stop = self.initial_stop(entry_price, atr)
        if current_price <= atr_stop:
            reasons.append(f"触发ATR止损({self.atr_mult}×ATR)")
            action = atr_stop
        
        # 2. 最大亏损硬止损
        max_stop = entry_price * (1 - self.max_loss_pct)
        if current_price <= max_stop:
            reasons.append(f"触发最大亏损{self.max_loss_pct*100:.0f}%")
            action = max_stop
        
        # 3. 浮动止盈(已盈利时)
        if highest_price > entry_price:
            trail = self.trailing_stop(entry_price, highest_price, atr)
            if current_price <= trail:
                profit = (highest_price - entry_price) / entry_price * 100
                reasons.append(f"触发浮动止盈(从+{profit:.1f}%回落{self.trail_pct*100:.0f}%)")
                action = trail
        
        # 4. 时间止损
        if days_held >= self.time_limit and not is_profitable:
            reasons.append(f"持仓{days_held}天未盈利, 触发时间止损")
            action = current_price
        
        if reasons:
            return True, " | ".join(reasons), action or current_price
        return False, "", None
    
    def check_take_profit(self, entry_price, current_price, highest_price):
        """
        止盈检查
        
        返回: (should_take, reason, sell_pct)
        """
        profit = (current_price - entry_price) / entry_price
        
        # 1. 达到目标收益率 → 卖部分
        if profit >= self.target_pct:
            return True, f"达到目标{self.target_pct*100:.0f}%", self.partial_pct
        
        # 2. 大幅超目标 → 卖更多
        if profit >= self.target_pct * 1.5:
            return True, f"超目标{(self.target_pct*1.5)*100:.0f}%", 0.70
        
        # 3. 涨停日止盈
        if profit >= 0.095:  # 接近涨停
            return True, "接近涨停", 0.50
        
        return False, "", 0

    def market_adjust(self, base_stop_mult, index_chg_5d, index_vol):
        """
        大盘联动调整 — 市场差时收紧止损
        
        index_chg_5d: 大盘5日涨跌%
        index_vol: 大盘波动率%
        """
        adj = 1.0
        
        # 大盘跌→止损收紧
        if index_chg_5d < -3: adj = 0.7
        elif index_chg_5d < -1: adj = 0.85
        elif index_chg_5d > 3: adj = 1.15  # 牛市可放宽
        
        # 高波动→收紧
        if index_vol > 2.5: adj *= 0.8
        
        return base_stop_mult * adj

# ═══════════════════════════════════
# 快速演示
# ═══════════════════════════════════
if __name__ == "__main__":
    rm = UnifiedRiskManager("band")
    
    print("=" * 55)
    print("  🛡️ 统一止盈止损引擎")
    print("=" * 55)
    
    # 场景演示
    tests = [
        ("正常止损", 10.0, 9.50, 10.20, 0.30, 2, True),
        ("浮动止盈", 10.0, 10.80, 11.00, 0.30, 5, True),
        ("时间止损", 10.0, 9.80, 10.00, 0.30, 12, False),
        ("达到目标", 10.0, 11.50, 11.50, 0.30, 3, True),
        ("最大亏损", 10.0, 9.10, 10.00, 0.30, 1, False),
    ]
    
    print(f"\n{'场景':<12} {'入场':>6} {'现价':>6} {'最高':>6} {'ATR':>5} {'天数':>4} → {'判定'}")
    print("-" * 55)
    for name, entry, current, high, atr, days, prof in tests:
        stop, reason, price = rm.check_stop(entry, current, high, atr, days, prof)
        take, treason, tpct = rm.check_take_profit(entry, current, high)
        
        if stop:
            print(f"  {name:<10} {entry:>5.2f} {current:>5.2f} {high:>5.2f} {atr:>4.2f} {days:>3}天 → 🔴 {reason[:40]}")
        elif take:
            print(f"  {name:<10} {entry:>5.2f} {current:>5.2f} {high:>5.2f} {atr:>4.2f} {days:>3}天 → 🟢 {treason} 卖{tpct*100:.0f}%")
        else:
            print(f"  {name:<10} {entry:>5.2f} {current:>5.2f} {high:>5.2f} {atr:>4.2f} {days:>3}天 → ✅ 持有")
    
    print(f"\n📋 策略参数对比:")
    print(f"  {'策略':<10} {'ATR止损':>8} {'浮动':>6} {'目标':>6} {'最大亏':>6} {'时限':>5} {'部分卖':>6}")
    for name, p in rm.PRESETS.items():
        print(f"  {name:<10} {p['atr_stop']:>6.1f}× {p['trail_pct']:>4.0%} {p['target']:>5.0%} {p['max_loss']:>5.0%} {p['time_limit']:>4}天 {p['partial']:>5.0%}")
