#!/usr/bin/env python3
"""估值安全边际模块 — PE/PB分位 + 戴维斯双击/双杀 + 安全边际率"""
import baostock as bs
import numpy as np
import json, os
from datetime import datetime, timedelta

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "state", "valuation_cache.json")

def _bcode(code):
    return f'sh.{code}' if code.startswith('6') else f'sz.{code}'

def get_valuation(code):
    """获取单个股票的估值快照"""
    try:
        bs.login()
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d')
        rs = bs.query_history_k_data_plus(_bcode(code),
            'date,close,peTTM,pbMRQ,psTTM',
            start_date=start, end_date=end, frequency='d')
        rows = []
        while rs.next(): rows.append(rs.get_row_data())
        bs.logout()
        
        if not rows: return None
        
        dates, closes, pes, pbs, pss = [], [], [], [], []
        for r in rows:
            d, c, pe, pb, ps = r
            dates.append(d); closes.append(float(c))
            pes.append(float(pe) if pe and pe != '0.000000' else np.nan)
            pbs.append(float(pb) if pb and pb != '0.000000' else np.nan)
            pss.append(float(ps) if ps and ps != '0.000000' else np.nan)
        
        pes_clean = [v for v in pes if not np.isnan(v)]
        pbs_clean = [v for v in pbs if not np.isnan(v)]
        current_pe = pes_clean[-1] if pes_clean else None
        current_pb = pbs_clean[-1] if pbs_clean else None
        
        # PE历史分位
        pe_pct = None
        if current_pe and len(pes_clean) > 60:
            pe_pct = sum(1 for v in pes_clean if v < current_pe) / len(pes_clean) * 100
        
        # PB历史分位  
        pb_pct = None
        if current_pb and len(pbs_clean) > 60:
            pb_pct = sum(1 for v in pbs_clean if v < current_pb) / len(pbs_clean) * 100
        
        # 安全边际率 (简化: 基于PE分位, PE<30%分位=有安全边际)
        margin_safety = 0
        if pe_pct is not None:
            if pe_pct <= 20: margin_safety = 50  # 极度低估
            elif pe_pct <= 30: margin_safety = 30
            elif pe_pct <= 50: margin_safety = 10
            elif pe_pct >= 80: margin_safety = -20  # 高估
            elif pe_pct >= 90: margin_safety = -40  # 泡沫
        
        # 戴维斯双击/双杀检测
        davis_signal = "neutral"
        if len(closes) >= 40 and len(pes_clean) >= 40:
            # 近20日价格趋势
            ma20_price = sum(closes[-20:]) / 20
            price_trend = (closes[-1] / ma20_price - 1) * 100
            # PE变化
            pe_trend = (pes_clean[-1] / np.mean(pes_clean[-20:]) - 1) * 100 if len(pes_clean) >= 20 else 0
            
            if price_trend > 5 and pe_trend > 5:
                davis_signal = "双击🚀"  # EPS↑ + PE↑
            elif price_trend < -5 and pe_trend < -5:
                davis_signal = "双杀💀"  # EPS↓ + PE↓
            elif pe_trend < -10:
                davis_signal = "杀估值⚠️"  # PE单独收缩
        
        return {
            "code": code,
            "pe_ttm": round(current_pe, 2) if current_pe else None,
            "pb_mrq": round(current_pb, 2) if current_pb else None,
            "pe_pct": round(pe_pct, 1) if pe_pct else None,
            "pb_pct": round(pb_pct, 1) if pb_pct else None,
            "margin_safety": margin_safety,  # 安全边际率(%)
            "davis_signal": davis_signal,
            "price": closes[-1] if closes else None,
            "data_days": len(rows),
        }
    except Exception as e:
        try: bs.logout()
        except: pass
        return {"code": code, "error": str(e)}

def batch_valuation(codes, use_cache=True):
    """批量估值(带缓存, 每日刷新)"""
    cache = {}
    today = datetime.now().strftime('%Y-%m-%d')
    
    if use_cache and os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE))
            if cache.get('date') == today:
                cached = cache.get('stocks', {})
                # 返回已有缓存+补缺
                missing = [c for c in codes if c not in cached]
                if not missing:
                    return cached
                # 只查缺失的
                results = {**cached}
                for code in missing[:5]:  # 限5只避免太慢
                    v = get_valuation(code)
                    if v: results[code] = v
                return results
        except: pass
    
    # 全量查询(限5只)
    results = {}
    for code in codes[:5]:
        v = get_valuation(code)
        if v: results[code] = v
    
    # 保存缓存
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    cache = {'date': today, 'stocks': results}
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, default=str)
    
    return results

def valuation_filter(code, verbose=False):
    """估值过滤器: 返回是否通过 + 评分"""
    v = get_valuation(code)
    if not v or v.get('error'):
        return True, "估值数据缺失→放行"
    
    score = 50  # 中性
    reasons = []
    
    # PE分位
    if v.get('pe_ttm') and v.get('pe_pct'):
        pe = v['pe_ttm']; pct = v['pe_pct']
        if pct <= 20:
            score += 25; reasons.append(f"PE{pe:.1f}分位{pct}%低估+25")
        elif pct <= 40:
            score += 10; reasons.append(f"PE分位{pct}%合理偏低+10")
        elif pct >= 85:
            score -= 30; reasons.append(f"PE分位{pct}%高估-30")
        elif pct >= 70:
            score -= 10; reasons.append(f"PE分位{pct}%偏高-10")
    
    # PB分位
    if v.get('pb_mrq') and v.get('pb_pct'):
        pb = v['pb_mrq']; pct = v['pb_pct']
        if pct <= 20:
            score += 15; reasons.append(f"PB{pb:.1f}分位{pct}%破净区+15")
        elif pct >= 85:
            score -= 20; reasons.append(f"PB分位{pct}%高估-20")
    
    # 戴维斯信号
    ds = v.get('davis_signal', 'neutral')
    if '双杀' in ds:
        score -= 25; reasons.append(f"戴维斯双杀-25")
    elif '杀估值' in ds:
        score -= 15; reasons.append(f"杀估值-15")
    elif '双击' in ds:
        score += 20; reasons.append(f"戴维斯双击+20")
    
    # 安全边际
    ms = v.get('margin_safety', 0)
    if ms >= 30:
        score += 15; reasons.append(f"安全边际{ms}%+15")
    elif ms <= -20:
        score -= 20; reasons.append(f"无安全边际{ms}%-20")
    
    if verbose:
        print(f"\n{v['code']} PE{v.get('pe_ttm','?')} 分位{v.get('pe_pct','?')}%")
        for r in reasons: print(f"  {r}")
        print(f"  总分:{score} → {'✅通过' if score >= 30 else '❌否决'}")
    
    return score >= 30, f"估值{score}分"

if __name__ == '__main__':
    import sys
    codes = sys.argv[1:] if len(sys.argv) > 1 else ['600519']
    for code in codes:
        ok, reason = valuation_filter(code, verbose=True)
        print(f"\n{code}: {reason} → {'买入' if ok else '回避'}")
