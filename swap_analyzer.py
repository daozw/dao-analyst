#!/usr/bin/env python3
"""
持仓切换收益对比引擎 V1.0
核心: 卖出旧持仓买新候选 → 必须证明新候选预期收益更高
"""
import math

class SwapAnalyzer:
    """
    切换分析:
    1. 估算旧持仓预期收益
    2. 估算新候选预期收益
    3. 仅当: 新收益 > 旧收益 + 缓冲 → 允许切换
    """
    
    SWAP_BUFFER = 0.02  # 切换需要至少2%超额收益(覆盖摩擦成本)
    
    @staticmethod
    def estimate_holding_return(position, days_remaining=3):
        """
        估算持仓剩余预期收益
        
        因子:
        - 动量: 正动量→继续, 负动量→反转概率
        - ATR: 波动大→潜在收益高但也风险高
        - 时间: 持有越久→不确定性越大
        """
        if position.days_held == 0:
            return 0.05  # 新仓默认5%
        
        # 动量因子: 最近走势
        daily_return = position.profit_pct / position.days_held
        
        # 反转概率: 连续涨多了→回调概率增加
        if position.profit_pct > 0.10:
            reversal_prob = 0.4  # 涨10%+ → 40%概率回调
        elif position.profit_pct > 0.05:
            reversal_prob = 0.2
        elif position.profit_pct > 0:
            reversal_prob = 0.1
        elif position.profit_pct > -0.03:
            reversal_prob = 0.05  # 微跌→可能反弹
        else:
            reversal_prob = 0.3  # 跌多了→可能继续跌
        
        # 预期日收益 (考虑反转)
        expected_daily = daily_return * (1 - reversal_prob) * 0.7  # 动量衰减
        
        # 乘剩余天数
        remaining_return = expected_daily * days_remaining
        
        # 限制在合理范围
        return max(-0.10, min(0.20, remaining_return))
    
    @staticmethod
    def estimate_candidate_return(candidate, atr_pct=0.03):
        """
        估算新候选预期收益
        
        基于:
        - 评分 (0-100 → 映射到预期收益)
        - 波动 (ATR → 潜在收益)
        - 当前涨跌 (追高→低预期, 回调→高预期)
        """
        # 评分到收益率映射
        if candidate.score >= 70:
            base_return = 0.12
        elif candidate.score >= 60:
            base_return = 0.09
        elif candidate.score >= 50:
            base_return = 0.06
        elif candidate.score >= 40:
            base_return = 0.03
        else:
            base_return = 0.01
        
        # ATR调整: 高波动→高潜在收益但需折扣
        vol_mult = min(1.5, max(0.5, atr_pct / 0.03))
        adjusted = base_return * vol_mult
        
        # 追高折扣: 涨幅>5%→预期降低
        if hasattr(candidate, 'chg') and candidate.chg > 5:
            adjusted *= 0.7
        elif hasattr(candidate, 'chg') and candidate.chg > 3:
            adjusted *= 0.85
        
        return max(0.01, min(0.20, adjusted))
    
    def should_swap(self, position, candidate, days_remaining=3):
        """
        判断是否应该切换
        
        返回: (should_swap: bool, analysis: dict)
        """
        # 估算双方预期收益
        hold_return = self.estimate_holding_return(position, days_remaining)
        new_return = self.estimate_candidate_return(candidate)
        
        # 净收益 = 新收益 - 旧收益
        net_benefit = new_return - hold_return
        
        # 决策
        should = net_benefit > self.SWAP_BUFFER
        
        return should, {
            "position": {
                "name": position.name,
                "code": position.code,
                "current_profit": f"{position.profit_pct*100:+.1f}%",
                "daily_return": f"{position.profit_pct/position.days_held*100:+.2f}%/天" if position.days_held > 0 else "新仓",
                "expected_remaining": f"{hold_return*100:+.1f}%",
                "days_held": position.days_held,
            },
            "candidate": {
                "name": candidate.name,
                "code": candidate.code,
                "score": candidate.score,
                "expected_return": f"{new_return*100:+.1f}%",
            },
            "net_benefit": f"{net_benefit*100:+.1f}%",
            "verdict": "✅ 切换" if should else "❌ 持有",
            "reason": self._reason(should, hold_return, new_return, net_benefit)
        }
    
    def _reason(self, should, hold, new, net):
        if should:
            if new > hold * 1.5:
                return f"新候选预期{new*100:.1f}%远超持仓{hold*100:.1f}%"
            return f"新候选预期{new*100:.1f}% > 持仓{hold*100:.1f}%+缓冲"
        else:
            if hold > new:
                return f"持仓预期{hold*100:.1f}% > 新候选{new*100:.1f}%, 不值得换"
            else:
                diff = (new - hold) * 100
                return f"新候选仅高{diff:.1f}%, 不足{self.SWAP_BUFFER*100:.0f}%缓冲, 不换"

# ═══════════════════════════════════
# 场景演示
# ═══════════════════════════════════
if __name__ == "__main__":
    from portfolio_scheduler import Position, Candidate
    
    analyzer = SwapAnalyzer()
    
    print("=" * 65)
    print("  ⚖️ 持仓切换收益对比引擎")
    print("=" * 65)
    
    # 场景1: 持仓盈利 vs 新候选 → 不换
    print("\n📊 场景1: 持仓盈利中, 新候选出来")
    pos1 = Position("600900", "长江电力", 200, 27.75, 28.50, 55, 2, 0.027, 28.60)
    cand1 = Candidate("600183", "生益科技", 140.00, 72, "PCB龙头")
    
    should, analysis = analyzer.should_swap(pos1, cand1)
    print(f"  持仓: {analysis['position']['name']} 盈利{analysis['position']['current_profit']}")
    print(f"       预期剩余收益: {analysis['position']['expected_remaining']}")
    print(f"  候选: {analysis['candidate']['name']} 评分{analysis['candidate']['score']}")
    print(f"       预期收益: {analysis['candidate']['expected_return']}")
    print(f"  净收益差: {analysis['net_benefit']}")
    print(f"  判定: {analysis['verdict']} — {analysis['reason']}")
    
    # 场景2: 持仓微亏 vs 高评分候选 → 换
    print("\n📊 场景2: 持仓微亏, 高评分候选")
    pos2 = Position("603890", "春秋电子", 300, 24.81, 24.20, 38, 3, -0.025, 25.60)
    cand2 = Candidate("600183", "生益科技", 138.00, 72, "PCB龙头回踩到位")
    
    should2, analysis2 = analyzer.should_swap(pos2, cand2)
    print(f"  持仓: {analysis2['position']['name']} 盈利{analysis2['position']['current_profit']}")
    print(f"       预期剩余收益: {analysis2['position']['expected_remaining']}")
    print(f"  候选: {analysis2['candidate']['name']} 评分{analysis2['candidate']['score']}")
    print(f"       预期收益: {analysis2['candidate']['expected_return']}")
    print(f"  净收益差: {analysis2['net_benefit']}")
    print(f"  判定: {analysis2['verdict']} — {analysis2['reason']}")
    
    # 场景3: 持仓大涨 vs 平庸候选 → 不换
    print("\n📊 场景3: 持仓大涨10%, 新候选平庸")
    pos3 = Position("600900", "长江电力", 200, 27.75, 30.53, 70, 4, 0.10, 30.80)
    cand3 = Candidate("000636", "风华高科", 50.00, 45, "元器件一般")
    
    should3, analysis3 = analyzer.should_swap(pos3, cand3)
    print(f"  持仓: {analysis3['position']['name']} 盈利{analysis3['position']['current_profit']}")
    print(f"       预期剩余收益: {analysis3['position']['expected_remaining']}")
    print(f"  候选: {analysis3['candidate']['name']} 评分{analysis3['candidate']['score']}")
    print(f"       预期收益: {analysis3['candidate']['expected_return']}")
    print(f"  净收益差: {analysis3['net_benefit']}")
    print(f"  判定: {analysis3['verdict']} — {analysis3['reason']}")
    
    # 场景4: 你的问题场景 — 卖了涨的买平庸的
    print("\n📊 场景4: ⚠️ 危险切换 — 卖掉盈利仓换平庸股")
    pos4 = Position("600900", "长江电力", 200, 27.75, 29.50, 62, 3, 0.063, 29.80)
    cand4 = Candidate("000636", "风华高科", 55.00, 48, "平庸候选")
    
    should4, analysis4 = analyzer.should_swap(pos4, cand4)
    print(f"  持仓: {analysis4['position']['name']} 盈利{analysis4['position']['current_profit']}")
    print(f"       预期剩余收益: {analysis4['position']['expected_remaining']}")
    print(f"  候选: {analysis4['candidate']['name']} 评分{analysis4['candidate']['score']}")
    print(f"       预期收益: {analysis4['candidate']['expected_return']}")
    print(f"  净收益差: {analysis4['net_benefit']}")
    print(f"  判定: {analysis4['verdict']} — {analysis4['reason']}")
    print(f"  💡 系统阻止了这笔亏钱交易")

    # 总结
    print(f"\n{'='*65}")
    print(f"  📋 切换规则总结")
    print(f"{'='*65}")
    print(f"  1. 估算双方预期收益(动量+波动+评分)")
    print(f"  2. 新收益 > 旧收益 + 2%缓冲 → 才切换")
    print(f"  3. 持仓盈利>5% → 反转概率上升 → 不轻易换")
    print(f"  4. 考虑了追高风险(涨幅>5%的候选→预期打折)")
    print(f"  5. 避免'卖了涨的买跌的'亏钱操作")
