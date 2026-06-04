#!/usr/bin/env python3
"""打板专用 — 封板强度·破板预警·排板策略"""
from datetime import datetime

class BoardAnalyzer:
    """涨停板分析器"""
    
    @staticmethod
    def classify_board(open_time, turnover, volume_ratio, sector_rank):
        """封板分类"""
        score = 0
        # 封板时间越早越好
        if open_time <= "09:35": score += 3   # 秒板
        elif open_time <= "10:00": score += 2  # 早盘板
        elif open_time <= "11:30": score += 1  # 上午板
        else: score += 0                        # 下午板
        
        # 换手率适中最好
        if 2 <= turnover <= 8: score += 2
        elif 8 < turnover <= 15: score += 1
        else: score += 0
        
        # 量比>2放量
        if volume_ratio > 3: score += 2
        elif volume_ratio > 1.5: score += 1
        
        # 板块龙头加分
        if sector_rank == 1: score += 2
        elif sector_rank <= 3: score += 1
        
        if score >= 7: return "💎 钻石板"
        elif score >= 5: return "🥇 黄金板"
        elif score >= 3: return "🥈 白银板"
        else: return "🥉 青铜板"

    @staticmethod
    def break_risk(price, high, turnover, volume):
        """破板风险评估"""
        risk = 0
        # 距涨停价越近越安全
        if price / high > 0.98: risk += 1
        else: risk += 3
        
        # 换手过高容易炸板
        if turnover > 20: risk += 3
        elif turnover > 15: risk += 2
        elif turnover > 10: risk += 1
        
        # 量太大容易炸
        if volume > 5e8: risk += 2
        
        if risk >= 6: return "🔴 高风险"
        elif risk >= 3: return "🟡 中风险"
        else: return "🟢 低风险"

    @staticmethod
    def strategy(board_type, risk_level, price):
        """打板策略"""
        if board_type in ("💎 钻石板", "🥇 黄金板") and risk_level == "🟢 低风险":
            return "排板(挂涨停价排队)"
        elif board_type in ("💎 钻石板", "🥇 黄金板"):
            return "扫板(市价追入)"
        elif board_type == "🥈 白银板" and risk_level != "🔴 高风险":
            return "观察(等回封确认)"
        else:
            return "放弃(风险收益不匹配)"

# 打板术语速查
GLOSSARY = {
    "秒板": "开盘1分钟内涨停→最强信号",
    "一字板": "开盘即涨停全天未打开→极强",
    "T字板": "开盘涨停 盘中打开 尾盘回封→中等",
    "烂板": "多次打开涨停→弱 次日大概率低开",
    "炸板": "涨停后打开未能回封→极弱 回避",
    "排板": "挂涨停价排队等成交→稳健",
    "扫板": "市价追买即将涨停的→激进",
    "打回封": "板打开后再次封板时买入→折中",
    "封单量": "涨停价挂单量 越大越安全",
    "撤单潮": "封单快速减少 预警信号",
}

if __name__ == "__main__":
    print("📖 打板术语速查:")
    for k, v in GLOSSARY.items():
        print(f"  {k:<8} {v}")
    
    print(f"\n🎯 打板策略矩阵:")
    analyzer = BoardAnalyzer()
    print(f"  钻石板+低风险 → {analyzer.strategy('💎 钻石板', '🟢 低风险', 10)}")
    print(f"  黄金板+中风险 → {analyzer.strategy('🥇 黄金板', '🟡 中风险', 10)}")
    print(f"  白银板+低风险 → {analyzer.strategy('🥈 白银板', '🟢 低风险', 10)}")
    print(f"  青铜板+高风险 → {analyzer.strategy('🥉 青铜板', '🔴 高风险', 10)}")
