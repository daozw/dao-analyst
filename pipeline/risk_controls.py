#!/usr/bin/env python3
"""风险管理模块 — 行业分散 + 凯利仓位 + 隔夜风险"""
import json, os, sys, math
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 行业分散检查 ──
SECTOR_LIMIT = 0.40  # 单一行业最多占仓位40%

def get_sector(code):
    """从池子信息获取行业"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        wl = json.load(open(os.path.join(base, "data/watchlist.json")))
        for gn, g in wl.get("groups", {}).items():
            for s in g.get("stocks", []):
                if s["code"] == code:
                    return s.get("sector", s.get("industry", "未知"))
    except: pass
    # fallback: 从腾讯行情获取
    try:
        import urllib.request, ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        q = f'sh{code}' if code.startswith('6') else f'sz{code}'
        raw = urllib.request.urlopen(
            f'https://qt.gtimg.cn/q={q}', timeout=5
        ).read().decode('gbk')
        d = raw.split('~')
        # 腾讯返回格式中, 行业在特定位置
        if len(d) > 12: return d[12] if d[12] else "未知"
    except: pass
    return "未知"

def check_sector_concentration(positions, new_code, new_sector=None):
    """检查行业集中度: 返回(是否通过, 当前集中度, 风险行业)"""
    if new_sector is None:
        new_sector = get_sector(new_code)
    
    sectors = {}
    for code, pos in positions.items():
        sec = pos.get("sector", get_sector(code))
        sectors[sec] = sectors.get(sec, 0) + pos.get("qty", 0) * pos.get("cost", 0)
    
    total = sum(sectors.values())
    new_total = total + (sum(p.get("qty",0) * p.get("cost",0) for p in [positions.get(new_code, {})]) or 1000)
    
    conc = {}
    max_sec = ""
    max_pct = 0
    for sec, val in sectors.items():
        pct = val / max(total, 1) * 100
        conc[sec] = round(pct, 1)
        if pct > max_pct:
            max_pct = pct
            max_sec = sec
    
    # 新买入后集中度
    if new_sector:
        new_val = sectors.get(new_sector, 0) + 1000  # 预估新仓
        new_pct = new_val / max(new_total, 1) * 100
        if new_pct > SECTOR_LIMIT * 100:
            return False, conc, f"{new_sector}集中度{new_pct:.0f}%>{SECTOR_LIMIT*100:.0f}%"
    
    return True, conc, ""

# ── 凯利公式仓位 ──
def kelly_position(win_rate, avg_win, avg_loss, capital, price, max_risk_pct=0.02):
    """
    凯利公式: f* = p - (1-p) / (W/L)
    f* = 最优仓位比例
    实际使用半凯利(f*/2)降低波动
    """
    if win_rate <= 0 or avg_loss <= 0:
        return int(capital * 0.01 / price / 100) * 100  # fallback: 1%
    
    p = win_rate / 100  # 胜率
    w_l = avg_win / avg_loss if avg_loss > 0 else 1  # 盈亏比
    
    # 凯利比例
    kelly_f = p - (1 - p) / w_l
    
    # 半凯利 + 上限
    half_kelly = max(0, min(kelly_f * 0.5, max_risk_pct))
    
    amount = capital * half_kelly
    shares = int(amount / price / 100) * 100
    return max(100, shares)  # 至少100股

def load_kelly_params():
    """从学习数据中获取凯利参数"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lf = os.path.join(base, "data", "state", "learning.json")
        if os.path.exists(lf):
            learn = json.load(open(lf))
            patterns = learn.get("patterns", {})
            return (
                patterns.get("win_rate", 50),  # 默认50%
                patterns.get("avg_win", 5.0),   # 默认5%
                abs(patterns.get("avg_loss", 3.0))  # 默认3%
            )
    except: pass
    # fallback: 保守参数
    return 50, 5.0, 3.0

# ── 隔夜风险估计 ──
def overnight_risk(code, confidence=0.95):
    """估计隔夜最大亏损(VaR)"""
    try:
        import numpy as np
        import baostock as bs
        from datetime import datetime, timedelta
        
        bs.login()
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        bcode = f'sh.{code}' if code.startswith('6') else f'sz.{code}'
        rs = bs.query_history_k_data_plus(bcode, 'date,open,close,preclose',
            start_date=start, end_date=end, frequency='d')
        gaps = []
        while rs.next():
            r = rs.get_row_data()
            pre = float(r[3])
            opn = float(r[1])
            if pre > 0:
                gaps.append((opn - pre) / pre * 100)
        bs.logout()
        
        if len(gaps) < 30:
            return None
        
        var = np.percentile(gaps, (1 - confidence) * 100)
        return round(var, 2)  # 负值表示亏损
    except Exception as e:
        try: bs.logout()
        except: pass
        return None

if __name__ == '__main__':
    # 测试
    print("行业: 600519 →", get_sector("600519"))
    print("行业: 000001 →", get_sector("000001"))
    
    wr, aw, al = load_kelly_params()
    print(f"\n凯利参数: 胜率{wr}% 均盈{aw}% 均亏{al}%")
    shares = kelly_position(wr, aw, al, 50000, 10.0)
    print(f"凯利仓位: ¥50,000 @¥10 → {shares}股")
