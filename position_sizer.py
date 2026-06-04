#!/usr/bin/env python3
"""
动态仓位管理 V3.0
ATR波动率调整 + 凯利公式 + 最大回撤约束 + 板块敞口限制
"""
import math
from datetime import datetime

class MarketThermometer:
    """市场温度计 — 驱动总仓位"""
    
    @staticmethod
    def total_exposure(index_chg_5d, volatility, breadth):
        """
        index_chg_5d: 大盘5日涨跌幅(%)
        volatility: 大盘波动率(%)
        breadth: 涨跌比(上涨家数/下跌家数)
        
        返回: 建议总仓位比例 (0-1.0)
        """
        score = 0
        
        # 趋势因子: 大盘5日涨跌
        if index_chg_5d > 3: score += 3      # 强势
        elif index_chg_5d > 1: score += 2    # 偏强
        elif index_chg_5d > -1: score += 1   # 震荡
        elif index_chg_5d > -3: score += 0   # 偏弱
        else: score -= 1                      # 弱势
        
        # 波动因子: 波动越低越敢满仓
        if volatility < 1.0: score += 2      # 低波动
        elif volatility < 1.5: score += 1    # 正常
        elif volatility < 2.5: score += 0    # 偏高
        else: score -= 1                      # 高波动→降仓
        
        # 广度因子: 多数股票涨=健康
        if breadth > 1.5: score += 2         # 普涨
        elif breadth > 1.0: score += 1       # 偏多
        elif breadth > 0.7: score += 0       # 分化
        else: score -= 1                      # 普跌
        
        # 映射到仓位
        exposure_map = {
            -3: 0.15, -2: 0.25, -1: 0.35,
            0: 0.50, 1: 0.65, 2: 0.80,
            3: 0.90, 4: 0.95, 5: 1.00,
            6: 1.00, 7: 1.00
        }
        return exposure_map.get(score, 0.50)

    @staticmethod
    def quick(simple_mode=True):
        """快速评估: 基于上周走势"""
        # 上周上证: 4126→4069 = -1.4%
        # 默认中性偏保守
        return 0.75  # 75%起步，等开盘确认


class PositionSizer:
    """
    三层仓位模型:
    1. 凯利公式 → 理论最优仓位
    2. ATR波动率 → 调整风险敞口
    3. 回撤约束 → 硬性上限
    """
    
    def __init__(self, total_capital=20000, max_capital=20000, 
                 max_single_pct=0.25, max_total_pct=1.0,
                 max_drawdown_pct=0.15):
        """
        total_capital: 总可用资金
        max_capital: 最大风险敞口（用户设定2万）
        max_single_pct: 单只最大仓位占比
        max_total_pct: 总仓位占比上限
        max_drawdown_pct: 触发熔断的回撤阈值
        """
        self.total = total_capital
        self.max = max_capital
        self.max_single_pct = max_single_pct
        self.max_total_pct = max_total_pct
        self.max_dd_pct = max_drawdown_pct
        
        self.current_drawdown = 0.0  # 当前回撤
        self.peak_value = total_capital  # 峰值
        
        self.positions = {}  # {ticker: {size, cost, atr, win_rate, ...}}
        self.sector_exposure = {}  # {sector: total_value}
        self.max_sector_pct = 0.50  # 单板块最大占比(放宽)
        self.market_thermometer = MarketThermometer()
        self.market_exposure = 1.0  # 默认满仓，开盘后根据市场调整
    
    def update_peak(self, current_value):
        """更新峰值"""
        if current_value > self.peak_value:
            self.peak_value = current_value
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.peak_value - current_value) / self.peak_value
    
    # ═══════════════════════════════════
    # 1. 凯利公式
    # ═══════════════════════════════════
    def kelly_fraction(self, win_rate, avg_win, avg_loss):
        """
        凯利公式: f* = (bp - q) / b
        b = 盈亏比 = avg_win / avg_loss
        p = 胜率
        q = 1 - p
        
        返回理论最优仓位比例
        保守使用: 凯利/2 (半凯利)
        """
        if avg_loss == 0:
            return 0
        
        b = avg_win / abs(avg_loss)  # 盈亏比
        p = win_rate
        q = 1 - p
        
        if b <= 0:
            return 0
        
        kelly = (b * p - q) / b
        kelly = max(0, min(kelly, 0.5))  # 封顶50%
        
        # 半凯利更保守
        half_kelly = kelly / 2
        
        return half_kelly
    
    # ═══════════════════════════════════
    # 2. ATR波动率调整
    # ═══════════════════════════════════
    def atr_adjustment(self, price, atr):
        """
        ATR调整: 波动越大 → 仓位越小
        基准: ATR/价格 = 3% 为正常波动
        """
        if price == 0:
            return 1.0
        
        volatility = atr / price  # ATR波动率
        
        if volatility < 0.02:     # 低波动 → 可加仓
            return 1.2
        elif volatility < 0.04:   # 正常
            return 1.0
        elif volatility < 0.06:   # 中高波动
            return 0.7
        elif volatility < 0.10:   # 高波动
            return 0.4
        else:                     # 极高波动
            return 0.15
    
    # ═══════════════════════════════════
    # 3. 回撤约束
    # ═══════════════════════════════════
    def drawdown_limit(self):
        """
        回撤越接近熔断线 → 仓位越小
        """
        if self.current_drawdown >= self.max_dd_pct:
            return 0.0  # 熔断
        
        remaining = self.max_dd_pct - self.current_drawdown
        ratio = remaining / self.max_dd_pct
        
        # 剩余回撤空间比例映射仓位
        if ratio > 0.7:
            return 1.0
        elif ratio > 0.4:
            return 0.6
        elif ratio > 0.2:
            return 0.3
        else:
            return 0.1
    
    # ═══════════════════════════════════
    # 综合计算
    # ═══════════════════════════════════
    def calculate(self, ticker, price, atr, win_rate=0.55, 
                  avg_win=0.08, avg_loss=-0.05, sector=None):
        """
        综合计算单只个股建议仓位
        
        返回:
        {
            "ticker": ticker,
            "price": price,
            "suggested_shares": int,
            "suggested_value": float,
            "kelly_pct": float,
            "atr_mult": float,
            "dd_mult": float,
            "final_pct": float,
            "limits": {...}
        }
        """
        
        # Step 1: 凯利理论仓位
        kelly_pct = self.kelly_fraction(win_rate, avg_win, avg_loss)
        
        # Step 2: ATR波动率调整
        atr_mult = self.atr_adjustment(price, atr)
        
        # Step 3: 回撤约束
        dd_mult = self.drawdown_limit()
        
        if dd_mult == 0:
            return {
                "ticker": ticker, "price": price,
                "suggested_shares": 0, "suggested_value": 0,
                "kelly_pct": kelly_pct, "atr_mult": atr_mult, "dd_mult": dd_mult,
                "final_pct": 0, "status": "🔴 熔断",
                "reason": "回撤已达熔断线"
            }
        
        # 综合仓位比例
        raw_pct = kelly_pct * atr_mult * dd_mult
        
        # 硬性上限
        final_pct = min(raw_pct, self.max_single_pct)
        
        # 板块敞口限制
        if sector:
            current_sector_val = self.sector_exposure.get(sector, 0)
            sector_limit = self.max * self.max_sector_pct
            sector_remaining = sector_limit - current_sector_val
            if sector_remaining <= 0:
                return {
                    "ticker": ticker, "price": price,
                    "suggested_shares": 0, "suggested_value": 0,
                    "kelly_pct": kelly_pct, "atr_mult": atr_mult, "dd_mult": dd_mult,
                    "final_pct": 0, "status": "🔴 板块限制",
                    "reason": f"板块{sector}已满{self.max_sector_pct*100:.0f}%上限"
                }
            final_pct = min(final_pct, sector_remaining / self.max)
        
        # 市场温度调整总仓位
        market_mult = self.market_exposure
        
        # 总仓位限制(动态)
        dynamic_max = self.max * market_mult
        current_used = sum(p.get("cost", 0) * p.get("size", 0) for p in self.positions.values())
        total_remaining = dynamic_max - current_used
        if total_remaining <= 0:
            return {
                "ticker": ticker, "price": price,
                "suggested_shares": 0, "suggested_value": 0,
                "kelly_pct": kelly_pct, "atr_mult": atr_mult, "dd_mult": dd_mult,
                "final_pct": 0, "status": "🔴 仓位已满",
                "reason": f"总仓位已达上限{self.max:,}元"
            }
        final_pct = min(final_pct, total_remaining / self.max)
        
        # 计算股数（按100股取整，A股规则）
        value = self.max * final_pct
        shares = int(value / price / 100) * 100
        
        # 评级
        if final_pct > 0.08:
            status = "🟢 重仓"
        elif final_pct > 0.04:
            status = "🟡 中等"
        elif final_pct > 0:
            status = "🔵 轻仓"
        else:
            status = "⚪ 零仓"
        
        return {
            "ticker": ticker,
            "price": price,
            "suggested_shares": shares,
            "suggested_value": shares * price,
            "kelly_pct": round(kelly_pct * 100, 1),
            "atr_mult": round(atr_mult, 2),
            "dd_mult": round(dd_mult, 2),
            "final_pct": round(final_pct * 100, 1),
            "status": status,
            "reason": f"凯利{kelly_pct*100:.1f}% × ATR{atr_mult:.1f} × 回撤{dd_mult:.1f} → {final_pct*100:.1f}%"
        }
    
    def portfolio_risk_check(self):
        """投资组合整体风险检查"""
        issues = []
        
        # 1. 总仓位检查
        current_used = sum(p.get("cost", 0) * p.get("size", 0) for p in self.positions.values())
        usage_pct = current_used / self.max * 100 if self.max > 0 else 0
        
        if usage_pct > 90:
            issues.append({"level": "🔴", "msg": f"总仓位{usage_pct:.0f}%接近满仓"})
        elif usage_pct > 70:
            issues.append({"level": "🟡", "msg": f"总仓位{usage_pct:.0f}%偏高"})
        
        # 2. 板块集中度
        for sector, val in self.sector_exposure.items():
            pct = val / self.max * 100
            if pct > self.max_sector_pct * 100:
                issues.append({"level": "🟠", "msg": f"板块{sector}占比{pct:.0f}%超标"})
            elif pct > 25:
                issues.append({"level": "🟡", "msg": f"板块{sector}占比{pct:.0f}%集中"})
        
        # 3. 回撤检查
        if self.current_drawdown > self.max_dd_pct * 0.7:
            issues.append({"level": "🟠", "msg": f"回撤{self.current_drawdown*100:.1f}%接近熔断线{self.max_dd_pct*100:.0f}%"})
        elif self.current_drawdown > self.max_dd_pct * 0.5:
            issues.append({"level": "🟡", "msg": f"回撤{self.current_drawdown*100:.1f}%过半"})
        
        return {
            "usage_pct": round(usage_pct, 1),
            "drawdown_pct": round(self.current_drawdown * 100, 1),
            "issues": issues,
            "healthy": len([i for i in issues if i["level"] in ("🔴","🟠")]) == 0
        }
    
    def add_position(self, ticker, shares, cost, atr=None, win_rate=None, sector=None):
        """记录持仓"""
        self.positions[ticker] = {
            "size": shares, "cost": cost,
            "atr": atr or 0, "win_rate": win_rate or 0.55
        }
        if sector:
            self.sector_exposure[sector] = self.sector_exposure.get(sector, 0) + shares * cost
    
    def remove_position(self, ticker, sector=None):
        """移除持仓"""
        if ticker in self.positions:
            pos = self.positions[ticker]
            if sector and sector in self.sector_exposure:
                self.sector_exposure[sector] -= pos["size"] * pos["cost"]
                if self.sector_exposure[sector] < 0:
                    self.sector_exposure[sector] = 0
            del self.positions[ticker]


# ═══════════════════════════════════
# 测试与演示
# ═══════════════════════════════════
if __name__ == "__main__":
    sizer = PositionSizer(total_capital=20000, max_capital=20000)
    
    print("📐 V3.0 动态仓位管理")
    print("=" * 55)
    
    # 场景1: 正常市场
    print("\n场景1: 正常波动 + 无回撤")
    calc1 = sizer.calculate("600027", price=5.50, atr=0.15, 
                            win_rate=0.55, avg_win=0.08, avg_loss=-0.05)
    print(f"  {calc1['ticker']} @¥{calc1['price']}")
    print(f"  {calc1['status']} | 建议{calc1['suggested_shares']}股 ¥{calc1['suggested_value']:,.0f}")
    print(f"  {calc1['reason']}")
    
    # 场景2: 高波动
    print("\n场景2: 高波动(ATR=0.50 即9%波动)")
    calc2 = sizer.calculate("002298", price=12.00, atr=1.10,
                            win_rate=0.55, avg_win=0.08, avg_loss=-0.05,
                            sector="电力")
    print(f"  {calc2['ticker']} @¥{calc2['price']}")
    print(f"  {calc2['status']} | 建议{calc2['suggested_shares']}股 ¥{calc2['suggested_value']:,.0f}")
    print(f"  {calc2['reason']}")
    
    # 场景3: 回撤接近熔断
    print("\n场景3: 回撤12%接近熔断线(15%)")
    sizer.current_drawdown = 0.12
    calc3 = sizer.calculate("000733", price=8.30, atr=0.35,
                            win_rate=0.60, avg_win=0.10, avg_loss=-0.05)
    print(f"  {calc3['ticker']} @¥{calc3['price']}")
    print(f"  {calc3['status']} | 建议{calc3['suggested_shares']}股 ¥{calc3['suggested_value']:,.0f}")
    print(f"  {calc3['reason']}")
    
    # 场景4: 熔断
    sizer.current_drawdown = 0.16
    print("\n场景4: 回撤16%触发熔断")
    calc4 = sizer.calculate("600519", price=1600, atr=30)
    print(f"  {calc4['status']} | 建议{calc4['suggested_shares']}股")
    print(f"  {calc4['reason']}")
    
    # 投资组合检查
    sizer.current_drawdown = 0.12
    sizer.add_position("600027", 300, 5.50, sector="电力")
    sizer.add_position("002298", 200, 12.00, sector="电力")
    sizer.add_position("000733", 100, 8.30, sector="军工")
    
    print(f"\n📊 投资组合风险检查:")
    check = sizer.portfolio_risk_check()
    print(f"  仓位使用率: {check['usage_pct']}%")
    print(f"  当前回撤: {check['drawdown_pct']}%")
    print(f"  健康状态: {'✅ 健康' if check['healthy'] else '⚠️ 预警'}")
    for issue in check["issues"]:
        print(f"  {issue['level']} {issue['msg']}")
