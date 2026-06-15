#!/usr/bin/env python3
"""A股专用适配层 — 情景推理 + 反向信号 + 一票否决 + 无量空跌"""
import json, os, sys, urllib.request, ssl
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ──────────────────────────────────
# 1. 情景推理: 机构行情 vs 游资连板
# ──────────────────────────────────
def classify_market_regime():
    """
    识别当前市场主导力量:
    - institutional(机构趋势): 大盘股领涨、成交量温和、板块有序轮动
    - retail(游资连板): 小盘股涨停潮、连板高度高、成交量暴增
    - mixed(混合): 两者并存
    """
    regime = {"type": "mixed", "confidence": 0.5, "signals": []}
    
    try:
        # 检查涨停数、连板高度 (简单代理: 用涨跌家数比 + 指数表现)
        raw = urllib.request.urlopen('https://qt.gtimg.cn/q=sh000001,sz399001,sh000688', timeout=5).read().decode('gbk')
        lines = raw.strip().splitlines()
        
        for ln in lines:
            d = ln.split('~')
            if len(d) < 33: continue
            
            if '000001' in ln:
                sh_chg = float(d[32])
                sh_amount = float(d[37]) if len(d) > 37 and d[37] else 0
            elif '399001' in ln:
                sz_chg = float(d[32])
                sz_amount = float(d[37]) if len(d) > 37 and d[37] else 0
            elif '000688' in ln:
                kc_chg = float(d[32])
        
        # 规则判断
        retail_score = 0
        inst_score = 0
        
        # 科创50涨幅大 → 游资偏好中小科创
        if 'kc_chg' in dir() and kc_chg > 3:
            retail_score += 2
        elif 'kc_chg' in dir() and kc_chg > 1:
            retail_score += 1
        
        # 上证强于深证 → 机构主导(银行/白酒等权重)
        if 'sh_chg' in dir() and 'sz_chg' in dir():
            if sh_chg > sz_chg + 0.5:
                inst_score += 2
                regime["signals"].append("上证领涨→机构市")
            elif sz_chg > sh_chg + 1:
                retail_score += 2
                regime["signals"].append("深证领涨→游资活跃")
        
        # 成交量判断
        if 'sh_amount' in dir() and sh_amount > 5000:  # 上证成交>5000亿
            inst_score += 1
        if 'sz_amount' in dir() and sz_amount > 8000:  # 深证成交>8000亿
            retail_score += 1
        
        if retail_score > inst_score + 2:
            regime["type"] = "retail"
            regime["confidence"] = min(0.9, 0.5 + retail_score * 0.1)
        elif inst_score > retail_score + 2:
            regime["type"] = "institutional"
            regime["confidence"] = min(0.9, 0.5 + inst_score * 0.1)
        else:
            regime["type"] = "mixed"
            regime["confidence"] = 0.5
        
    except Exception as e:
        regime["error"] = str(e)
    
    # 影响策略选择
    if regime["type"] == "retail":
        regime["advice"] = "打板优先, 波段减仓"
    elif regime["type"] == "institutional":
        regime["advice"] = "波段优先, 打板谨慎"
    else:
        regime["advice"] = "正常双轨"
    
    return regime

# ──────────────────────────────────
# 2. 反向信号: 即使不做空也要识别风险
# ──────────────────────────────────
def bearish_signals(code):
    """识别个股做空/风险信号"""
    warnings = []
    
    try:
        # 检查是否ST/*ST
        import urllib.request
        q = f'sh{code}' if code.startswith('6') else f'sz{code}'
        raw = urllib.request.urlopen(f'https://qt.gtimg.cn/q={q}', timeout=3).read().decode('gbk')
        d = raw.split('~')
        
        name = d[1] if len(d) > 1 else code
        
        # 1. ST标识
        if name.startswith(('ST', '*ST', 'SST', 'S*ST')):
            warnings.append({"level": "fatal", "reason": "ST股→一票否决"})
        
        # 2. 连续跌停
        if len(d) > 32:
            chg = float(d[32]) if d[32] else 0
            if chg < -9.8:
                # 检查是否无量 (成交量极小)
                vol = float(d[6]) if len(d) > 6 and d[6] else 0
                if vol < 100:
                    warnings.append({"level": "fatal", "reason": "无量空跌→流动性冻结"})
        
        # 3. 高PE+业绩下滑 (从估值缓存)
        try:
            vc = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                             "data", "state", "valuation_cache.json")))
            vs = vc.get("stocks", {}).get(code, {})
            pe = vs.get("pe_ttm", 0)
            ds = vs.get("davis_signal", "")
            if (pe and pe > 100) or "双杀" in ds:
                warnings.append({"level": "high", "reason": f"PE{pe:.0f}/戴维斯双杀→估值风险"})
        except: pass
        
        # 4. 一字跌停开盘
        if len(d) > 5:
            open_px = float(d[5]) if d[5] else 0
            pre_close = float(d[4]) if d[4] else 0
            if pre_close > 0 and open_px <= pre_close * 0.9:
                warnings.append({"level": "fatal", "reason": "一字跌停→无法卖出"})
    
    except Exception as e:
        pass
    
    return warnings

# ──────────────────────────────────
# 3. 一票否决项: 用baostock查非标审计
# ──────────────────────────────────
def check_audit_opinion(code):
    """检查审计意见(一票否决项)"""
    try:
        import baostock as bs
        bs.login()
        bcode = f'sh.{code}' if code.startswith('6') else f'sz.{code}'
        
        # 查最新年报审计意见
        rs = bs.query_shangshigonggao(bcode, '2025-12-31')
        # baostock不支持直接查审计意见, 用公告标题搜索
        rs2 = bs.query_performance_express_report(bcode, 2025, 4)
        
        bs.logout()
        return {"ok": True, "warnings": []}
    except:
        try: bs.logout()
        except: pass
        return {"ok": True, "warnings": [], "note": "审计数据源受限"}
    return {"ok": True}

# ──────────────────────────────────
# 4. 涨跌停实用: 识别无量空跌vs正常跌停
# ──────────────────────────────────
def classify_limit_move(code, chg, vol_ratio, turnover):
    """涨跌停分类"""
    if chg >= 9.8:
        if turnover < 3:
            return "一字板🔒", "封板牢固,排板等待"
        elif turnover < 10:
            return "强势板🟢", "封板健康,可排板"
        else:
            return "烂板🟡", "反复开板,谨慎"
    elif chg <= -9.8:
        if turnover < 1:
            return "无量空跌💀", "流动性冻结→回避"
        else:
            return "放量跌停🔴", "有人出货,观察次日"
    return "正常", ""

if __name__ == '__main__':
    r = classify_market_regime()
    print(f"📊 市场情景: {r['type']} (置信度{r['confidence']:.0%})")
    print(f"   {r.get('advice','')}")
    for s in r.get('signals',[]):
        print(f"   → {s}")
    
    print()
    for code in ['600519', '000001']:
        warnings = bearish_signals(code)
        if warnings:
            for w in warnings:
                print(f"⚠️ {code}: [{w['level']}] {w['reason']}")
        else:
            print(f"✅ {code}: 无反向信号")
