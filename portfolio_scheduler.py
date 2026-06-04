#!/usr/bin/env python3
"""
持仓调度引擎 V1.0
解决: 已有持仓 vs 新候选 → 智能调仓
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math

@dataclass
class Position:
    code: str
    name: str
    shares: int
    cost: float
    current_price: float
    current_score: float      # 当前综合评分
    days_held: int
    profit_pct: float
    highest_price: float
    locked: bool = False      # 锁仓(不卖)

@dataclass
class Candidate:
    code: str
    name: str
    price: float
    score: float              # 综合评分
    reason: str

class PortfolioScheduler:
    """
    持仓调度规则:
    1. 预留现金优先 → 不卖持仓也能买
    2. 评分替换 → 新候选分 > 持仓分+阈值 → 换股
    3. 时间淘汰 → 持仓3天+未盈利 → 候选替换
    4. 利润保护 → 盈利>5%的持仓不轻易换
    5. 板块平衡 → 同板块不超50%
    """
    
    def __init__(self, total_capital=20000, max_positions=6):
        self.capital = total_capital
        self.max_positions = max_positions
        self.replace_threshold = 10  # 新候选需高于持仓10分才换
    
    def schedule(self, positions: List[Position], candidates: List[Candidate], 
                 cash_available: float) -> Dict:
        """
        调度决策
        
        返回: {
            "hold": [...],      # 继续持有的
            "sell": [...],      # 卖出的
            "buy": [...],       # 买入的
            "cash_after": float # 操作后现金
        }
        """
        # ⚠️ 时效规则: 候选仅当日有效, 不跨天复用
        # 每天9:00五源重新筛选, 旧候选作废
        
        actions = {"hold": [], "sell": [], "buy": [], "cash_after": cash_available,
                   "reason": [], "skipped": []}
        
        remaining_cash = cash_available
        
        # ===== 第一步: 评估现有持仓 =====
        for pos in positions:
            should_sell = False
            reason = ""
            
            # 规则1: 跌破止损 → 无条件卖(由risk_manager处理, 这里标记)
            if pos.profit_pct <= -0.08:
                should_sell = True
                reason = f"止损 {pos.profit_pct*100:.0f}%"
            
            # 规则2: 持仓3天+未盈利 → 考虑替换
            elif pos.days_held >= 3 and pos.profit_pct <= 0:
                # 如果有新候选分更高
                better_candidates = [c for c in candidates if c.score > pos.current_score + 5]
                if better_candidates:
                    should_sell = True
                    reason = f"持仓{pos.days_held}天未盈"
            
            # 规则3: 盈利中但回撤严重(从高点跌>8%)
            elif pos.highest_price > pos.cost and pos.profit_pct > 0:
                drawdown = (pos.highest_price - pos.current_price) / pos.highest_price
                if drawdown > 0.08:
                    should_sell = True
                    reason = f"从高点回撤{drawdown*100:.0f}%"
            
            if should_sell and not pos.locked:
                sell_value = pos.shares * pos.current_price
                remaining_cash += sell_value
                actions["sell"].append({"code": pos.code, "name": pos.name, 
                                       "shares": pos.shares, "value": sell_value, "reason": reason})
            else:
                actions["hold"].append(pos)
        
        # ===== 第二步: 买入新候选 =====
        # 按评分排序
        sorted_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
        
        # 当前持仓数
        current_count = len(actions["hold"])
        
        for cand in sorted_candidates:
            # 规则4: 已达最大持仓数 → 检查是否值得替换
            if current_count + len(actions["buy"]) >= self.max_positions:
                # 找最弱的持仓
                weakest = min(actions["hold"], key=lambda p: p.current_score)
                if cand.score > weakest.current_score + self.replace_threshold:
                    # 进一步检查: 切换后预期收益是否更高
                    try:
                        from swap_analyzer import SwapAnalyzer
                        sa = SwapAnalyzer()
                        should, analysis = sa.should_swap(weakest, cand)
                        if should:
                            sell_val = weakest.shares * weakest.current_price
                            remaining_cash += sell_val
                            actions["hold"].remove(weakest)
                            actions["sell"].append({
                                "code": weakest.code, "name": weakest.name,
                                "shares": weakest.shares, "value": sell_val,
                                "reason": f"被{cand.name}替换(预期+{analysis['net_benefit']})"
                            })
                            current_count -= 1
                        else:
                            actions["reason"].append(f"不换{weakest.name}: {analysis['reason']}")
                            continue
                    except:
                        # 回退到纯评分比较
                        sell_val = weakest.shares * weakest.current_price
                        remaining_cash += sell_val
                        actions["hold"].remove(weakest)
                        actions["sell"].append({
                            "code": weakest.code, "name": weakest.name,
                            "shares": weakest.shares, "value": sell_val,
                            "reason": f"被{cand.name}({cand.score}分)替换"
                        })
                        current_count -= 1
                else:
                    break
            
            # 规则5: 已有同股(去重)
            if any(p.code == cand.code for p in actions["hold"]):
                continue
            if any(b["code"] == cand.code for b in actions["buy"]):
                continue
            
            # 规则6: 检查是否值得替换持仓
            if current_count + len(actions["buy"]) >= self.max_positions:
                # 已达上限, 需要替换
                # 找最弱的持仓
                weakest = min(actions["hold"], key=lambda p: p.current_score)
                if cand.score > weakest.current_score + self.replace_threshold:
                    # 替换
                    sell_val = weakest.shares * weakest.current_price
                    remaining_cash += sell_val
                    actions["hold"].remove(weakest)
                    actions["sell"].append({"code": weakest.code, "name": weakest.name,
                                           "shares": weakest.shares, "value": sell_val,
                                           "reason": f"被{cand.name}({cand.score}分)替换"})
                    current_count -= 1
            
            # 计算可买股数
            max_spend = min(remaining_cash * 0.5, self.capital * 0.25)  # 单只≤25%总资金
            shares = int(max_spend / cand.price / 100) * 100
            if shares < 100:
                # 钱不够1手, 用剩余现金能买多少
                shares = int(remaining_cash / cand.price / 100) * 100
            
            if shares >= 100:
                buy_value = shares * cand.price
                if buy_value <= remaining_cash:
                    remaining_cash -= buy_value
                    actions["buy"].append({
                        "code": cand.code, "name": cand.name,
                        "shares": shares, "price": cand.price,
                        "value": buy_value, "score": cand.score,
                        "reason": cand.reason
                    })
        
        # 标记未买入的候选为过期(当日有效)
        bought_codes = {b["code"] for b in actions["buy"]}
        for cand in sorted_candidates:
            if cand.code not in bought_codes:
                actions["skipped"].append({
                    "code": cand.code, "name": cand.name,
                    "score": cand.score, "reason": "资金不足/持仓满/评分不够"
                })
        
        actions["cash_after"] = remaining_cash
        
        # 生成操作说明
        actions["reason"] = self._generate_summary(actions, positions, candidates)
        
        return actions
    
    def _generate_summary(self, actions, positions, candidates):
        lines = []
        if actions["sell"]:
            names = ",".join(s["name"] for s in actions["sell"])
            lines.append(f"卖出: {names}")
        if actions["buy"]:
            names = ",".join(b["name"] for b in actions["buy"])
            lines.append(f"买入: {names}")
        if not actions["sell"] and not actions["buy"]:
            lines.append("持仓不变, 无新买入")
        return lines

# ═══════════════════════════════════
# 场景演示
# ═══════════════════════════════════
if __name__ == "__main__":
    sched = PortfolioScheduler(total_capital=20000, max_positions=4)
    
    print("=" * 65)
    print("  📦 持仓调度引擎 — 场景演示")
    print("=" * 65)
    
    # 场景: 周一买了长江电力+春秋电子, 周二新候选出现
    print("\n📅 场景: 周二调仓")
    print("-" * 50)
    
    positions = [
        Position("600900", "长江电力", 200, 27.75, 28.00, 55, 1, 0.009, 28.10),
        Position("603890", "春秋电子", 300, 24.81, 25.50, 48, 1, 0.028, 25.60),
    ]
    
    candidates = [
        Candidate("600183", "生益科技", 138.00, 72, "五源TOP1, 回踩到位"),
        Candidate("002463", "沪电股份", 130.00, 65, "PCB板块共振"),
        Candidate("000636", "风华高科", 50.00, 58, "元器件放量"),
    ]
    
    result = sched.schedule(positions, candidates, cash_available=7007)
    
    print(f"💰 可用资金: ¥7,007")
    print(f"\n📊 调度决策:")
    
    if result["sell"]:
        print(f"\n  🔴 卖出:")
        for s in result["sell"]:
            print(f"     {s['name']} {s['code']} {s['shares']}股 ¥{s['value']:,.0f} ({s['reason']})")
    
    print(f"\n  ✅ 持有:")
    for p in result["hold"]:
        print(f"     {p.name} {p.code} {p.shares}股 ¥{p.current_price:.2f}")
    
    if result["buy"]:
        print(f"\n  🟢 买入:")
        for b in result["buy"]:
            print(f"     {b['name']} {b['code']} {b['shares']}股 @¥{b['price']:.2f} = ¥{b['value']:,.0f}")
    
    print(f"\n  💵 剩余现金: ¥{result['cash_after']:,.0f}")

    # 场景2: 持仓亏损+新候选更好
    print(f"\n\n📅 场景2: 周四防守 — 持仓亏损需要换")
    print("-" * 50)
    
    positions2 = [
        Position("600900", "长江电力", 200, 27.75, 26.50, 35, 3, -0.045, 28.10),
        Position("603890", "春秋电子", 300, 24.81, 23.00, 28, 3, -0.073, 25.60),
    ]
    
    result2 = sched.schedule(positions2, candidates, cash_available=5000)
    
    for s in result2["sell"]:
        print(f"  🔴 卖 {s['name']}: {s['reason']}")
    for b in result2["buy"]:
        print(f"  🟢 买 {b['name']} {b['shares']}股 评分{b['score']}")
    for p in result2["hold"]:
        print(f"  ✅ 留 {p.name}")
    
    # 时效演示
    print(f"\n\n⏰ 时效规则演示:")
    if result["skipped"]:
        print(f"  以下候选未买入(当日有效, 明天作废):")
        for s in result["skipped"][:3]:
            print(f"    ❌ {s['name']} {s['code']} 评分{s['score']} — {s['reason']}")
        print(f"  ⚠️ 明天9:00重新筛选, 这些候选自动作废")
    
    print(f"\n📋 调度规则总结:")
    print(f"  1. 优先用剩余现金买(不卖持仓)")
    print(f"  2. 新候选>持仓分+10 → 替换弱持仓")
    print(f"  3. 持仓3天未盈 → 被替换")
    print(f"  4. 盈利>5%不换(利润保护)")
    print(f"  5. 同板块≤50%, 总持仓≤4只")
